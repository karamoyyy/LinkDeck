"""
Fitur tambahan LinkDeck (tahap 1):
  * Pengelola berkas HP (/sdcard)          * Pengelola aplikasi HP + dock favorit
  * Kontrol media HP                        * Pembaruan otomatis dari GitHub Releases
  * Laporan masalah sekali klik             * "Kirim ke HP" (menu Kirim ke Windows / CLI --send)
  * Pintasan global keyboard                * Catatan log terakhir (untuk laporan)

Didaftarkan oleh server.build_app() lewat register(router, core) — `core` adalah modul server.
"""
from __future__ import annotations

import asyncio
import io
import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections import deque
from pathlib import Path

from aiohttp import web

core = None                       # diisi register()
REPO = "karamoyyy/LinkDeck"
TOOL_JAR = "/data/local/tmp/linkdeck-tool.jar"
LOG_LINES: deque = deque(maxlen=3000)
PENDING: list[str] = []           # berkas "Kirim ke HP" yang menunggu HP tersambung


# ================================================================ utilitas

def q(path: str) -> str:
    """Kutip aman untuk shell Android."""
    return "'" + path.replace("'", "'\\''") + "'"


def safe_phone_path(p: str) -> str | None:
    p = "/" + p.strip().strip("/") if p.strip() else "/sdcard"
    p = re.sub(r"/+", "/", p)
    if ".." in p.split("/"):
        return None
    if not (p == "/sdcard" or p.startswith(("/sdcard/", "/storage/"))):
        return None
    return p


def vtuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


class _Tee(io.TextIOBase):
    """Salin semua keluaran print() ke penyangga log untuk laporan masalah."""

    def __init__(self, inner):
        self.inner = inner

    def write(self, s):
        if s and s.strip():
            for line in s.rstrip().splitlines():
                LOG_LINES.append(time.strftime("%H:%M:%S ") + line)
        if self.inner:
            try:
                return self.inner.write(s)
            except Exception:
                return len(s)
        return len(s)

    def flush(self):
        if self.inner:
            try:
                self.inner.flush()
            except Exception:
                pass


def ok(**kw):
    return core.ok(**kw)


def fail(msg: str, status: int = 400):
    return core.fail(msg, status)


async def adb(serial: str, *args: str, timeout: float = 30):
    return await core.run("adb", "-s", serial, *args, timeout=timeout)


# ================================================================ berkas HP

LS_RE = re.compile(r"^([dlcbps-][rwxsStT-]{9})\S*\s+\d+\s+\S+\s+\S+\s+(\d+)?\s*(\d{4}-\d\d-\d\d)\s+(\d\d:\d\d)\s+(.+)$")


def parse_ls(out: str) -> list[dict]:
    items = []
    for line in out.splitlines():
        m = LS_RE.match(line.strip())
        if not m:
            continue
        perm, size, date, tm, name = m.groups()
        target = None
        if perm[0] == "l" and " -> " in name:
            name, target = name.split(" -> ", 1)
        if name in (".", ".."):
            continue
        kind = "dir" if perm[0] == "d" or (perm[0] == "l" and target and "." not in Path(target).name) else "file"
        items.append({"name": name, "dir": kind == "dir", "size": int(size or 0), "time": f"{date} {tm}"})
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return items


async def h_files_list(req):
    d = await req.json()
    serial, path = d.get("serial", ""), safe_phone_path(d.get("path", "/sdcard"))
    if not serial:
        return fail("Sambungkan HP Android dulu.")
    if not path:
        return fail("Folder di luar penyimpanan HP tidak bisa dibuka.")
    c, out, err = await adb(serial, "shell", f"ls -la {q(path + '/')}", timeout=20)
    if c and not out.strip():
        return fail(f"Folder tidak bisa dibuka: {(err or out).strip()[:160]}")
    return ok(path=path, items=parse_ls(out))


