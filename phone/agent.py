#!/usr/bin/env python3
"""
LinkDeck agent — berjalan di dalam Debian 13 (di HP). Semua lalu lintas lewat TLS (wss://).

  /info   (tanpa PIN)  identitas agen untuk penemuan otomatis
  /ws     (PIN)        kontrol: clipboard, berkas, tautan, info, sinkron folder, input mouse/keyboard
  /vnc    (PIN)        terowongan ke server VNC lokal (VNC sendiri hanya mendengarkan di localhost)
  /term   (PIN)        terminal bash (pty)
  /audio  (PIN)        suara desktop Debian (PCM s16le) ke PC

Juga menyiarkan beacon UDP agar LinkDeck di PC menemukan HP tanpa mengetik IP.
Dijalankan oleh linkdeck-start. Butuh: python3-aiohttp, python3-xlib, xclip, openssl.
"""
import asyncio
import base64
import fcntl
import hashlib
import hmac
import json
import os
import pty
import shlex
import shutil
import signal
import socket
import ssl
import struct
import re  # noqa: F401
import subprocess
import termios
import time
from pathlib import Path

from aiohttp import WSMsgType, web

VERSION = "1.12.0"
LD = Path.home() / ".linkdeck"
TOKEN = os.environ.get("LINKDECK_TOKEN", "")
AGENT_ID = os.environ.get("LINKDECK_ID", "")
PORT = int(os.environ.get("LINKDECK_AGENT_PORT", "8765"))
VNC_PORT = int(os.environ.get("LINKDECK_VNC_PORT", "5901"))
BEACON_PORT = 47823
DISPLAY = os.environ.get("DISPLAY", ":1")
CERT = Path(os.environ.get("LINKDECK_CERT", LD / "cert.pem"))
KEY = Path(os.environ.get("LINKDECK_KEY", LD / "key.pem"))
INBOX = Path.home() / "Downloads" / "LinkDeck"
OUTBOX = Path.home() / "LinkDeck-Kirim"
SENT = OUTBOX / "terkirim"
SYNC = Path(os.environ.get("LINKDECK_SYNC_DIR", Path.home() / "LinkDeck-Sinkron"))
MAX_FILE = 48 * 1024 * 1024
ENV = {**os.environ, "DISPLAY": DISPLAY}
AUDIO_CMD = os.environ.get("LINKDECK_AUDIO_CMD", "")   # untuk pengujian / sistem audio khusus
# soket aplikasi pendamping Android; awalan "@" = namespace abstrak Linux (seperti LocalServerSocket Android)
COMPANION_SOCK = os.environ.get("LINKDECK_COMPANION_SOCK", "@linkdeck_companion")
POWER_DIR = Path(os.environ.get("LINKDECK_POWER_DIR", "/sys/class/power_supply"))
TERMUX_BATTERY = ("termux-battery-status", "/data/data/com.termux/files/usr/bin/termux-battery-status")

clients: set = set()
last_clip = None
recent_set: dict = {}   # teks yang baru diisikan dari PC -> waktu; mencegah gema balik ke PC


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def fingerprint() -> str:
    try:
        der = ssl.PEM_cert_to_DER_cert(CERT.read_text())
        return hashlib.sha256(der).hexdigest()
    except Exception:
        return ""


FP = fingerprint()


def authorized(req) -> bool:
    return bool(TOKEN) and hmac.compare_digest(req.query.get("token", ""), TOKEN)


# ------------------------------------------------------------------ clipboard

def x_displays() -> list[str]:
    """Semua layar X yang aktif: layar LinkDeck (:1) DAN layar XFCE yang tampil di HP (mis. Termux:X11 :0)."""
    found = {DISPLAY}
    for d in ("/tmp/.X11-unix", os.environ.get("PREFIX", "") + "/tmp/.X11-unix"):
        try:
            for name in os.listdir(d):
                if name.startswith("X") and name[1:].isdigit():
                    found.add(":" + name[1:])
        except OSError:
            pass
    return sorted(found, key=lambda x: int(x[1:].split(".")[0]) if x[1:].split(".")[0].isdigit() else 99)


def clip_get(display: str | None = None):
    env = {**ENV, "DISPLAY": display or DISPLAY}
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard", "-o"], env=env,
                           capture_output=True, timeout=2)
        return r.stdout.decode(errors="replace") if r.returncode == 0 else None
    except Exception:
        return None


def clip_set(text: str, display: str | None = None) -> None:
    env = {**ENV, "DISPLAY": display or DISPLAY}
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard", "-i"], env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        p.communicate(text.encode(), timeout=3)
    except Exception as e:
        log("clip_set:", e)


disp_clip: dict[str, str | None] = {}     # isi clipboard terakhir per layar X


async def clip_set_all(text: str, skip: str | None = None) -> None:
    """Isi clipboard di semua layar X (kecuali asal salinan), lalu tunggu sampai benar-benar terpasang."""
    for d in x_displays():
        disp_rich[d] = None
        if d == skip:
            disp_clip[d] = text
            continue
        await asyncio.to_thread(clip_set, text, d)
        for _ in range(20):
            if await asyncio.to_thread(clip_get, d) == text:
                break
            await asyncio.sleep(0.05)
        disp_clip[d] = text


# ------------------------------------------------------------------ berkas

def safe_name(name: str) -> str:
    name = Path(name or "berkas").name.strip(" .")
    return "".join(c if c.isalnum() or c in "._-() []" else "_" for c in name)[:120] or "berkas"


def safe_rel(rel: str) -> Path | None:
    p = (SYNC / rel).resolve()
    return p if str(p).startswith(str(SYNC.resolve()) + os.sep) else None


def unique(p: Path) -> Path:
    i = 2
    base = p.stem
    while p.exists():
        p = p.with_name(f"{base} ({i}){p.suffix}")
        i += 1
    return p


def sync_manifest() -> dict:
    SYNC.mkdir(parents=True, exist_ok=True)
    out = {}
    for f in SYNC.rglob("*"):
        if f.is_file() and not f.name.startswith(".") and f.stat().st_size <= MAX_FILE:
            st = f.stat()
            out[f.relative_to(SYNC).as_posix()] = [st.st_size, int(st.st_mtime)]
    return out


