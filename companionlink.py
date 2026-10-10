"""
Sambungan ke aplikasi pendamping Android ("LinkDeck Pendamping", paket id.linkdeck.companion).

Bila terpasang di HP, LinkDeck menyambung ke soket lokalnya lewat adb
(`adb forward tcp:0 localabstract:linkdeck_companion`) dan menerima secara langsung (push):
  * notifikasi baru / berubah / hilang, lengkap dengan tombol aksinya -> bisa dibalas dari laptop;
  * status baterai: persen, sedang diisi atau tidak, jenis pengisi daya, suhu.
Selama pendamping tersambung, LinkDeck berhenti menjalankan `dumpsys notification` / `dumpsys battery`
berkala untuk HP itu (lebih hemat, penting untuk Bluetooth). Tanpa pendamping semuanya tetap jalan seperti dulu.

Protokol: satu objek JSON per baris; lihat companion/src/.../NotifService.java.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

import notif

core = None          # modul server, diisi register()

PKG = "id.linkdeck.companion"
COMPONENT = f"{PKG}/{PKG}.NotifService"
SOCKET = "linkdeck_companion"
APK_NAME = "linkdeck-companion.apk"
REPO = "karamoyyy/LinkDeck"
RELEASE_URL = f"https://github.com/{REPO}/releases/latest/download/{APK_NAME}"
PING_EVERY, DEAD_AFTER = 25, 70

ERRORS = {
    "gone": "Notifikasi itu sudah tidak ada di HP.",
    "no action": "Tombol notifikasi itu sudah tidak tersedia.",
    "not a reply action": "Notifikasi itu tidak bisa dibalas.",
    "empty": "Tulis balasan dulu.",
    "denied": "Akses ditolak oleh aplikasi pendamping.",
}


def version_code(v: str) -> int:
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v or "")
    return int(m.group(1)) * 10000 + int(m.group(2)) * 100 + int(m.group(3)) if m else 0


def bundled_apk() -> Path | None:
    p = core.ROOT / "companion" / APK_NAME
    return p if p.is_file() else None


def cached_apk() -> Path:
    return core.user_data_dir() / "companion" / APK_NAME


# ================================================================ sambungan per HP

class Link:
    def __init__(self, serial: str) -> None:
        self.serial = serial
        self.task: asyncio.Task | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.port: int | None = None
        self.connected = False
        self.full = False
        self.listening = False
        self.hello: dict = {}
        self.battery: dict | None = None
        self.state = "idle"            # idle | connecting | on | off (layanan tidak jalan) | error
        self.error = ""
        self.pending: dict[int, asyncio.Future] = {}
        self.next_id = 1
        self.keys: dict[str, str] = {}   # kunci notifikasi -> id item di S.notifs
        self.last_rx = 0.0
        self.replied: dict[str, float] = {}   # kunci -> waktu balasan dari laptop (pembaruan berikutnya tidak di-toast)

    def status(self) -> dict:
        return {"state": self.state, "connected": self.connected, "full": self.full,
                "listening": self.listening, "version": self.hello.get("app"), "error": self.error,
                "battery": self.battery}

    async def send(self, obj: dict) -> None:
        w = self.writer
        if not w:
            raise ConnectionError("pendamping belum tersambung")
        w.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
        await w.drain()

    async def request(self, obj: dict, timeout: float = 10) -> dict:
        rid = self.next_id
        self.next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[rid] = fut
        try:
            await self.send({**obj, "id": rid})
            return await asyncio.wait_for(fut, timeout)
        finally:
            self.pending.pop(rid, None)

    async def run(self) -> None:
        S = core.S
        self.state, self.error = "connecting", ""
        c, out, err = await core.run("adb", "-s", self.serial, "forward", "tcp:0", f"localabstract:{SOCKET}", timeout=10)
        if c or not out.strip().isdigit():
            self.state, self.error = "error", (err or out).strip()[:200]
            return
        self.port = int(out.strip())
        try:
            reader, self.writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", self.port), 8)
            # bila layanan tidak berjalan (akses notifikasi mati), adb langsung menutup sambungan
            line = await asyncio.wait_for(reader.readline(), 10)
            if not line:
                self.state = "off"
                return
            await self.handle(json.loads(line))
            self.connected = True
            await broadcast_status(self.serial)
            pinger = asyncio.create_task(self.ping_loop())
            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    self.last_rx = time.time()
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    await self.handle(msg)
            finally:
                pinger.cancel()
            self.state = "idle"
        except (OSError, asyncio.TimeoutError, ValueError) as e:
            self.state, self.error = "error", str(e)[:200]
        finally:
            was = self.connected
            self.connected = False
            if self.writer:
                self.writer.close()
                self.writer = None
            for f in self.pending.values():
                if not f.done():
                    f.set_exception(ConnectionError("sambungan ke pendamping terputus"))
            await core.run("adb", "-s", self.serial, "forward", "--remove", f"tcp:{self.port}", timeout=6)
            if was:
                S.polled.pop("notif:" + self.serial, None)     # kembali ke cara lama secepatnya
                S.polled.pop("bat:" + self.serial, None)
                mine = [x for x in S.notifs if x.get("serial") == self.serial]
                for x in mine:
                    x["live"] = False                           # tombol Balas/aksi tidak bisa dipakai lagi
                if mine:
                    await core.broadcast({"type": "notif_sync", "serial": self.serial, "items": mine})
                await broadcast_status(self.serial)

    async def ping_loop(self) -> None:
        self.last_rx = time.time()
        while True:
            await asyncio.sleep(PING_EVERY)
            if time.time() - self.last_rx > DEAD_AFTER and self.writer:
                self.writer.close()            # tidak ada jawaban: anggap putus, readline() selesai
                return
            try:
                await self.send({"type": "ping"})
            except (ConnectionError, OSError):
                return

    # ------------------------------------------------------------ pesan dari HP

    async def handle(self, m: dict) -> None:
        t = m.get("type")
        if t == "hello":
            self.hello, self.full = m, bool(m.get("full"))
            self.listening = bool(m.get("listening"))
            self.state = "on"
        elif t == "battery":
            await self.on_battery(m)
        elif t == "list":
            self.listening = bool(m.get("listening", self.listening))
            await self.on_list(m.get("items") or [])
        elif t == "notif":
            self.listening = True
            if m.get("op") == "posted" and isinstance(m.get("n"), dict):
                await self.on_posted(m["n"])
            elif m.get("op") == "removed":
                await self.on_removed(str(m.get("key", "")))
        elif t == "result":
            f = self.pending.get(m.get("id"))
            if f and not f.done():
                f.set_result(m)

    async def on_battery(self, m: dict) -> None:
        S = core.S
        self.battery = {k: m.get(k) for k in ("level", "status", "plugged", "charging", "temp", "voltage", "current_ua")}
        s = S.stats.setdefault(self.serial, {"lat": [], "bat": [], "temp": None})
        level = m.get("level")
        if isinstance(level, int) and 0 <= level <= 100:
            s["bat"] = (s["bat"] + [level])[-30:]
        if isinstance(m.get("temp"), (int, float)):
            s["temp"] = round(float(m["temp"]), 1)
        s["charging"] = bool(m.get("charging"))
        s["plugged"] = m.get("plugged") or "none"
        s["bstatus"] = m.get("status")
        s["via"] = "companion"
        await core.broadcast({"type": "battery", "serial": self.serial, "level": level,
                              "charging": s["charging"], "plugged": s["plugged"], "temp": s["temp"]})

    def make_item(self, n: dict) -> dict | None:
        pkg = str(n.get("pkg") or "")
        if (pkg in notif.SKIP_PKGS or pkg == PKG or n.get("ongoing") or n.get("foreground")
                or n.get("summary")):
            return None
        title, text = str(n.get("title") or ""), str(n.get("text") or "")
        msgs = [x for x in (n.get("messages") or []) if isinstance(x, dict)][-5:]
        if msgs and not text:
            text = str(msgs[-1].get("text") or "")
        if not (title or text):
            return None
        key = str(n.get("key") or "")
        labels = {a["pkg"]: a["label"] for a in core.S.apps.get(self.serial, [])}
        app = str(n.get("app") or "") or labels.get(pkg) or pkg.rsplit(".", 1)[-1].capitalize()
        acts = [{"i": int(a.get("i", -1)), "title": str(a.get("title") or "")[:60], "reply": bool(a.get("reply")),
                 "hint": str(a.get("hint") or "")[:60]}
                for a in (n.get("actions") or []) if isinstance(a, dict) and a.get("title")][:4]
        t = n.get("time")
        return {"id": hashlib.sha1(f"{key}|{title}|{text}".encode()).hexdigest()[:12],
                "serial": self.serial, "key": key, "pkg": pkg, "app": app[:60],
                "title": title[:200], "text": text[:1000], "t": (t / 1000) if isinstance(t, (int, float)) and t > 0 else time.time(),
                "quiet": False, "actions": acts, "clearable": bool(n.get("clearable", True)),
                "conversation": str(n.get("conversation") or "")[:120],
                "messages": [{"from": str(x.get("from") or "")[:80], "text": str(x.get("text") or "")[:500]} for x in msgs],
                "live": True}

    async def on_list(self, raw: list) -> None:
        S = core.S
        seen = S.notif_seen.setdefault(self.serial, set())
        items = []
        for n in raw:
            it = self.make_item(n) if isinstance(n, dict) else None
            if it:
                it["quiet"] = True          # daftar awal: sudah ada di HP, jangan munculkan toast beruntun
                seen.add(it["id"])
                items.append(it)
        items.sort(key=lambda x: -x["t"])
        S.notifs = [x for x in S.notifs if x.get("serial") != self.serial] + items
        S.notifs.sort(key=lambda x: -x["t"])
        del S.notifs[60:]
        self.keys = {it["key"]: it["id"] for it in items}
        await core.broadcast({"type": "notif_sync", "serial": self.serial, "items": items})

    async def on_posted(self, n: dict) -> None:
        S = core.S
        it = self.make_item(n)
        key = str(n.get("key") or "")
        if not it:
            if key in self.keys:
                await self.on_removed(key)
            return
        seen = S.notif_seen.setdefault(self.serial, set())
        fresh = it["id"] not in seen
        seen.add(it["id"])
        if time.time() - self.replied.pop(key, 0) < 15:
            it["quiet"] = True              # pembaruan karena balasan dari laptop sendiri
        old = next((x for x in S.notifs if x.get("serial") == self.serial and x.get("key") == key), None)
        if old is not None:
            S.notifs.remove(old)
        if fresh or old is None:
            S.notifs.insert(0, it)
        else:
            it["t"] = old["t"]
            S.notifs.insert(next((i for i, x in enumerate(S.notifs) if x["t"] <= it["t"]), len(S.notifs)), it)
        del S.notifs[60:]
        self.keys[key] = it["id"]
        if len(seen) > 2000:
            S.notif_seen[self.serial] = set(self.keys.values())
        await core.broadcast({"type": "notif_upsert", "item": it, "fresh": fresh})

    async def on_removed(self, key: str) -> None:
        S = core.S
        self.keys.pop(key, None)
        before = len(S.notifs)
        S.notifs = [x for x in S.notifs if not (x.get("serial") == self.serial and x.get("key") == key)]
        if len(S.notifs) != before:
            await core.broadcast({"type": "notif_gone", "serial": self.serial, "key": key})


LINKS: dict[str, Link] = {}
INSTALLED: dict[str, dict] = {}      # serial -> {"installed": bool, "code": int, "t": waktu cek}
UPDATED: set[str] = set()


def live(serial: str) -> Link | None:
    lk = LINKS.get(serial)
    return lk if lk and lk.connected else None


def notif_live(serial: str) -> bool:
    lk = live(serial)
    return bool(lk and lk.full and lk.listening)


def battery_live(serial: str) -> bool:
    lk = live(serial)
    return bool(lk and lk.battery)


def status(serial: str) -> dict:
    lk = LINKS.get(serial)
    inst = INSTALLED.get(serial) or {}
    st = lk.status() if lk else {"state": "idle", "connected": False}
    return {**st, "installed": inst.get("installed"), "installed_code": inst.get("code", 0),
            "bundled": bool(bundled_apk()), "bundled_code": version_code(core.VERSION)}


async def broadcast_status(serial: str) -> None:
    await core.broadcast({"type": "companion", "serial": serial, "status": status(serial)})


async def check_installed(serial: str) -> dict:
    c, out, _ = await core.run("adb", "-s", serial, "shell", f"dumpsys package {PKG} | grep -m1 versionCode=",
                               timeout=10)
    m = re.search(r"versionCode=(\d+)", out)
    info = {"installed": bool(m), "code": int(m.group(1)) if m else 0, "t": time.time()}
    INSTALLED[serial] = info
    return info


async def grant(serial: str) -> bool:
    """Nyalakan akses notifikasi untuk pendamping lewat adb (tanpa membuka Pengaturan)."""
    c, out, err = await core.run("adb", "-s", serial, "shell", "cmd", "notification", "allow_listener", COMPONENT,
                                 timeout=10)
    if c or re.search(r"(?i)unknown|exception|error", out + err):
        # Android lama: tambahkan sendiri ke daftar pendengar
        _, cur, _ = await core.run("adb", "-s", serial, "shell", "settings", "get", "secure",
                                   "enabled_notification_listeners", timeout=8)
        cur = cur.strip()
        parts = [p for p in ("" if cur == "null" else cur).split(":") if p]
        if COMPONENT not in parts:
            parts.append(COMPONENT)
            await core.run("adb", "-s", serial, "shell", "settings", "put", "secure",
                           "enabled_notification_listeners", ":".join(parts), timeout=8)
    _, now, _ = await core.run("adb", "-s", serial, "shell", "settings", "get", "secure",
                               "enabled_notification_listeners", timeout=8)
    return PKG in now


async def get_apk() -> Path:
    b = bundled_apk()
    if b:
        return b
    dest = cached_apk()
    if dest.is_file() and time.time() - dest.stat().st_mtime < 7 * 86400:
        return dest

    def dl() -> None:
        req = urllib.request.Request(RELEASE_URL, headers={"User-Agent": "linkdeck"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(20 * 1024 * 1024)
        if not data.startswith(b"PK"):
            raise OSError("berkas unduhan bukan APK")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
    try:
        await asyncio.to_thread(dl)
    except Exception as e:
        if dest.is_file():
            return dest
        raise RuntimeError(f"APK pendamping tidak ada di aplikasi ini dan gagal diunduh dari GitHub ({e}). "
                           "Unduh linkdeck-companion.apk dari halaman Releases lalu pasang di HP.") from e
    return dest


def install_error(text: str) -> str:
    if "INSTALL_FAILED_USER_RESTRICTED" in text:
        return ("HP menolak pemasangan lewat USB. Di Opsi pengembang nyalakan \"Pasang lewat USB\" "
                "(Xiaomi/POCO: perlu masuk akun Mi), atau ketuk Izinkan di layar HP, lalu coba lagi.")
    if "INSTALL_FAILED_INSUFFICIENT_STORAGE" in text:
        return "Penyimpanan HP penuh."
    m = re.search(r"(INSTALL_[A-Z_]+|Failure \[[^\]]+\])", text)
    return f"Pemasangan gagal: {m.group(1) if m else text.strip()[:200]}"


async def install(serial: str) -> dict:
    apk = await get_apk()
    c, out, err = await core.run("adb", "-s", serial, "install", "-r", str(apk), timeout=180)
    text = out + err
    if c or "Success" not in text:
        if re.search(r"UPDATE_INCOMPATIBLE|signatures do not match|VERSION_DOWNGRADE", text):
            # tanda tangan / versi berbeda dari pemasangan lama: copot lalu pasang ulang
            await core.run("adb", "-s", serial, "uninstall", PKG, timeout=60)
            c, out, err = await core.run("adb", "-s", serial, "install", str(apk), timeout=180)
            text = out + err
        if c or "Success" not in text:
            raise RuntimeError(install_error(text))
    granted = await grant(serial)
    await check_installed(serial)
    lk = LINKS.get(serial)
    if lk and lk.task and not lk.task.done():
        lk.task.cancel()
    LINKS.pop(serial, None)
    core.S.polled.pop("companion:" + serial, None)
    return {"granted": granted}


# ================================================================ tugas latar

async def loop() -> None:
    S = core.S
    while True:
        await asyncio.sleep(3)
        try:
            present = {d["serial"] for d in S.devices if d["state"] == "device"}
            for serial in list(LINKS):
                if serial not in present and not LINKS[serial].connected:
                    LINKS.pop(serial, None)
            if not S.settings.get("companion", True):
                for lk in LINKS.values():
                    if lk.task and not lk.task.done():
                        lk.task.cancel()
                continue
            for serial in present:
                lk = LINKS.get(serial)
                if lk and lk.task and not lk.task.done():
                    continue
                inst = INSTALLED.get(serial)
                if not inst or (not inst["installed"] and time.time() - inst["t"] > 60):
                    inst = await check_installed(serial)
                    await broadcast_status(serial)
                if not inst["installed"]:
                    continue
                # perbarui pendamping yang lebih lama dari versi bawaan aplikasi ini (sekali per sesi)
                if (bundled_apk() and serial not in UPDATED
                        and 0 < inst["code"] < version_code(core.VERSION)):
                    UPDATED.add(serial)
                    try:
                        await install(serial)
                        await core.log("Aplikasi pendamping di HP diperbarui.")
                    except Exception as e:
                        await core.log(f"Pembaruan aplikasi pendamping gagal: {e}", "warn")
                    continue
                wait = 20 if lk and lk.state == "off" else 8
                if lk and not core.due("companion:" + serial, wait):
                    continue
                core.S.polled["companion:" + serial] = time.time()
                if not lk:
                    lk = LINKS[serial] = Link(serial)
                lk.task = asyncio.create_task(lk.run())
        except Exception as e:
            print("companion:", e, flush=True)


# ================================================================ endpoint

async def h_status(req):
    S = core.S
    serials = [d["serial"] for d in S.devices if d["state"] == "device"]
    return core.ok(devices={s: status(s) for s in serials}, bundled=bool(bundled_apk()))


async def h_install(req):
    d = await req.json()
    serial = d.get("serial") or ""
    if serial not in {x["serial"] for x in core.S.devices if x["state"] == "device"}:
        return core.fail("HP Android belum tersambung.")
    try:
        r = await install(serial)
    except Exception as e:
        return core.fail(str(e))
    await broadcast_status(serial)
    return core.ok(**r, status=status(serial))


async def h_grant(req):
    d = await req.json()
    serial = d.get("serial") or ""
    granted = await grant(serial)
    lk = LINKS.get(serial)
    if lk:
        core.S.polled.pop("companion:" + serial, None)
    return core.ok(granted=granted)


async def h_act(req):
    d = await req.json()
    serial, key, op = d.get("serial") or "", str(d.get("key") or ""), d.get("op")
    if op not in ("reply", "action", "dismiss"):
        return core.fail("Perintah tidak dikenal.")
    lk = live(serial)
    if not lk or not lk.full:
        return core.fail("Aplikasi pendamping di HP belum tersambung.")
    msg = {"type": op, "key": key}
    if op in ("reply", "action"):
        msg["action"] = int(d.get("action", -1))
    if op == "reply":
        text = str(d.get("text") or "").strip()
        if not text:
            return core.fail(ERRORS["empty"])
        msg["text"] = text[:4000]
    if op == "reply":
        lk.replied[key] = time.time()
    try:
        r = await lk.request(msg)
    except asyncio.TimeoutError:
        return core.fail("HP tidak menjawab. Coba lagi.")
    except (ConnectionError, OSError) as e:
        return core.fail(str(e))
    if not r.get("ok"):
        err = str(r.get("error") or "")
        return core.fail(ERRORS.get(err, f"Gagal: {err}"))
    return core.ok()


async def on_startup(app):
    core.S.tasks.append(asyncio.create_task(loop()))


async def on_shutdown(app):
    for lk in LINKS.values():
        if lk.task and not lk.task.done():
            lk.task.cancel()
        if lk.port:
            await core.run("adb", "-s", lk.serial, "forward", "--remove", f"tcp:{lk.port}", timeout=4)


def register(router, core_module, app) -> None:
    global core
    core = core_module
    router.add_post("/api/companion/status", h_status)
    router.add_post("/api/companion/install", h_install)
    router.add_post("/api/companion/grant", h_grant)
    router.add_post("/api/notif/act", h_act)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