async def h_files_op(req):
    d = await req.json()
    serial, op = d.get("serial", ""), d.get("op", "")
    path = safe_phone_path(d.get("path", ""))
    if not serial or not path or path in ("/sdcard", "/storage"):
        return fail("Lokasi tidak valid.")
    if op == "mkdir":
        cmd = f"mkdir -p {q(path)}"
    elif op == "delete":
        cmd = f"rm -rf {q(path)}"
    elif op == "rename":
        new = safe_phone_path(str(Path(path).parent / Path(d.get("name", "")).name))
        if not new or not Path(d.get("name", "")).name:
            return fail("Nama baru tidak valid.")
        cmd = f"mv {q(path)} {q(new)}"
    else:
        return fail("Aksi tidak dikenal.")
    c, out, err = await adb(serial, "shell", cmd, timeout=60)
    if c:
        return fail((err or out).strip()[:200] or "Gagal.")
    return ok()


async def h_files_pull(req):
    """Salin berkas/folder HP ke folder Downloads/LinkDeck di laptop."""
    d = await req.json()
    serial, path = d.get("serial", ""), safe_phone_path(d.get("path", ""))
    if not serial or not path:
        return fail("Lokasi tidak valid.")
    core.SAVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = core.unique_path(core.SAVE_DIR / core.safe_name(Path(path).name))
    c, out, err = await adb(serial, "pull", path, str(dest), timeout=1800)
    if c:
        return fail(f"Gagal mengunduh: {(err or out).strip()[:200]}")
    return ok(path=str(dest))


async def h_files_raw(req):
    """Isi berkas HP untuk pratinjau (gambar, teks) di LinkDeck."""
    serial, path = req.query.get("serial", ""), safe_phone_path(req.query.get("path", ""))
    if not serial or not path:
        return web.Response(status=400)
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    proc = await asyncio.create_subprocess_exec("adb", "-s", serial, "exec-out", f"cat {q(path)}",
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                                                creationflags=core.NOWIN)
    resp = web.StreamResponse(headers={"Content-Type": ctype, "Cache-Control": "no-store"})
    await resp.prepare(req)
    try:
        while chunk := await proc.stdout.read(1 << 16):
            await resp.write(chunk)
    finally:
        if proc.returncode is None:
            proc.kill()
    await resp.write_eof()
    return resp


# ================================================================ aplikasi HP

async def list_apps(serial: str, refresh: bool = False) -> list[dict]:
    if serial in core.S.apps and not refresh:
        return core.S.apps[serial]
    apps = []
    jar, ver = core.server_jar()
    if jar and ver:                                       # label aplikasi lewat server scrcpy bawaan
        c, _, _ = await adb(serial, "push", str(jar), TOOL_JAR, timeout=60)
        if not c:
            _, out, err = await adb(serial, "shell",
                                    f"CLASSPATH={TOOL_JAR} app_process / com.genymobile.scrcpy.Server {ver} "
                                    "list_apps=true log_level=info", timeout=60)
            apps = core.notif.parse_apps(out + "\n" + err)
    if not apps:
        _, out, _ = await adb(serial, "shell", "pm list packages -3", timeout=20)
        apps = [{"label": p.split(":", 1)[1].rsplit(".", 1)[-1].capitalize(), "pkg": p.split(":", 1)[1],
                 "system": False} for p in out.split() if p.startswith("package:")]
    core.S.apps[serial] = apps
    return apps


# ---------------------------------------------------------------- deteksi game di HP

GAME_HELPER = "/data/local/tmp/linkdeck-companion.apk"     # APK pendamping memuat kelas GameList (tidak perlu dipasang)
GAMES: dict[str, dict] = {}                                  # serial -> hasil deteksi terakhir
# bukan game walau kadang bertanda game: peluncur/penguat game bawaan HP dan toko
NOT_GAMES = ("com.google.android.play.games", "com.google.android.", "com.android.", "com.samsung.android.game.",
             "com.miui.", "com.xiaomi.gamecenter", "com.xiaomi.glgm", "com.coloros.", "com.oplus.", "com.heytap.",
             "com.vivo.", "com.iqoo.", "com.transsion.", "com.huawei.gameassistant", "com.hihonor.", "com.asus.",
             "id.linkdeck.")