# ------------------------------------------------------------------ tahap 2: berkas, apt, sistem (permintaan ber-rid)

HOME = Path.home().resolve()
PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+.\-]{0,100}$")
apt_job: dict = {"proc": None}
_cpu_prev: dict = {}


def within_home(p: Path) -> bool:
    try:
        p = p.resolve()
    except OSError:
        return False
    return p == HOME or str(p).startswith(str(HOME) + os.sep)


def fs_path(raw: str) -> Path:
    raw = (raw or "~").strip()
    p = Path(os.path.expanduser(raw))
    return p if p.is_absolute() else HOME / p


def fs_list(path: str) -> dict:
    p = fs_path(path).resolve()
    if not p.is_dir():
        raise ValueError("Folder tidak ditemukan.")
    items = []
    with os.scandir(p) as it:
        for e in it:
            try:
                st = e.stat(follow_symlinks=True)
                is_dir = e.is_dir(follow_symlinks=True)
            except OSError:
                st, is_dir = None, False
            items.append({"name": e.name, "dir": is_dir, "link": e.is_symlink(), "hidden": e.name.startswith("."),
                          "size": (st.st_size if st and not is_dir else 0),
                          "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)) if st else ""})
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return {"path": str(p), "home": str(HOME), "writable": within_home(p), "items": items[:3000]}


def fs_op(op: str, path: str, name: str = "") -> None:
    p = fs_path(path)
    if op == "mkdir":
        target = p
    else:
        target = p
        if not target.exists() and not target.is_symlink():
            raise ValueError("Berkas tidak ditemukan.")
    if not within_home(target.parent if op != "mkdir" else target) or target.resolve() == HOME:
        raise ValueError("Hanya bisa mengubah isi folder rumah (~).")
    if op == "mkdir":
        target.mkdir(parents=True, exist_ok=False)
    elif op == "rename":
        new = target.with_name(safe_name(name))
        if new.exists():
            raise ValueError("Nama itu sudah dipakai.")
        target.rename(new)
    elif op == "delete":
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    else:
        raise ValueError("Aksi tidak dikenal.")


def fs_get(path: str) -> dict:
    p = fs_path(path).resolve()
    if not p.is_file():
        raise ValueError("Bukan berkas.")
    if p.stat().st_size > MAX_FILE:
        raise ValueError(f"Berkas lebih dari {MAX_FILE // 1048576} MB; pakai folder sinkron atau ~/LinkDeck-Kirim.")
    return {"name": p.name, "data": base64.b64encode(p.read_bytes()).decode()}


def fs_put(folder: str, name: str, data: str) -> str:
    d = fs_path(folder).resolve()
    if not d.is_dir() or not within_home(d):
        raise ValueError("Unggah hanya ke folder di dalam folder rumah (~).")
    dest = unique(d / safe_name(name))
    tmp = dest.with_name(f".{dest.name}.part")
    tmp.write_bytes(base64.b64decode(data))
    tmp.replace(dest)
    return dest.name


def apt_search(q: str) -> list:
    q = q.strip()[:60]
    if not q:
        return []
    r = subprocess.run(["apt-cache", "search", "--names-only", "--", q], capture_output=True, text=True, timeout=30)
    rows = []
    for line in r.stdout.splitlines():
        if " - " in line:
            pkg, desc = line.split(" - ", 1)
            rows.append({"pkg": pkg.strip(), "desc": desc.strip()})
    ql = q.lower()
    rows.sort(key=lambda x: (x["pkg"] != ql, not x["pkg"].startswith(ql), len(x["pkg"])))
    rows = rows[:60]
    return apt_mark_installed(rows)


def apt_mark_installed(rows: list) -> list:
    if not rows:
        return rows
    r = subprocess.run(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Status}\n", *[x["pkg"] for x in rows]],
                       capture_output=True, text=True, timeout=20)
    inst = {l.split("\t")[0] for l in r.stdout.splitlines() if l.endswith("\tinstalled")}
    for x in rows:
        x["installed"] = x["pkg"] in inst
    return rows


def apt_info(pkgs: list) -> list:
    pkgs = [p for p in pkgs if PKG_RE.match(p)][:40]
    if not pkgs:
        return []
    r = subprocess.run(["apt-cache", "show", "--no-all-versions", *pkgs], capture_output=True, text=True, timeout=30)
    desc = {}
    cur = None
    for line in r.stdout.splitlines():
        if line.startswith("Package: "):
            cur = line[9:].strip()
        elif line.startswith(("Description: ", "Description-en: ")) and cur and cur not in desc:
            desc[cur] = line.split(": ", 1)[1].strip()
    rows = [{"pkg": p, "desc": desc[p]} for p in pkgs if p in desc]
    return apt_mark_installed(rows)


async def apt_run(action: str, pkg: str, password: str) -> None:
    """Jalankan apt-get, siarkan keluarannya baris demi baris (apt_log) lalu apt_done."""
    if action == "update":
        cmd = ["apt-get", "update"]
    else:
        cmd = ["apt-get", "install" if action == "install" else "remove", "-y", pkg]
    root = os.geteuid() == 0
    if not root:
        if not shutil.which("sudo"):
            await send_all({"type": "apt_done", "ok": False, "action": action, "pkg": pkg,
                            "msg": "sudo belum terpasang. Masuk sebagai root lalu jalankan: apt install sudo"})
            return
        cmd = ["sudo", "-S", "-p", "", "--"] + cmd
    env = {**ENV, "DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C.UTF-8"}
    proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT, env=env)
    apt_job["proc"] = proc
    try:
        if not root:
            proc.stdin.write((password or "").encode() + b"\n")
            await proc.stdin.drain()
        proc.stdin.close()
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                await send_all({"type": "apt_log", "line": line[:400]})
        code = await proc.wait()
    finally:
        apt_job["proc"] = None
    msg = None
    if code != 0 and not root:
        msg = "Gagal. Bila sandi salah, coba lagi; bila pengguna ini tidak boleh memakai sudo, masuk sebagai root."
    await send_all({"type": "apt_done", "ok": code == 0, "code": code, "action": action, "pkg": pkg, "msg": msg})


def cpu_sample() -> tuple | None:
    try:
        f = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        v = [int(x) for x in f]
        return sum(v), v[3] + (v[4] if len(v) > 4 else 0)
    except Exception:
        return None


def proc_table() -> dict:
    out = {}
    tick = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    for e in os.scandir("/proc"):
        if not e.name.isdigit():
            continue
        try:
            stat = Path(f"/proc/{e.name}/stat").read_text()
            name = stat[stat.index("(") + 1:stat.rindex(")")]
            parts = stat[stat.rindex(")") + 2:].split()
            cpu = (int(parts[11]) + int(parts[12])) / tick
            rss = int(parts[21]) * os.sysconf("SC_PAGE_SIZE")
            uid = os.stat(f"/proc/{e.name}").st_uid
            try:
                cmd = Path(f"/proc/{e.name}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
            except OSError:
                cmd = ""
            out[int(e.name)] = {"name": name, "cpu_t": cpu, "rss": rss, "uid": uid, "cmd": cmd[:200]}
        except Exception:
            continue
    return out


def mem_info() -> dict:
    info = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
    except Exception:
        return {}
    return {"total": info.get("MemTotal"), "avail": info.get("MemAvailable"),
            "swap_total": info.get("SwapTotal"), "swap_free": info.get("SwapFree")}


async def sys_info() -> dict:
    import pwd
    c1, p1, t1 = cpu_sample(), await asyncio.to_thread(proc_table), time.monotonic()
    await asyncio.sleep(0.6)
    c2, p2, t2 = cpu_sample(), await asyncio.to_thread(proc_table), time.monotonic()
    cpu = None
    if c1 and c2 and c2[0] > c1[0]:
        cpu = round(100 * (1 - (c2[1] - c1[1]) / (c2[0] - c1[0])), 1)
    ncpu = os.cpu_count() or 1
    mem = mem_info()
    users: dict = {}
    procs = []
    for pid, p in p2.items():
        prev = p1.get(pid)
        pc = round(100 * (p["cpu_t"] - prev["cpu_t"]) / max(0.01, t2 - t1) / ncpu, 1) if prev else 0.0
        if p["uid"] not in users:
            try:
                users[p["uid"]] = pwd.getpwuid(p["uid"]).pw_name
            except KeyError:
                users[p["uid"]] = str(p["uid"])
        procs.append({"pid": pid, "name": p["name"], "cmd": p["cmd"], "cpu": max(0.0, pc),
                      "mem": p["rss"], "user": users[p["uid"]], "mine": p["uid"] == os.getuid()})
    procs.sort(key=lambda x: (-x["cpu"], -x["mem"]))
    disks = []
    for label, path in (("Folder rumah", str(HOME)), ("Sistem (/)", "/")):
        try:
            du = shutil.disk_usage(path)
            disks.append({"label": label, "path": path, "total": du.total, "used": du.used, "free": du.free})
        except OSError:
            pass
    try:
        up = float(Path("/proc/uptime").read_text().split()[0])
    except Exception:
        up = None
    try:
        load = list(os.getloadavg())
    except OSError:
        load = None
    return {"cpu": cpu, "cores": ncpu, "mem": mem, "disks": disks, "uptime": up, "load": load,
            "procs": procs[:150], "count": len(procs), "me": users.get(os.getuid()) or str(os.getuid())}


def proc_kill(pid: int, force: bool) -> None:
    if pid in (os.getpid(), os.getppid(), 1) or pid <= 0:
        raise ValueError("Proses ini tidak boleh dihentikan dari LinkDeck.")
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        raise ValueError("Proses sudah tidak ada.")
    except PermissionError:
        raise ValueError("Tidak diizinkan: proses milik pengguna lain.")


async def handle_req(ws, d: dict) -> None:
    """Permintaan ber-rid dari PC; jawabannya {"type": "reply", "rid": ..., "ok": ...}."""
    rid, t = d.get("rid"), d.get("type")
    res: dict = {}
    try:
        if t == "fs_list":
            res = await asyncio.to_thread(fs_list, d.get("path", "~"))
        elif t == "fs_op":
            await asyncio.to_thread(fs_op, d.get("op", ""), d.get("path", ""), d.get("name", ""))
        elif t == "fs_get":
            res = await asyncio.to_thread(fs_get, d.get("path", ""))
        elif t == "fs_put":
            res = {"name": await asyncio.to_thread(fs_put, d.get("dir", ""), d.get("name", ""), d.get("data", ""))}
        elif t == "apt_search":
            res = {"items": await asyncio.to_thread(apt_search, str(d.get("q", "")))}
        elif t == "apt_info":
            res = {"items": await asyncio.to_thread(apt_info, list(d.get("pkgs", [])))}
        elif t == "apt_run":
            action, pkg = d.get("action"), str(d.get("pkg", ""))
            if action not in ("install", "remove", "update") or (action != "update" and not PKG_RE.match(pkg)):
                raise ValueError("Paket tidak valid.")
            if apt_job["proc"]:
                raise ValueError("Masih ada pemasangan lain yang berjalan.")
            asyncio.create_task(apt_run(action, pkg, str(d.get("password", ""))))
            res = {"root": os.geteuid() == 0}
        elif t == "sys_info":
            res = await sys_info()
        elif t == "proc_kill":
            await asyncio.to_thread(proc_kill, int(d.get("pid", 0)), bool(d.get("force")))
        else:
            raise ValueError("Permintaan tidak dikenal.")
        await ws.send_str(json.dumps({"type": "reply", "rid": rid, "ok": True, **res}))
    except Exception as e:
        msg = str(e) if isinstance(e, (ValueError, OSError)) else f"{e.__class__.__name__}: {e}"
        await ws.send_str(json.dumps({"type": "reply", "rid": rid, "ok": False, "error": msg[:300]}))


# ------------------------------------------------------------------ tahap 2: clipboard gambar & berkas

RICH_MAX = 20 * 1024 * 1024          # gambar maks. 20 MB
FILES_MAX = 20                       # berkas per salinan
CLIP_IN = INBOX / "Clipboard"
disp_rich: dict[str, str | None] = {}   # sidik terakhir isi gambar/berkas per layar
rich_recent: dict[str, float] = {}      # sidik yang baru diisikan dari PC
rich_batches: dict[str, dict] = {}


def xclip_targets(display: str) -> list[str]:
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                           env={**ENV, "DISPLAY": display}, capture_output=True, timeout=2)
        return r.stdout.decode(errors="replace").split() if r.returncode == 0 else []
    except Exception:
        return []