# penerbit game terkenal (cadangan bila game tidak menandai dirinya sebagai game)
GAME_PREFIXES = (
    "com.mobile.legends", "com.moonton.", "com.tencent.ig", "com.tencent.tmgp.", "com.tencent.lolm", "com.pubg.",
    "com.vng.pubgmobile", "com.krafton.", "com.dts.freefire", "com.garena.game.", "com.miHoYo.", "com.mihoyo.",
    "com.HoYoverse.", "com.hoyoverse.", "com.supercell.", "com.roblox.", "com.mojang.", "com.activision.",
    "com.ea.game", "com.ea.games", "com.gameloft.", "com.king.", "com.netease.", "com.levelinfinite.",
    "com.proximabeta.", "com.riotgames.", "com.innersloth.", "com.kiloo.", "com.imangi.", "com.outfit7.",
    "com.playrix.", "com.rovio.", "com.miniclip.", "com.ubisoft.", "com.zynga.", "com.nexon.", "com.netmarble.",
    "com.ncsoft.", "com.square_enix.", "com.bandainamcoent.", "jp.konami.", "com.sega.", "com.YoStar", "com.yostar.",
    "com.playtika.", "com.halfbrick.", "com.lilithgame", "com.farlightgames.", "com.igg.", "com.nianticlabs.",
    "com.epicgames.", "com.blizzard.", "com.ngame.", "com.gravity.", "com.fingersoft.", "com.ketchapp",
    "com.voodoo.", "com.habby.", "com.tap4fun.", "com.funplus.", "com.moonactive.", "com.scopely.", "com.cygames.",
    "com.kakaogames.", "com.com2us.", "com.gamevil.", "com.devsisters.", "com.agaming.", "com.yoozoo.", "com.wb.goog.")


def game_by_name(pkg: str) -> bool:
    if pkg.startswith(GAME_PREFIXES):
        return True
    parts = pkg.lower().split(".")
    return any(p in ("game", "games") or p.endswith("game") and len(p) > 6 for p in parts[1:])


async def list_games(serial: str, refresh: bool = False) -> dict:
    """Game yang terpasang dan bisa dibuka, dengan label. Utamanya memakai tanda dari Android sendiri
    (appCategory="game" / isGame) dan tanda mesin game di APK (Unity, Unreal, Cocos, Godot)."""
    if serial in GAMES and not refresh:
        return GAMES[serial]
    apps = await list_apps(serial, refresh)
    found: dict[str, str] = {}
    note, method = "", "android"
    try:
        import companionlink
        apk = await companionlink.get_apk()
    except Exception as e:
        apk, method = None, "nama"
        note = f"Deteksi lengkap butuh APK pendamping ({e}). Sementara memakai nama paket."
    if apk:
        c, _, err = await adb(serial, "push", str(apk), GAME_HELPER, timeout=90)
        if c:
            method, note = "nama", f"APK pembantu tidak bisa dikirim ke HP: {err.strip()[:120]}"
        else:
            _, out, err = await adb(serial, "shell", f"CLASSPATH={GAME_HELPER} app_process / id.linkdeck.companion.GameList",
                                    timeout=90)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "GAME":
                    found[parts[1]] = parts[2] if len(parts) > 2 else "flag"
            if "DONE" not in out:
                bad = next((l for l in (out + "\n" + err).splitlines() if l.strip()), "tidak ada jawaban")
                method, note = "nama", f"Pembaca daftar game di HP gagal ({bad.strip()[:120]}). Sementara memakai nama paket."
    games = []
    for a in apps:
        pkg = a["pkg"]
        if pkg.startswith(NOT_GAMES):
            continue
        why = found.get(pkg) or ("nama" if game_by_name(pkg) else None)
        if why:
            games.append({"pkg": pkg, "label": a["label"], "why": why, "system": bool(a.get("system"))})
    games.sort(key=lambda g: (g["system"], g["label"].lower()))
    res = {"games": games, "method": method, "note": note, "t": time.time()}
    GAMES[serial] = res
    return res


async def h_games_list(req):
    d = await req.json()
    if not d.get("serial"):
        return fail("Sambungkan HP Android dulu.")
    return ok(**await list_games(d["serial"], bool(d.get("refresh"))))


async def h_apps_list(req):
    d = await req.json()
    if not d.get("serial"):
        return fail("Sambungkan HP Android dulu.")
    return ok(apps=await list_apps(d["serial"], bool(d.get("refresh"))))