def xclip_read(display: str, target: str) -> bytes | None:
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard", "-t", target, "-o"],
                           env={**ENV, "DISPLAY": display}, capture_output=True, timeout=5)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def xclip_write(display: str, target: str, data: bytes) -> None:
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard", "-t", target, "-i"],
                             env={**ENV, "DISPLAY": display}, stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p.communicate(data, timeout=5)
    except Exception as e:
        log("xclip_write:", e)


def uris_to_paths(text: str) -> list[Path]:
    from urllib.parse import unquote, urlparse
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("file://"):
            p = Path(unquote(urlparse(line).path))
            if p.is_file():
                out.append(p)
    return out[:FILES_MAX]


UNKNOWN = "?"                          # pembacaan gagal sesaat: jangan ubah status
TEXT_TYPES = ("UTF8_STRING", "STRING", "TEXT", "text/plain", "text/plain;charset=utf-8", "COMPOUND_TEXT")


def read_rich(display: str):
    """('image', png) / ('files', [Path]) bila clipboard berisi gambar/berkas, None bila tidak, UNKNOWN bila gagal baca."""
    targets = xclip_targets(display)
    if not targets:
        return UNKNOWN
    if "x-special/gnome-copied-files" in targets or "text/uri-list" in targets:
        raw = xclip_read(display, "x-special/gnome-copied-files" if "x-special/gnome-copied-files" in targets
                         else "text/uri-list")
        if raw is None:
            return UNKNOWN
        paths = uris_to_paths(raw.decode(errors="replace"))
        if paths:
            return "files", paths
    if "image/png" in targets:
        png = xclip_read(display, "image/png")
        if png is None:
            return UNKNOWN
        if png and len(png) <= RICH_MAX:
            return "image", png
    return None


def rich_sig(kind: str, val) -> str:
    """Sidik isi: gambar = hash PNG; berkas = nama + ukuran (jalurnya beda di tiap perangkat)."""
    if kind == "image":
        return "img:" + hashlib.sha1(val).hexdigest()
    keys = sorted(f"{Path(p).name}\t{Path(p).stat().st_size if Path(p).exists() else 0}" for p in val)
    return "files:" + hashlib.sha1("\n".join(keys).encode()).hexdigest()


def set_rich_all(kind: str, val, skip: str | None = None, from_pc: bool = False) -> str:
    if kind == "image":
        sig, target, data = rich_sig("image", val), "image/png", val
    else:
        sig = rich_sig("files", val)
        target = "x-special/gnome-copied-files"
        data = ("copy\n" + "\n".join(Path(p).resolve().as_uri() for p in val)).encode()
    if from_pc:
        rich_recent[sig] = time.time()             # isi kiriman PC: pantulannya jangan dikirim balik
    for disp in x_displays():
        disp_rich[disp] = sig
        if disp != skip:
            xclip_write(disp, target, data)
            for _ in range(20):                    # tunggu sampai xclip benar-benar memegang clipboard
                if target in xclip_targets(disp):
                    break
                time.sleep(0.05)
    return sig


RICH_TYPES = ("image/png", "x-special/gnome-copied-files", "text/uri-list")
rich_on = {"v": False}                  # dinyalakan oleh LinkDeck PC 1.10+ (sakelar "Gambar & berkas"); PC lama tidak mengenalnya


async def rich_scan(display: str) -> None:
    """Clipboard layar ini (mungkin) berisi gambar/berkas: kirim ke PC bila baru."""
    first = display not in disp_rich           # isi yang sudah ada saat mulai: catat, jangan kirim
    got = await asyncio.to_thread(read_rich, display)
    if got == UNKNOWN:
        return
    if not got:
        disp_rich[display] = None              # mis. tautan web (text/uri-list) -> diproses sebagai teks
        return
    kind, val = got
    sig = rich_sig(kind, val)
    if first or sig == disp_rich.get(display):
        disp_rich[display] = sig
        return
    global last_clip
    disp_rich[display] = sig
    disp_clip[display] = None                  # teks sama yang disalin berikutnya tetap terdeteksi
    last_clip = None
    if time.time() - rich_recent.get(sig, 0) < 3:
        return                                 # pantulan isi yang baru dikirim PC
    if kind == "image":
        await send_all({"type": "clip_image", "png": base64.b64encode(val).decode(), "display": display})
    else:
        files = [p for p in val if p.stat().st_size <= MAX_FILE]
        batch = hashlib.sha1(sig.encode()).hexdigest()[:10]
        for i, p in enumerate(files):
            await send_all({"type": "clip_files", "batch": batch, "index": i, "total": len(files), "name": p.name,
                            "data": base64.b64encode(p.read_bytes()).decode(), "display": display})
        skipped = len(val) - len(files)
        if skipped:
            await send_all({"type": "error",
                            "msg": f"{skipped} berkas lebih dari {MAX_FILE // 1048576} MB tidak ikut disalin."})
    await asyncio.to_thread(set_rich_all, kind, val, display)   # samakan ke layar X lain


async def rich_from_pc(d: dict) -> None:
    global last_clip
    last_clip = None
    for disp in list(disp_clip):
        disp_clip[disp] = None
    if d.get("type") == "clip_image":
        png = base64.b64decode(d.get("png", ""))
        if png:
            await asyncio.to_thread(set_rich_all, "image", png, None, True)
        return
    key = str(d.get("batch", "x"))[:16]
    b = rich_batches.setdefault(key, {"files": [], "t": time.time(),
                                      "dir": CLIP_IN / (time.strftime("%Y%m%d-%H%M%S-") + safe_name(key))})
    folder = b["dir"]
    folder.mkdir(parents=True, exist_ok=True)
    dest = unique(folder / safe_name(d.get("name", "berkas")))
    dest.write_bytes(base64.b64decode(d.get("data", "")))
    b["files"].append(dest)
    if int(d.get("index", 0)) + 1 >= int(d.get("total", 1)):
        rich_batches.pop(key, None)
        await asyncio.to_thread(set_rich_all, "files", b["files"], None, True)
        await send_all({"type": "saved", "name": f"{len(b['files'])} berkas dari clipboard ({folder})"})
    for k in [k for k, v in rich_batches.items() if time.time() - v["t"] > 300]:
        rich_batches.pop(k, None)