async def h_apps_action(req):
    d = await req.json()
    serial, pkg, action = d.get("serial", ""), d.get("pkg", ""), d.get("action", "")
    if not serial or not re.match(r"^[\w.]+$", pkg):
        return fail("Aplikasi tidak valid.")
    if action == "stop":
        c, out, err = await adb(serial, "shell", "am", "force-stop", pkg)
        return fail(err.strip()) if c else ok(msg="Aplikasi dihentikan.")
    if action == "clear":
        _, out, err = await adb(serial, "shell", "pm", "clear", pkg, timeout=60)
        return ok(msg="Data aplikasi dihapus.") if "Success" in out else fail(f"Gagal: {(out + err).strip()[:160]}")
    if action == "uninstall":
        _, out, err = await adb(serial, "uninstall", pkg, timeout=120)
        if "Success" not in out:
            return fail(f"Gagal menghapus: {(out + err).strip()[:160]}")
        core.S.apps.pop(serial, None)
        GAMES.pop(serial, None)
        return ok(msg="Aplikasi dihapus dari HP.")
    if action == "backup":
        _, out, _ = await adb(serial, "shell", "pm", "path", pkg, timeout=20)
        paths = [l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("package:")]
        if not paths:
            return fail("Berkas APK tidak ditemukan.")
        label = next((a["label"] for a in core.S.apps.get(serial, []) if a["pkg"] == pkg), pkg)
        folder = core.SAVE_DIR / "APK"
        folder.mkdir(parents=True, exist_ok=True)
        if len(paths) == 1:
            dest = core.unique_path(folder / f"{core.safe_name(label)}.apk")
            c, o, e = await adb(serial, "pull", paths[0], str(dest), timeout=600)
        else:                                             # aplikasi terpecah (split APK): simpan semua bagian
            dest = core.unique_path(folder / core.safe_name(f"{label} ({pkg})"))
            dest.mkdir(parents=True)
            c, o, e = 0, "", ""
            for p in paths:
                c, o, e = await adb(serial, "pull", p, str(dest / Path(p).name), timeout=600)
                if c:
                    break
        if c:
            return fail(f"Gagal mencadangkan: {(e or o).strip()[:160]}")
        return ok(msg=f"APK disimpan di {dest}", path=str(dest))
    return fail("Aksi tidak dikenal.")


async def h_apps_install(req):
    reader = await req.multipart()
    serial, results = "", []
    tmp = core.SAVE_DIR / ".pasang"
    tmp.mkdir(parents=True, exist_ok=True)
    async for part in reader:
        if part.name == "serial":
            serial = (await part.text()).strip()
            continue
        if part.name != "file" or not part.filename:
            continue
        name = core.safe_name(part.filename)
        if not name.lower().endswith(".apk"):
            results.append({"name": name, "ok": False, "msg": "bukan berkas .apk"})
            continue
        f = tmp / name
        with f.open("wb") as fh:
            while chunk := await part.read_chunk(1 << 20):
                fh.write(chunk)
        if not serial:
            return fail("Sambungkan HP Android dulu.")
        _, out, err = await adb(serial, "install", "-r", str(f), timeout=900)
        msg = (out + err).strip()
        results.append({"name": name, "ok": "Success" in msg, "msg": "terpasang" if "Success" in msg else msg[-200:]})
        f.unlink(missing_ok=True)
    core.S.apps.pop(serial, None)
    GAMES.pop(serial, None)
    if not results:
        return fail("Tidak ada berkas APK.")
    return ok(results=results)


# ================================================================ kontrol media

MEDIA_KEYS = {"playpause": 85, "next": 87, "prev": 88, "volup": 24, "voldown": 25, "mute": 164}


def parse_media(out: str) -> dict | None:
    best = None
    for block in re.split(r"\n(?=\s{4}\S.*\(userId=\d+\))", out):
        pkg = re.search(r"\bpackage=([\w.]+)", block)
        st = re.search(r"state=PlaybackState \{state=(\d+)", block)
        desc = re.search(r"metadata: size=\d+, description=(.*)", block)
        if not pkg or not desc or desc.group(1).strip() in ("", "null", "null, null, null"):
            continue
        parts = [p.strip() for p in desc.group(1).split(", ")]
        item = {"pkg": pkg.group(1), "playing": bool(st and st.group(1) == "3"),
                "title": parts[0] if parts and parts[0] != "null" else "",
                "artist": parts[1] if len(parts) > 1 and parts[1] != "null" else ""}
        if item["playing"]:
            return item
        best = best or item
    return best


async def h_media(req):
    d = await req.json()
    serial, action = d.get("serial", ""), d.get("action")
    if not serial:
        return fail("Sambungkan HP Android dulu.")
    if action:
        if action not in MEDIA_KEYS:
            return fail("Aksi tidak dikenal.")
        await adb(serial, "shell", "input", "keyevent", str(MEDIA_KEYS[action]), timeout=10)
        await asyncio.sleep(0.4)
    _, out, _ = await adb(serial, "shell", "dumpsys media_session", timeout=15)
    return ok(media=parse_media(out))


# ================================================================ pembaruan otomatis

def install_kind() -> str:
    exe = Path(sys.executable).resolve()
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if os.environ.get("APPIMAGE"):
        return "appimage"
    if core.ROOT == Path("/usr/lib/linkdeck"):
        return "debian-app"
    if core.FROZEN and str(exe).startswith("/opt/linkdeck"):
        return "deb"
    return "source"


ASSET_PATTERNS = {"windows": r"-windows-setup\.exe$", "macos": r"-macos-arm64\.dmg$",
                  "appimage": r"-x86_64\.AppImage$", "deb": r"^linkdeck_[\d.]+_amd64\.deb$",
                  "debian-app": r"^linkdeck-debian_[\d.]+_all\.deb$"}


def _get(url: str, timeout: float = 15):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "LinkDeck"}), timeout=timeout)


def _fetch_release() -> dict:
    """Rilis terbaru. Utamanya lewat API GitHub; bila ditolak (mis. batas permintaan habis),
    pakai halaman rilis biasa di github.com."""
    try:
        with _get(f"https://api.github.com/repos/{REPO}/releases/latest") as r:
            return json.loads(r.read().decode())
    except Exception:
        pass
    with _get(f"https://github.com/{REPO}/releases/latest") as r:
        final = r.geturl()
    m = re.search(r"/releases/tag/([^/?#]+)", final)
    if not m:
        raise RuntimeError("belum ada rilis di GitHub")
    tag = m.group(1)
    with _get(f"https://github.com/{REPO}/releases/expanded_assets/{tag}") as r:
        html = r.read().decode(errors="replace")
    assets = []
    for href in sorted(set(re.findall(rf'href="(/{re.escape(REPO)}/releases/download/{re.escape(tag)}/[^"]+)"', html))):
        assets.append({"name": href.rsplit("/", 1)[1], "size": 0, "browser_download_url": "https://github.com" + href})
    return {"tag_name": tag, "html_url": final, "body": "", "assets": assets}


async def check_update() -> dict:
    rel = await asyncio.to_thread(_fetch_release)
    latest = rel.get("tag_name", "").lstrip("v")
    kind = install_kind()
    pat = ASSET_PATTERNS.get(kind)
    asset = next((a for a in rel.get("assets", []) if pat and re.search(pat, a["name"])), None)
    info = {"current": core.VERSION, "latest": latest, "newer": vtuple(latest) > vtuple(core.VERSION),
            "url": rel.get("html_url"), "notes": (rel.get("body") or "")[:1500], "kind": kind,
            "asset": {"name": asset["name"], "size": asset["size"], "url": asset["browser_download_url"]} if asset else None}
    core.S.update_info = info
    return info


async def h_update_check(req):
    try:
        return ok(update=await check_update())
    except Exception as e:
        return fail(f"Tidak bisa memeriksa pembaruan: {e}")