# ------------------------------------------------------------------ input (mouse & keyboard dari PC)

class Injector:
    """Menyuntikkan gerakan mouse dan tombol ke sesi X lewat ekstensi XTEST."""

    def __init__(self):
        from Xlib import X, XK, display
        from Xlib.ext import xtest
        self.X, self.XK, self.xtest = X, XK, xtest
        self.d = display.Display(DISPLAY)
        self.root = self.d.screen().root
        self.down_keys: set[int] = set()
        self.down_btns: set[int] = set()

    def size(self):
        g = self.root.get_geometry()
        return g.width, g.height

    def move(self, dx: int, dy: int):
        p = self.root.query_pointer()
        w, h = self.size()
        x = max(0, min(w - 1, p.root_x + dx))
        y = max(0, min(h - 1, p.root_y + dy))
        self.xtest.fake_input(self.d, self.X.MotionNotify, x=x, y=y)
        self.d.sync()
        return x, y, w, h

    def warp(self, fx: float, fy: float):
        w, h = self.size()
        self.xtest.fake_input(self.d, self.X.MotionNotify, x=int(fx * (w - 1)), y=int(fy * (h - 1)))
        self.d.sync()

    def button(self, b: int, down: bool):
        self.xtest.fake_input(self.d, self.X.ButtonPress if down else self.X.ButtonRelease, b)
        (self.down_btns.add if down else self.down_btns.discard)(b)
        self.d.sync()

    def scroll(self, dx: int, dy: int):
        for b, n in ((4 if dy > 0 else 5, abs(dy)), (6 if dx < 0 else 7, abs(dx))):
            for _ in range(min(int(n), 20)):
                self.xtest.fake_input(self.d, self.X.ButtonPress, b)
                self.xtest.fake_input(self.d, self.X.ButtonRelease, b)
        self.d.sync()

    def key(self, sym, down: bool):
        if isinstance(sym, str):
            ks = self.XK.string_to_keysym(sym)
            if not ks and len(sym) == 1:
                ks = ord(sym) if ord(sym) < 0x100 else 0x1000000 + ord(sym)
        else:
            ks = int(sym)
        kc = self.d.keysym_to_keycode(ks) if ks else 0
        if not kc:
            return
        self.xtest.fake_input(self.d, self.X.KeyPress if down else self.X.KeyRelease, kc)
        (self.down_keys.add if down else self.down_keys.discard)(kc)
        self.d.sync()

    def release_all(self):
        for kc in list(self.down_keys):
            self.xtest.fake_input(self.d, self.X.KeyRelease, kc)
        for b in list(self.down_btns):
            self.xtest.fake_input(self.d, self.X.ButtonRelease, b)
        self.down_keys.clear()
        self.down_btns.clear()
        self.d.sync()


injector = None
kvm_edge = "left"   # tepi layar Debian untuk kembali ke PC


def get_injector():
    global injector
    if injector is None:
        injector = Injector()
    return injector


def screen_size():
    try:
        return list(get_injector().size())
    except Exception:
        return None


def set_resolution(size: str) -> tuple[bool, str]:
    """Ubah ukuran desktop Debian (Xtigervnc mendukung RandR)."""
    import re
    if not re.match(r"^\d{3,4}x\d{3,4}$", size):
        return False, "Format resolusi harus LEBARxTINGGI"
    if not shutil.which("xrandr"):
        return False, "xrandr belum terpasang di Debian (paket x11-xserver-utils)"
    r = subprocess.run(["xrandr", "-s", size], env=ENV, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        r = subprocess.run(["xrandr", "--fb", size], env=ENV, capture_output=True, text=True, timeout=10)
    return r.returncode == 0, (r.stderr or "").strip()[:200]


# ------------------------------------------------------------------ kontrol utama /ws

async def send_all(obj: dict) -> None:
    data = json.dumps(obj)
    for ws in list(clients):
        try:
            await ws.send_str(data)
        except Exception:
            clients.discard(ws)


async def handle(ws, d: dict) -> None:
    global last_clip, kvm_edge
    t = d.get("type")
    if t == "in":
        try:
            inj = get_injector()
        except Exception as e:
            await ws.send_str(json.dumps({"type": "error", "msg": f"Input tidak tersedia: {e}"}))
            return
        k = d.get("k")
        if k == "move":
            x, y, w, h = inj.move(int(d.get("dx", 0)), int(d.get("dy", 0)))
            back = ((kvm_edge == "left" and x <= 0 and d.get("dx", 0) < 0) or
                    (kvm_edge == "right" and x >= w - 1 and d.get("dx", 0) > 0))
            if back:
                inj.release_all()
                await ws.send_str(json.dumps({"type": "kvm_release", "fy": y / max(1, h - 1)}))
        elif k == "enter":
            kvm_edge = d.get("edge", "left")
            inj.warp(0.0 if kvm_edge == "left" else 1.0, float(d.get("fy", 0.5)))
        elif k == "btn":
            inj.button(int(d["b"]), bool(d["down"]))
        elif k == "scroll":
            inj.scroll(int(d.get("dx", 0)), int(d.get("dy", 0)))
        elif k == "key":
            inj.key(d["sym"], bool(d["down"]))
        elif k == "reset":
            inj.release_all()
    elif t == "resolution":
        size = str(d.get("size", ""))
        ok, msg = await asyncio.to_thread(set_resolution, size)
        await ws.send_str(json.dumps({"type": "resolution", "ok": ok, "size": size, "msg": msg,
                                      "screen": screen_size()}))
    elif t == "clip_check":                         # untuk tombol Uji: isi clipboard tiap layar X
        res = {d: await asyncio.to_thread(clip_get, d) for d in x_displays()}
        await ws.send_str(json.dumps({"type": "clip_check", "displays": res, "xclip": bool(shutil.which("xclip"))}))
    elif t == "clip":
        text = d.get("text", "")
        if text and text != last_clip:
            last_clip = text
            recent_set[text] = time.time()
            await clip_set_all(text)
    elif t in ("clip_image", "clip_files"):
        if rich_on["v"]:
            await rich_from_pc(d)
    elif t == "rich":
        rich_on["v"] = bool(d.get("on", True))
    elif t == "file":
        INBOX.mkdir(parents=True, exist_ok=True)
        dest = unique(INBOX / safe_name(d.get("name", "berkas")))
        dest.write_bytes(base64.b64decode(d.get("data", "")))
        await send_all({"type": "saved", "name": dest.name})
    elif t == "open":
        url = d.get("url", "")
        if url.startswith(("http://", "https://")):
            subprocess.Popen(["xdg-open", url], env=ENV, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    elif t == "sync_list":
        await ws.send_str(json.dumps({"type": "sync_list", "files": await asyncio.to_thread(sync_manifest),
                                      "dir": str(SYNC)}))
    elif t == "sync_get":
        p = safe_rel(d.get("path", ""))
        if p and p.is_file():
            await ws.send_str(json.dumps({"type": "sync_file", "path": d["path"],
                                          "mtime": int(p.stat().st_mtime),
                                          "data": base64.b64encode(p.read_bytes()).decode()}))
    elif t == "sync_put":
        p = safe_rel(d.get("path", ""))
        if p:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(f".{p.name}.part")
            tmp.write_bytes(base64.b64decode(d.get("data", "")))
            os.utime(tmp, (time.time(), int(d.get("mtime", time.time()))))
            tmp.replace(p)
    elif t == "sync_del":
        p = safe_rel(d.get("path", ""))
        if p and p.is_file():
            p.unlink()


async def ws_handler(req: web.Request):
    if not authorized(req):
        return web.Response(status=403, text="PIN salah")
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=MAX_FILE * 2)
    await ws.prepare(req)
    clients.add(ws)
    log("PC tersambung dari", req.remote)
    size = None
    try:
        size = get_injector().size()
    except Exception:
        pass
    await ws.send_str(json.dumps({"type": "hello", "id": AGENT_ID, "host": os.uname().nodename,
                                  "display": DISPLAY, "version": VERSION, "screen": size,
                                  "sync_dir": str(SYNC), "clip_displays": x_displays(),
                                  "clip_ok": bool(shutil.which("xclip")),
                                  "features": ["rid", "fs", "apt", "sys", "rich", "battery"],
                                  "root": os.geteuid() == 0, "user": Path.home().name}))
    if battery_last:
        await ws.send_str(json.dumps({"type": "battery", **battery_last}))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                d = json.loads(msg.data)
                if d.get("rid"):
                    asyncio.create_task(handle_req(ws, d))
                else:
                    await handle(ws, d)
            except Exception as e:
                log("handle:", e)
    finally:
        clients.discard(ws)
        if injector:
            injector.release_all()
    return ws


async def info_handler(req: web.Request):
    return web.json_response({"app": "linkdeck-agent", "id": AGENT_ID, "name": os.uname().nodename,
                              "version": VERSION, "fp": FP})


# ------------------------------------------------------------------ terowongan VNC

async def vnc_handler(req: web.Request):
    if not authorized(req):
        return web.Response(status=403)
    ws = web.WebSocketResponse(max_msg_size=0)
    await ws.prepare(req)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", VNC_PORT)
    except OSError as e:
        await ws.close(message=f"VNC lokal tidak jalan: {e}"[:100].encode())
        return ws

    async def pump():
        try:
            while data := await reader.read(65536):
                await ws.send_bytes(data)
        finally:
            await ws.close()

    task = asyncio.create_task(pump())
    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                writer.write(msg.data)
                await writer.drain()
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
    finally:
        task.cancel()
        writer.close()
    return ws


# ------------------------------------------------------------------ terminal

async def term_handler(req: web.Request):
    if not authorized(req):
        return web.Response(status=403)
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(req)
    shell = os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"
    pid, fd = pty.fork()
    if pid == 0:  # anak: jadi shell
        os.chdir(str(Path.home()))
        env = {**ENV, "TERM": "xterm-256color", "COLORTERM": "truecolor"}
        os.execvpe(shell, [shell, "-l"], env)
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def readable():
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b""
        q.put_nowait(data)
        if not data:
            loop.remove_reader(fd)

    loop.add_reader(fd, readable)

    async def pump():
        while (data := await q.get()):
            await ws.send_bytes(data)
        await ws.close()

    task = asyncio.create_task(pump())
    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                os.write(fd, msg.data)
            elif msg.type == WSMsgType.TEXT:
                d = json.loads(msg.data)
                if d.get("type") == "resize":
                    fcntl.ioctl(fd, termios.TIOCSWINSZ,
                                struct.pack("HHHH", int(d["rows"]), int(d["cols"]), 0, 0))
                elif d.get("type") == "input":
                    os.write(fd, d["data"].encode())
    finally:
        task.cancel()
        try:
            loop.remove_reader(fd)
        except Exception:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
            os.close(fd)
            os.waitpid(pid, os.WNOHANG)
        except OSError:
            pass
    return ws


# ------------------------------------------------------------------ audio

def audio_command(rate: int, ch: int, fmt: str = "s16le") -> list[str] | None:
    if AUDIO_CMD:
        return shlex.split(AUDIO_CMD.format(rate=rate, ch=ch, fmt=fmt))
    if shutil.which("parec"):   # PulseAudio / pipewire-pulse (termasuk PULSE_SERVER ke Termux)
        return ["parec", "--raw", f"--format={fmt}", f"--rate={rate}", f"--channels={ch}",
                "--latency-msec=60", "-d", "@DEFAULT_MONITOR@"]
    if fmt != "s16le":
        return None
    if shutil.which("pw-record"):
        return ["pw-record", "--target", "0", "--format", "s16", "--rate", str(rate),
                "--channels", str(ch), "-"]
    return None


async def audio_handler(req: web.Request):
    if not authorized(req):
        return web.Response(status=403)
    q = req.query.get("q", "high")
    # high: 48 kHz stereo PCM (~1,5 Mbps) | mid: 24 kHz mono PCM (~384 kbps) | low: 16 kHz mono mu-law (~128 kbps)
    rate, ch, fmt = {"low": (16000, 1, "ulaw"), "mid": (24000, 1, "s16le")}.get(q, (48000, 2, "s16le"))
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(req)
    cmd = audio_command(rate, ch, fmt)
    if cmd is None and fmt != "s16le":
        rate, ch, fmt = 16000, 1, "s16le"
        cmd = audio_command(rate, ch, fmt)
    if not cmd:
        await ws.send_str(json.dumps({"type": "error", "msg": "Tidak ada parec/pw-record di Debian. "
                                      "Pasang pulseaudio-utils dan pastikan PulseAudio jalan."}))
        await ws.close()
        return ws
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV)
    await ws.send_str(json.dumps({"type": "format", "rate": rate, "channels": ch, "encoding": fmt}))

    async def pump():
        try:
            chunk = rate * ch * (1 if fmt == "ulaw" else 2) // 20             # ~50 ms
            while data := await proc.stdout.read(chunk):
                await ws.send_bytes(data)
            err = (await proc.stderr.read()).decode(errors="replace").strip()
            if err:
                await ws.send_str(json.dumps({"type": "error", "msg": f"Audio berhenti: {err[:200]}"}))
        finally:
            await ws.close()

    task = asyncio.create_task(pump())
    try:
        async for _ in ws:
            pass
    finally:
        task.cancel()
        if proc.returncode is None:
            proc.kill()
    return ws