async def h_update_install(req):
    info = core.S.__dict__.get("update_info") or await check_update()
    if not info.get("newer"):
        return fail("Sudah versi terbaru.")
    asset = info.get("asset")
    if not asset:
        return ok(action="open", url=info["url"])
    folder = core.user_data_dir() / "pembaruan"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / asset["name"]

    def download():
        with _get(asset["url"], timeout=60) as r, open(dest.with_suffix(".part"), "wb") as fh:
            total, got, last = asset["size"] or int(r.headers.get("Content-Length") or 0) or 1, 0, 0
            while chunk := r.read(1 << 16):
                fh.write(chunk)
                got += len(chunk)
                pct = int(got * 100 / total)
                if pct >= last + 5:
                    last = pct
                    core.S.loop.call_soon_threadsafe(asyncio.ensure_future,
                                                     core.broadcast({"type": "update_progress", "pct": pct}))
        dest.with_suffix(".part").replace(dest)

    try:
        await asyncio.to_thread(download)
    except Exception as e:
        return fail(f"Unduhan gagal: {e}")
    kind = info["kind"]
    if kind == "windows":
        subprocess.Popen([str(dest), "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return ok(action="installing", msg="Pemasang berjalan. LinkDeck akan ditutup selama pemasangan; bila tidak terbuka lagi sendiri, buka dari menu Start.")
    if kind == "macos":
        subprocess.Popen(["open", str(dest)])
        return ok(action="manual", msg="Seret LinkDeck ke Applications untuk mengganti versi lama, lalu buka lagi.")
    if kind == "appimage":
        old = Path(os.environ["APPIMAGE"])
        dest.chmod(0o755)
        shutil.copy2(dest, old.with_suffix(".baru"))
        os.replace(old.with_suffix(".baru"), old)
        return ok(action="restart", msg="AppImage diperbarui. Tutup lalu buka lagi LinkDeck.")
    return ok(action="command", msg="Jalankan perintah ini di terminal, lalu buka lagi LinkDeck:",
              command=f"sudo apt install '{dest}'")


async def update_on_start():
    await asyncio.sleep(8)
    if not core.S.settings.get("auto_update", True):
        return
    try:
        info = await check_update()
        if info["newer"]:
            await core.broadcast({"type": "update", "update": info})
    except Exception as e:
        print("cek pembaruan:", e, flush=True)


# ================================================================ laporan masalah

def mask(text: str) -> str:
    text = re.sub(r"\b(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}\b", r"\1.x.x", text)          # IP
    text = re.sub(r"\b([A-Za-z0-9]{3})[A-Za-z0-9]{5,}(?=[\s:'\"])", r"\1•••", text)     # nomor seri
    return text


async def h_report(req):
    _, adbv, _ = await core.run("adb", "version", timeout=10)
    _, devs, _ = await core.run("adb", "devices", "-l", timeout=10)
    info = {
        "linkdeck": core.VERSION, "os": platform.platform(), "python": sys.version.split()[0],
        "frozen": core.FROZEN, "install": install_kind(), "tools": core.S.tools,
        "settings": core.S.settings, "sessions": core.public_sessions(),
        "debian": bool(core.S.debian), "clip_status": core.clip_status(),
        "devices": [{"model": d["model"], "transport": d["transport"], "state": d["state"]} for d in core.S.devices],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("info.json", mask(json.dumps(info, indent=1, ensure_ascii=False, default=str)))
        z.writestr("log-terakhir.txt", mask("\n".join(LOG_LINES)))
        z.writestr("adb.txt", mask(adbv + "\n" + devs))
        logf = core.user_data_dir() / "linkdeck.log"
        if logf.exists():
            z.writestr("linkdeck.log", mask(logf.read_text(errors="replace")[-400_000:]))
    core.SAVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = core.SAVE_DIR / time.strftime("linkdeck-laporan-%Y%m%d-%H%M%S.zip")
    dest.write_bytes(buf.getvalue())
    return ok(path=str(dest), issues=f"https://github.com/{REPO}/issues/new")


# ================================================================ "Kirim ke HP"

def sendto_link() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "SendTo" / "LinkDeck (HP Android).lnk"


def set_sendto(on: bool) -> str | None:
    """Tambah/hapus pintasan di menu klik kanan 'Kirim ke' Windows. Mengembalikan pesan galat bila gagal."""
    if sys.platform != "win32":
        return "Hanya tersedia di Windows."
    link = sendto_link()
    if not on:
        link.unlink(missing_ok=True)
        return None
    target = sys.executable if core.FROZEN else sys.executable
    args = "--send" if core.FROZEN else f'"{core.ROOT / "app.py"}" --send'
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
          f"$s.TargetPath='{target}';$s.Arguments='{args}';$s.IconLocation='{target},0';$s.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, creationflags=core.NOWIN, timeout=30)
    return None if r.returncode == 0 else (r.stderr or r.stdout).strip()[:200]


async def push_paths(paths: list[str]) -> dict:
    dev = next((d for d in core.S.devices if d["state"] == "device"), None)
    if not dev:
        PENDING.extend(paths)
        return {"queued": len(paths)}
    sent, failed = [], []
    await adb(dev["serial"], "shell", "mkdir", "-p", core.ANDROID_DROP)
    for p in paths:
        src = Path(p)
        if not src.exists():
            failed.append(src.name)
            continue
        c, _, _ = await adb(dev["serial"], "push", str(src), f"{core.ANDROID_DROP}/{core.safe_name(src.name)}", timeout=1800)
        (failed if c else sent).append(src.name)
    if sent:
        await core.log(f"Terkirim ke HP ({core.ANDROID_DROP}): {', '.join(sent)}")
    if failed:
        await core.log(f"Gagal dikirim ke HP: {', '.join(failed)}", "warn")
    return {"sent": sent, "failed": failed}


async def h_sendfiles(req):
    d = await req.json()
    paths = [str(p) for p in d.get("paths", []) if isinstance(p, str)][:200]
    if not paths:
        return fail("Tidak ada berkas.")
    return ok(**await push_paths(paths))


async def pending_loop():
    pend = os.environ.get("LINKDECK_PENDING")
    if pend:
        try:
            PENDING.extend(json.loads(pend))
        except ValueError:
            pass
    while True:
        await asyncio.sleep(3)
        if PENDING and any(d["state"] == "device" for d in core.S.devices):
            batch = PENDING[:]
            PENDING.clear()
            await push_paths(batch)


def write_session_file():
    f = core.user_data_dir() / "session.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"port": core.PORT, "token": core.TOKEN, "pid": os.getpid()}))
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass


# ================================================================ pintasan global

HOTKEYS = {"<ctrl>+<alt>+m": "mirror", "<ctrl>+<alt>+k": "keyboard"}
_hotkey_listener = None


async def hotkey_action(name: str):
    dev = next((d for d in core.S.devices if d["state"] == "device"), None)
    if not dev:
        await core.log("Pintasan: belum ada HP Android tersambung.", "warn")
        return
    mode = "input" if name == "keyboard" else None
    running = [sid for sid, s in core.S.sessions.items() if s["serial"] == dev["serial"]
               and ((s["mode"] == "input") if mode else s["mode"] in ("virtual", "mirror"))]
    if running:
        for sid in running:
            await core.stop_session(sid)
        return
    req = {"serial": dev["serial"], "mode": "input", "preset": dev["transport"]} if mode else \
        {**(core.load_json(core.user_data_dir() / "last-mirror.json", {}) or
            {"mode": "virtual", "width": 1920, "height": 1080, "dpi": 160, "audio": True}),
         "serial": dev["serial"], "preset": dev["transport"] if dev["transport"] in ("usb", "wifi", "bt") else "usb"}
    if req.get("mode") == "virtual" and not core.S.tools.get("virtual_display"):
        req["mode"] = "mirror"                       # scrcpy lama: pakai Cermin agar pintasan tetap berguna
    try:
        await core.start_session(req)
    except ValueError as e:
        await core.log(f"Pintasan: {e}", "warn")


def start_hotkeys() -> str | None:
    global _hotkey_listener
    stop_hotkeys()
    try:
        from pynput import keyboard
    except Exception as e:
        return f"Pintasan global tidak tersedia di sistem ini ({e})."
    loop = core.S.loop
    _hotkey_listener = keyboard.GlobalHotKeys({
        k: (lambda n=v: loop.call_soon_threadsafe(asyncio.ensure_future, hotkey_action(n)))
        for k, v in HOTKEYS.items()})
    _hotkey_listener.daemon = True
    _hotkey_listener.start()
    return None


def stop_hotkeys():
    global _hotkey_listener
    if _hotkey_listener:
        try:
            _hotkey_listener.stop()
        except Exception:
            pass
        _hotkey_listener = None


async def h_prefs(req):
    """Pengaturan yang punya efek di sistem (Kirim ke, pintasan global)."""
    d = await req.json()
    msg = None
    if "sendto" in d:
        msg = await asyncio.to_thread(set_sendto, bool(d["sendto"]))
        if not msg:
            core.S.settings["sendto"] = bool(d["sendto"])
    if "hotkeys" in d:
        core.S.settings["hotkeys"] = bool(d["hotkeys"])
        if d["hotkeys"]:
            msg = await asyncio.to_thread(start_hotkeys)
            if msg:
                core.S.settings["hotkeys"] = False
        else:
            stop_hotkeys()
    if "autostart" in d:
        import tray
        try:
            await asyncio.to_thread(tray.autostart_set, bool(d["autostart"]), core.FROZEN, core.ROOT)
            core.S.settings["autostart"] = bool(d["autostart"])
        except Exception as e:
            msg = f"Jalan otomatis tidak bisa diubah: {e}"
    for k in ("theme", "zoom", "privacy", "auto_privacy", "auto_update", "dock", "onboarded", "tray", "lang",
              "companion", "mic_target", "mic_clean", "mic_monitor", "wiz_what"):
        if k in d:
            if (k == "lang" and d[k] not in ("", "id", "en")) or (k == "wiz_what" and d[k] not in ("android", "debian", "both")):
                continue
            core.S.settings[k] = d[k]
    core.save_json(core.user_data_dir() / "settings.json", core.S.settings)
    return fail(msg) if msg else ok(settings=core.S.settings)


# ================================================================ pendaftaran

async def h_app_show(req):
    desk = getattr(core, "DESKTOP", None)
    if desk is None:
        return ok(shown=False)
    await asyncio.to_thread(desk.show)
    return ok(shown=True)


async def h_app_quit(req):
    desk = getattr(core, "DESKTOP", None)
    if desk is not None:
        core.S.loop.call_later(0.3, desk.quit)
    else:                                            # python server.py: hentikan proses dengan rapi
        import signal
        core.S.loop.call_later(0.3, os.kill, os.getpid(), signal.SIGINT)
    return ok()


def desktop_info() -> dict:
    import tray
    desk = getattr(core, "DESKTOP", None)
    info = desk.info() if desk else {"mode": None, "tray": False, "tray_menu": False}
    try:
        auto = tray.autostart_status()
    except Exception:
        auto = False
    return {**info, "autostart": auto, "autostart_ok": tray.autostart_supported(), "app": desk is not None}


async def h_app_info(req):
    return ok(**desktop_info())


async def on_startup(app):
    if core.S.settings.get("hotkeys"):
        err = await asyncio.to_thread(start_hotkeys)
        if err:
            print(err, flush=True)
    core.S.tasks += [asyncio.create_task(update_on_start()), asyncio.create_task(pending_loop())]
    write_session_file()


async def on_shutdown(app):
    stop_hotkeys()
    (core.user_data_dir() / "session.json").unlink(missing_ok=True)


def register(router, core_module, app) -> None:
    global core
    core = core_module
    if not isinstance(sys.stdout, _Tee):
        sys.stdout = _Tee(sys.stdout)
    r = router
    r.add_post("/api/phone/files", h_files_list)
    r.add_post("/api/phone/files/op", h_files_op)
    r.add_post("/api/phone/files/pull", h_files_pull)
    r.add_get("/api/phone/files/raw", h_files_raw)
    r.add_post("/api/phone/apps", h_apps_list)
    r.add_post("/api/phone/games", h_games_list)
    r.add_post("/api/phone/apps/action", h_apps_action)
    r.add_post("/api/phone/apps/install", h_apps_install)
    r.add_post("/api/media", h_media)
    r.add_post("/api/update/check", h_update_check)
    r.add_post("/api/update/install", h_update_install)
    r.add_post("/api/report", h_report)
    r.add_post("/api/sendfiles", h_sendfiles)
    r.add_post("/api/prefs", h_prefs)
    r.add_post("/api/app/show", h_app_show)
    r.add_post("/api/app/quit", h_app_quit)
    r.add_post("/api/app/info", h_app_info)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