# ------------------------------------------------------------------ antarmuka jaringan HP

IFACE_LABEL = (("wlan", "Wi-Fi"), ("bt-pan", "Bluetooth"), ("bnep", "Bluetooth"), ("rndis", "Tethering USB"),
               ("usb", "Tethering USB"), ("ap", "Hotspot"), ("swlan", "Hotspot"), ("rmnet", "Data seluler"),
               ("ccmni", "Data seluler"), ("seth", "Data seluler"), ("v4-rmnet", "Data seluler"))


def iface_label(name: str) -> str:
    return next((label for pre, label in IFACE_LABEL if name.startswith(pre)), name)


def list_ifaces() -> list[tuple[str, str]]:
    """(nama, IPv4) tiap antarmuka lewat ioctl SIOCGIFCONF — tetap jalan di proot Android 11+ (netlink diblokir)."""
    import array
    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        size = 40 if struct.calcsize("P") == 8 else 32          # sizeof(struct ifreq)
        buf = array.array("B", b"\0" * size * 32)
        ifc = struct.pack("iL", len(buf), buf.buffer_info()[0])
        n = struct.unpack("iL", fcntl.ioctl(s.fileno(), 0x8912, ifc))[0]
        raw = buf.tobytes()[:n]
        for i in range(0, n, size):
            name = raw[i:i + 16].split(b"\0", 1)[0].decode(errors="replace")
            ip = socket.inet_ntoa(raw[i + 20:i + 24])
            if name != "lo" and not ip.startswith("127."):
                out.append((name, ip))
        s.close()
    except OSError:
        pass
    return out


# ------------------------------------------------------------------ tugas latar

async def clip_loop() -> None:
    """Pantau clipboard di SEMUA layar X. Salinan baru di satu layar dikirim ke PC dan disamakan ke layar lain.
    Jenis isi diperiksa dulu (TARGETS): gambar/berkas dikirim sebagai gambar/berkas, selain itu sebagai teks."""
    global last_clip
    for d in x_displays():
        disp_clip[d] = await asyncio.to_thread(clip_get, d)
        got = await asyncio.to_thread(read_rich, d) if shutil.which("xclip") else None
        disp_rich[d] = rich_sig(*got) if got and got != UNKNOWN else None
    last_clip = disp_clip.get(DISPLAY)
    if not shutil.which("xclip"):
        log("Peringatan: xclip tidak ada; clipboard Debian tidak bisa dipantau. Pasang: sudo apt install xclip")
    while True:
        await asyncio.sleep(0.6)
        if not clients:
            continue
        for d in x_displays():
            targets = await asyncio.to_thread(xclip_targets, d)
            if rich_on["v"] and any(x in targets for x in RICH_TYPES):
                await rich_scan(d)
                if disp_rich.get(d):
                    continue                           # berisi gambar/berkas: jangan kirim juga sebagai teks
            if targets and not any(x in targets for x in TEXT_TYPES):
                continue                               # bukan teks (mis. hanya gambar): jangan dibaca sebagai teks
            text = await asyncio.to_thread(clip_get, d)
            if d not in disp_clip:                     # layar baru muncul: catat dulu, jangan kirim isi lama
                disp_clip[d] = text
                continue
            if not text or text == disp_clip.get(d):
                continue
            disp_clip[d] = text
            disp_rich[d] = None
            if text == last_clip or time.time() - recent_set.get(text, 0) < 6:   # gema dari PC: abaikan
                continue
            last_clip = text
            await send_all({"type": "clip", "text": text, "display": d})
            await clip_set_all(text, skip=d)           # samakan ke layar X lain di HP
        now = time.time()
        for table in (recent_set, rich_recent):
            for k in [k for k, v in table.items() if now - v > 60]:
                del table[k]


def mem_used_pct():
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0])
        return round(100 * (1 - info["MemAvailable"] / info["MemTotal"]))
    except Exception:
        return None


async def info_loop() -> None:
    while True:
        await asyncio.sleep(3)
        if not clients:
            continue
        try:
            load = os.getloadavg()[0]
        except OSError:
            load = None
        await send_all({"type": "info", "load": load, "mem": mem_used_pct(), "host": os.uname().nodename,
                        "clip_displays": x_displays()})


# ---------------------------------------------------------------- baterai HP (tanpa adb)

battery_last: dict | None = None


def _read(p: Path) -> str:
    try:
        return p.read_text().strip()
    except OSError:
        return ""


def battery_sysfs() -> dict | None:
    """Baca /sys/class/power_supply (jalan di chroot/root; di proot sering ditolak SELinux)."""
    try:
        entries = sorted(POWER_DIR.iterdir())
    except OSError:
        return None
    plugged = "none"
    for e in entries:
        kind = _read(e / "type").lower()
        if kind in ("usb", "mains", "wireless", "usb_pd", "usb_c") and _read(e / "online") == "1":
            plugged = {"mains": "ac", "wireless": "wireless"}.get(kind, "usb")
    for e in entries:
        if _read(e / "type") != "Battery":
            continue
        cap = _read(e / "capacity")
        if not cap.isdigit():
            continue
        status = _read(e / "status").lower()
        temp = _read(e / "temp")
        return {"level": min(100, int(cap)), "plugged": plugged, "source": "sysfs",
                "charging": status == "charging" or (status == "full" and plugged != "none"),
                "temp": round(int(temp) / 10, 1) if temp.lstrip("-").isdigit() else None}
    return None


def battery_termux() -> dict | None:
    """termux-battery-status (paket termux-api + aplikasi Termux:API)."""
    for exe in TERMUX_BATTERY:
        if "/" in exe:
            path = exe if os.access(exe, os.X_OK) else None
        else:
            path = shutil.which(exe)
        if not path:
            continue
        try:
            out = subprocess.run([path], capture_output=True, text=True, timeout=8).stdout
            j = json.loads(out)
            level = int(j["percentage"])
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            continue
        st = str(j.get("status") or "").upper()
        plugged = {"PLUGGED_USB": "usb", "PLUGGED_AC": "ac", "PLUGGED_WIRELESS": "wireless"}.get(
            str(j.get("plugged") or "").upper(), "none")
        temp = j.get("temperature")
        return {"level": level, "plugged": plugged, "source": "termux",
                "charging": st == "CHARGING" or (st == "FULL" and plugged != "none"),
                "temp": round(float(temp), 1) if isinstance(temp, (int, float)) else None}
    return None


async def publish_battery(b: dict) -> None:
    global battery_last
    changed = not battery_last or any(battery_last.get(k) != b.get(k) for k in ("level", "charging", "plugged"))
    battery_last = b
    if changed:
        await send_all({"type": "battery", **b})


async def battery_loop() -> None:
    """Baterai HP untuk PC: dari aplikasi pendamping (langsung, saat berubah), atau dibaca berkala."""
    termux_retry = 0.0
    while True:
        if not clients:
            await asyncio.sleep(5)
            continue
        try:
            path = "\0" + COMPANION_SOCK[1:] if COMPANION_SOCK.startswith("@") else COMPANION_SOCK
            r, w = await asyncio.wait_for(asyncio.open_unix_connection(path), 5)
        except (OSError, asyncio.TimeoutError, ValueError):
            r = w = None
        if r:
            try:
                while True:
                    line = await r.readline()
                    if not line:
                        break
                    try:
                        m = json.loads(line)
                    except ValueError:
                        continue
                    if m.get("type") == "battery" and isinstance(m.get("level"), int) and m["level"] >= 0:
                        temp = m.get("temp")
                        await publish_battery({"level": m["level"], "charging": bool(m.get("charging")),
                                               "plugged": m.get("plugged") or "none", "source": "companion",
                                               "temp": temp if isinstance(temp, (int, float)) else None})
            except (OSError, asyncio.IncompleteReadError, ValueError):
                pass
            finally:
                w.close()
            await asyncio.sleep(5)
            continue
        b = await asyncio.to_thread(battery_sysfs)
        if b is None and time.time() >= termux_retry:
            b = await asyncio.to_thread(battery_termux)
            if b is None:
                termux_retry = time.time() + 600      # tidak tersedia: jangan dicoba terus
        if b:
            await publish_battery(b)
        await asyncio.sleep(30)


async def outbox_loop() -> None:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    SENT.mkdir(parents=True, exist_ok=True)
    while True:
        await asyncio.sleep(2)
        if not clients:
            continue
        for f in sorted(OUTBOX.iterdir()):
            if not f.is_file() or time.time() - f.stat().st_mtime < 1.5:
                continue
            if f.stat().st_size > MAX_FILE:
                continue
            await send_all({"type": "file", "name": f.name,
                            "data": base64.b64encode(f.read_bytes()).decode()})
            shutil.move(str(f), str(unique(SENT / f.name)))


async def beacon_loop() -> None:
    """Siarkan keberadaan agen ke jaringan lokal (Wi-Fi dan tethering Bluetooth)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)
    msg = json.dumps({"ld": 1, "id": AGENT_ID, "name": os.uname().nodename, "port": PORT,
                      "fp": FP, "v": VERSION}).encode()
    tick = 0
    targets: set[str] = set()
    while True:
        if tick % 10 == 0:
            # siaran per jaringan (Wi-Fi, Bluetooth, hotspot) — 255.255.255.255 saja hanya keluar lewat
            # jalur utama, yang sering kali data seluler
            targets = {"255.255.255.255", "192.168.44.255"}
            for name, ip in list_ifaces():
                if iface_label(name) != "Data seluler":
                    targets.add(ip.rsplit(".", 1)[0] + ".255")
        for target in targets:
            try:
                sock.sendto(msg, (target, BEACON_PORT))
            except OSError:
                pass
        tick += 1
        await asyncio.sleep(2)


async def on_startup(app):
    for fn in (clip_loop, info_loop, outbox_loop, beacon_loop, battery_loop):
        asyncio.create_task(fn())


def main() -> None:
    import sys
    if "--ifaces" in sys.argv:                        # dipakai linkdeck-start untuk menampilkan IP
        rows = list_ifaces()
        for name, ip in rows:
            print(f"  {iface_label(name) + ' (' + name + ')':<26}: {ip}")
        if not rows:
            print("  (daftar jaringan tidak terbaca)")
        return
    if not TOKEN:
        raise SystemExit("LINKDECK_TOKEN kosong. Jalankan lewat linkdeck-start.")
    ctx = None
    if CERT.exists() and KEY.exists():
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(str(CERT), str(KEY))
    else:
        log("Peringatan: sertifikat tidak ada, berjalan TANPA enkripsi. Jalankan linkdeck-setup.")
    if not shutil.which("xclip"):
        log("Peringatan: xclip tidak ada, clipboard tidak akan tersinkron.")
    app = web.Application(client_max_size=MAX_FILE * 2)
    app.router.add_get("/info", info_handler)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/vnc", vnc_handler)
    app.router.add_get("/term", term_handler)
    app.router.add_get("/audio", audio_handler)
    app.on_startup.append(on_startup)
    log(f"Agen LinkDeck {VERSION} di port {PORT} ({'TLS' if ctx else 'tanpa TLS'}), DISPLAY {DISPLAY}")
    web.run_app(app, host="0.0.0.0", port=PORT, ssl_context=ctx, print=None)


if __name__ == "__main__":
    main()
