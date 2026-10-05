#!/usr/bin/env python3
"""
LinkDeck — jembatan layar, clipboard, berkas, suara, dan input antara HP (Android + Debian XFCE) dan PC.

    python server.py       # server saja, buka http://127.0.0.1:8740
    python app.py          # aplikasi desktop (jendela sendiri)

Di belakang layar:
    adb + scrcpy (>= 4.0)  layar virtual / cermin / kamera Android, jendela per aplikasi, notifikasi
    agen Debian (TLS)      desktop XFCE (VNC lewat terowongan), terminal, audio, clipboard,
                           berkas, sinkron folder, satu mouse & keyboard
"""
from __future__ import annotations

import asyncio
import base64
import glob
import hashlib
import io
import json
import mimetypes
import os
import re
import secrets
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import webbrowser
from asyncio.subprocess import PIPE, STDOUT
from pathlib import Path

import aiohttp
from aiohttp import ClientSession, WSMsgType, web

try:
    import pyperclip
except ImportError:
    pyperclip = None

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

FROZEN = getattr(sys, "frozen", False)
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
import notif  # noqa: E402

STATIC = ROOT / "static"
BIN = ROOT / "bin"
if not BIN.is_dir():
    BIN = ROOT / "vendor" / "scrcpy"
if BIN.is_dir():
    os.environ["PATH"] = str(BIN) + os.pathsep + os.environ.get("PATH", "")
VERSION = os.environ.get("LINKDECK_VERSION") or next(
    (p.read_text().strip() for p in (ROOT / "VERSION",) if p.exists()), "dev")


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "LinkDeck"


def _asset_dir(name: str) -> Path:
    bundled = STATIC / name
    if any(bundled.glob("*")) or not FROZEN:
        return bundled
    return user_data_dir() / name


NOVNC_DIR = _asset_dir("novnc")
XTERM_DIR = _asset_dir("xterm")
NOVNC_VERSION = "1.5.0"
NOVNC_URL = f"https://github.com/novnc/noVNC/archive/refs/tags/v{NOVNC_VERSION}.tar.gz"
XTERM_PKGS = {
    "xterm": ("https://registry.npmjs.org/@xterm/xterm/-/xterm-5.5.0.tgz",
              {"package/lib/xterm.js": "xterm.js", "package/css/xterm.css": "xterm.css",
               "package/LICENSE": "LICENSE"}),
    "fit": ("https://registry.npmjs.org/@xterm/addon-fit/-/addon-fit-0.10.0.tgz",
            {"package/lib/addon-fit.js": "addon-fit.js"}),
}
OPEN_BROWSER = True
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

HOST = "127.0.0.1"
PORT = int(os.environ.get("LINKDECK_PORT", "8740"))
SAVE_DIR = Path(os.environ.get("LINKDECK_SAVE_DIR", str(Path.home() / "Downloads" / "LinkDeck")))
SYNC_DIR = Path(os.environ.get("LINKDECK_SYNC_DIR", str(Path.home() / "LinkDeck-Sinkron")))
TOKEN = secrets.token_urlsafe(18)
MAX_AGENT_FILE = 48 * 1024 * 1024
LOCAL_AGENT_PORT = 18765
EXT_VNC_PORT = 15900
AGENT_PORT = 8765
BEACON_PORT = 47823
ANDROID_DROP = "/sdcard/Download/LinkDeck"

# Preset per jalur. --video-buffer meredam patah-patah akibat jitter jaringan (sedikit menambah jeda).
PRESETS = {
    "usb": ["--video-bit-rate=16M", "--max-fps=60"],
    "wifi": ["--video-bit-rate=6M", "--max-size=1600", "--max-fps=60", "--video-buffer=40"],
    "bt": ["--video-bit-rate=800K", "--max-size=720", "--max-fps=15", "--video-buffer=150", "--no-audio"],
}
# Kualitas VNC (noVNC) per jalur: (kualitas JPEG 0-9, kompresi 0-9)
VNC_QUALITY = {"usb": (8, 1), "wifi": (6, 2), "bt": (2, 9)}
# Seberapa sering adb ditanya (detik) per jalur: Bluetooth jauh lebih jarang agar tidak memakan bandwidth
POLL = {"usb": {"lat": 3, "bat": 15, "notif": 6}, "wifi": {"lat": 3, "bat": 30, "notif": 8},
        "bt": {"lat": 15, "bat": 120, "notif": 25}}
NOTIF_CMD = r"dumpsys notification --noredact | grep -E '^  [^ ]|NotificationRecord\(|android\.(title|text|bigText)='"
DEVICE_GRACE = 10   # detik: perangkat yang hilang sesaat tetap ditampilkan (cegah UI berkedip)
DEFAULT_SETTINGS = {"autoconnect": True, "sync": True, "notif": True}


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(p)


class State:
    def __init__(self) -> None:
        self.ui: set[web.WebSocketResponse] = set()
        self.tools: dict = {}
        self.devices: list[dict] = []
        self.sessions: dict[str, dict] = {}          # id -> {serial, mode, label, proc}
        self.stopping: set[str] = set()
        self.debian: dict | None = None
        self.connecting = False
        self.agent_ws = None
        self.agent_task: asyncio.Task | None = None
        self.debian_info: dict = {"load": [], "mem": None, "host": None, "screen": None}
        self.clips: list[dict] = []
        self.last_clip: str | None = None
        self.clip_warned = False
        self.stats: dict[str, dict] = {}
        self.vnc_bytes = 0
        self.vnc_rate: list[float] = []
        self.tasks: list[asyncio.Task] = []
        self.discovered: dict[str, dict] = {}
        self.pairings: dict = load_json(user_data_dir() / "pairings.json", {})
        self.settings: dict = {**DEFAULT_SETTINGS, **load_json(user_data_dir() / "settings.json", {})}
        self.waiters: dict[str, asyncio.Future] = {}
        self.notifs: list[dict] = []
        self.notif_seen: dict[str, set] = {}
        self.apps: dict[str, list] = {}
        self.kvm = None
        self.kvm_on = False
        self.ext_vnc: asyncio.base_events.Server | None = None
        self.sync_state: dict = load_json(user_data_dir() / "sync-state.json", {})
        self.sync_info = {"last": None, "count": 0, "error": None}
        self.loop: asyncio.AbstractEventLoop | None = None
        # alamat adb jaringan yang disiapkan lewat kabel: {"ip:5555": "bt"|"wifi"}
        self.adb_targets: dict = load_json(user_data_dir() / "adb-targets.json", {})
        self.dev_gone: dict[str, float] = {}
        self.polled: dict[str, float] = {}


S = State()


# ================================================================ utilitas

async def run(*args: str, timeout: float = 20.0) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=PIPE, stderr=PIPE, creationflags=NOWIN)
    except FileNotFoundError:
        return 127, "", f"'{args[0]}' tidak ditemukan di PATH"
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "perintah melewati batas waktu"
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def run_bytes(*args: str, timeout: float = 20.0) -> tuple[int, bytes]:
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=PIPE, stderr=PIPE, creationflags=NOWIN)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        return proc.returncode or 0, out
    except (FileNotFoundError, asyncio.TimeoutError):
        return 1, b""


async def broadcast(event: dict) -> None:
    data = json.dumps(event)
    for ws in list(S.ui):
        try:
            await ws.send_str(data)
        except Exception:
            S.ui.discard(ws)


async def log(msg: str, level: str = "info") -> None:
    print(f"[{level}] {msg}", flush=True)
    await broadcast({"type": "log", "level": level, "msg": msg, "t": time.time()})


def ok(**kw) -> web.Response:
    return web.json_response({"ok": True, **kw})


def fail(msg: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": msg}, status=status)


def safe_name(name: str) -> str:
    name = Path(name or "berkas").name
    name = re.sub(r"[^\w.\- ()\[\]]+", "_", name).strip(" .")
    return name[:120] or "berkas"


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 999):
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
    return p.with_name(f"{p.stem}-{int(time.time())}{p.suffix}")


def classify(serial: str) -> str:
    if serial in S.adb_targets:
        return S.adb_targets[serial]
    m = re.match(r"^(\d+\.\d+\.\d+\.\d+):\d+$", serial)
    if m:
        return "bt" if m.group(1).startswith("192.168.44.") else "wifi"
    if "_adb-tls-connect" in serial:
        return "wifi"
    return "usb"


def short_fp(fp: str) -> str:
    return ":".join(fp[i:i + 2] for i in range(0, 16, 2)).upper() if fp else ""


def public_debian() -> dict | None:
    if not S.debian:
        return None
    d = {k: v for k, v in S.debian.items() if k not in ("pin",)}
    d["agent"] = S.agent_ws is not None
    d["fp_short"] = short_fp(S.debian.get("fp", ""))
    d["has_password"] = bool(S.pairings.get(S.debian.get("id", ""), {}).get("password"))
    d["kvm"] = S.kvm_on
    d["vnc_quality"] = VNC_QUALITY.get(S.debian.get("transport"), VNC_QUALITY["wifi"])
    d["screen"] = S.debian_info.get("screen")
    return d


def public_sessions() -> list[dict]:
    return [{"id": k, "serial": v["serial"], "mode": v["mode"], "label": v["label"]}
            for k, v in S.sessions.items()]


def public_pairings() -> list[dict]:
    return [{"id": k, "name": v.get("name"), "fp_short": short_fp(v.get("fp", ""))}
            for k, v in S.pairings.items()]


def save_pairings() -> None:
    save_json(user_data_dir() / "pairings.json", S.pairings)


# ================================================================ alat & perangkat

async def detect_tools() -> dict:
    t = {k: bool(shutil.which(k)) for k in ("adb", "scrcpy", "vncviewer")}
    t["clipboard"] = pyperclip is not None
    t["scrcpy_version"] = None
    t["virtual_display"] = t["flex"] = False
    if t["scrcpy"]:
        _, out, err = await run("scrcpy", "--version", timeout=8)
        m = re.search(r"scrcpy (\d+)\.(\d+)", out + err)
        if m:
            major = int(m.group(1))
            t["scrcpy_version"] = f"{m.group(1)}.{m.group(2)}"
            t["virtual_display"] = major >= 3
            t["flex"] = major >= 4
    t["novnc"] = (NOVNC_DIR / "core" / "rfb.js").exists()
    t["xterm"] = (XTERM_DIR / "xterm.js").exists()
    t["v4l2"] = sorted(glob.glob("/dev/video*")) if sys.platform.startswith("linux") else []
    t["platform"] = sys.platform
    S.tools = t
    return t


async def refresh_devices() -> None:
    if not S.tools.get("adb"):
        S.devices = []
        return
    _, out, _ = await run("adb", "devices", "-l", timeout=8)
    busy = {s["serial"] for s in S.sessions.values()}
    devs = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        serial = parts[0]
        devs.append({"serial": serial, "state": parts[1], "model": info.get("model", serial).replace("_", " "),
                     "transport": classify(serial), "mirroring": serial in busy})
    now, present = time.time(), {d["serial"] for d in devs}
    for old in S.devices:
        if old["serial"] in present:
            continue
        first = S.dev_gone.setdefault(old["serial"], now)
        if now - first < DEVICE_GRACE:          # putus sesaat (umum di Bluetooth): tahan dulu
            devs.append(old)
    for serial in present:
        S.dev_gone.pop(serial, None)
    if devs != S.devices:
        S.devices = devs
        await broadcast({"type": "devices", "devices": devs})


# ================================================================ clipboard

async def set_pc_clip(text: str) -> None:
    if not pyperclip:
        return
    try:
        await asyncio.to_thread(pyperclip.copy, text)
    except Exception:
        if not S.clip_warned:
            S.clip_warned = True
            hint = " Pasang xclip atau wl-clipboard." if sys.platform.startswith("linux") else ""
            await log("Clipboard PC tidak bisa ditulis." + hint, "warn")


async def add_clip(text: str, src: str) -> None:
    text = text[:20000]
    if S.clips and S.clips[0]["text"] == text:
        return
    item = {"id": secrets.token_hex(4), "text": text, "src": src, "t": time.time()}
    S.clips.insert(0, item)
    del S.clips[40:]
    await broadcast({"type": "clip", "item": item})


async def clip_watcher() -> None:
    if not pyperclip:
        return
    try:
        S.last_clip = await asyncio.to_thread(pyperclip.paste)
    except Exception:
        S.last_clip = None
    while True:
        await asyncio.sleep(0.7)
        try:
            text = await asyncio.to_thread(pyperclip.paste)
        except Exception:
            continue
        if text and text != S.last_clip:
            S.last_clip = text
            await add_clip(text, "pc")
            await send_agent({"type": "clip", "text": text})


# ================================================================ agen Debian (TLS)

def agent_ssl(fp: str | None):
    return aiohttp.Fingerprint(bytes.fromhex(fp)) if fp else False


def agent_url(path: str) -> str:
    d = S.debian
    return f"wss://{d['host']}:{d['port']}{path}?token={d['pin']}"


def cert_fp(host: str, port: int) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=4) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            return hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()


async def agent_info(host: str, port: int, fp: str | None = None, timeout: float = 4) -> dict:
    async with ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
        async with s.get(f"https://{host}:{port}/info", ssl=agent_ssl(fp)) as r:
            return await r.json()


async def send_agent(obj: dict) -> bool:
    ws = S.agent_ws
    if ws is None or ws.closed:
        return False
    try:
        await ws.send_str(json.dumps(obj))
        return True
    except Exception:
        return False


async def agent_request(obj: dict, key: str, timeout: float = 30) -> dict | None:
    fut = asyncio.get_running_loop().create_future()
    S.waiters[key] = fut
    try:
        if not await send_agent(obj):
            return None
        return await asyncio.wait_for(fut, timeout)
    except asyncio.TimeoutError:
        return None
    finally:
        S.waiters.pop(key, None)


async def on_agent_msg(d: dict) -> None:
    t = d.get("type")
    if t in ("sync_list",):
        fut = S.waiters.get("sync_list")
        if fut and not fut.done():
            fut.set_result(d)
    elif t == "sync_file":
        fut = S.waiters.get("sync_file:" + d.get("path", ""))
        if fut and not fut.done():
            fut.set_result(d)
    elif t == "clip":
        text = d.get("text", "")
        if text and text != S.last_clip:
            S.last_clip = text
            await set_pc_clip(text)
            await add_clip(text, "debian")
    elif t == "file":
        name = safe_name(d.get("name", "berkas"))
        try:
            data = base64.b64decode(d.get("data", ""))
        except ValueError:
            return
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        dest = unique_path(SAVE_DIR / name)
        dest.write_bytes(data)
        await broadcast({"type": "file", "from": "debian", "name": dest.name, "path": str(dest)})
    elif t == "info":
        info = S.debian_info
        if isinstance(d.get("load"), (int, float)):
            info["load"] = (info["load"] + [round(float(d["load"]), 2)])[-40:]
        info["mem"] = d.get("mem")
        info["host"] = d.get("host") or info["host"]
    elif t == "hello":
        S.debian_info["host"] = d.get("host")
        S.debian_info["screen"] = d.get("screen")
        if S.debian:
            S.debian["sync_dir"] = d.get("sync_dir")
    elif t == "saved":
        await log(f"Debian menyimpan {d.get('name')} di ~/Downloads/LinkDeck")
    elif t == "kvm_release":
        if S.kvm:
            await asyncio.to_thread(S.kvm.release, d.get("fy"))
    elif t == "resolution":
        if d.get("screen"):
            S.debian_info["screen"] = d["screen"]
        await broadcast({"type": "resolution", "ok": d.get("ok"), "size": d.get("size"),
                         "msg": d.get("msg"), "screen": d.get("screen")})
    elif t == "error":
        await log(d.get("msg", "Kesalahan di agen Debian"), "warn")


async def agent_loop() -> None:
    while S.debian:
        try:
            async with ClientSession() as sess:
                async with sess.ws_connect(agent_url("/ws"), ssl=agent_ssl(S.debian["fp"]), heartbeat=15,
                                           max_msg_size=MAX_AGENT_FILE * 2, timeout=6) as ws:
                    S.agent_ws = ws
                    await broadcast({"type": "debian", "debian": public_debian()})
                    async for msg in ws:
                        if msg.type == WSMsgType.TEXT:
                            try:
                                await on_agent_msg(json.loads(msg.data))
                            except ValueError:
                                pass
                        elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                            break
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        if S.agent_ws is not None:
            S.agent_ws = None
            if S.kvm:
                await asyncio.to_thread(S.kvm.release, None)
            await broadcast({"type": "debian", "debian": public_debian()})
        await asyncio.sleep(3)


async def connect_debian(transport: str, host: str, serial: str | None, pin: str,
                         remember: bool = True) -> dict:
    """Hubungkan ke agen Debian. Mengembalikan public_debian(); melempar ValueError berisi pesan."""
    port = AGENT_PORT
    if transport == "usb":
        if not serial:
            raise ValueError("Pilih HP yang tersambung kabel di bagian Android.")
        c, _, e = await run("adb", "-s", serial, "forward", f"tcp:{LOCAL_AGENT_PORT}", f"tcp:{AGENT_PORT}")
        if c:
            raise ValueError(f"adb forward gagal: {e.strip()}")
        host, port = "127.0.0.1", LOCAL_AGENT_PORT
    elif not re.match(r"^[\w.\-]+$", host or ""):
        raise ValueError("Isi IP HP, misalnya 192.168.1.23.")
    try:
        fp = await asyncio.to_thread(cert_fp, host, port)
        info = await agent_info(host, port, fp)
    except Exception as e:
        raise ValueError(f"Agen Debian tidak menjawab di {host}:{port}. Jalankan 'linkdeck-start' "
                         f"di Debian lalu coba lagi. ({e.__class__.__name__})")
    aid = info.get("id") or fp[:16]
    pairing = S.pairings.get(aid)
    if pairing and pairing.get("fp") and pairing["fp"] != fp:
        raise ValueError("Sidik jari sertifikat agen BERUBAH sejak terakhir tersambung. Kalau kamu "
                         "baru menjalankan 'linkdeck-cert --baru', lupakan perangkat ini lalu sambungkan "
                         "ulang. Kalau tidak, bisa jadi ada yang menyamar di jaringan.")
    pin = pin or (pairing or {}).get("pin", "")
    if not pin:
        raise ValueError("Isi PIN agen yang tampil di 'linkdeck-start'.")
    try:
        async with ClientSession() as s:
            async with s.ws_connect(f"wss://{host}:{port}/ws?token={pin}", ssl=aiohttp.Fingerprint(bytes.fromhex(fp)),
                                    timeout=6):
                pass
    except aiohttp.WSServerHandshakeError as e:
        if e.status == 403:
            if pairing:
                pairing.pop("pin", None)
                save_pairings()
            raise ValueError("PIN agen salah.")
        raise ValueError(f"Agen menolak sambungan ({e.status}).")

    await stop_debian()
    S.debian = {"transport": transport, "serial": serial, "host": host, "port": port, "pin": pin,
                "fp": fp, "id": aid, "name": info.get("name") or host, "version": info.get("version")}
    S.debian_info = {"load": [], "mem": None, "host": None, "screen": None}
    if remember:
        entry = S.pairings.setdefault(aid, {})
        entry.update({"name": S.debian["name"], "pin": pin, "fp": fp})
        save_pairings()
    S.agent_task = asyncio.create_task(agent_loop())
    await log(f"Debian {S.debian['name']} tersambung lewat {transport.upper()} (terenkripsi TLS)")
    await broadcast({"type": "debian", "debian": public_debian()})
    await broadcast({"type": "pairings", "pairings": public_pairings()})
    return public_debian()


async def stop_debian() -> None:
    if S.kvm:
        await asyncio.to_thread(S.kvm.stop)
        S.kvm_on = False
    if S.ext_vnc:
        S.ext_vnc.close()
        S.ext_vnc = None
    if S.agent_task:
        S.agent_task.cancel()
        S.agent_task = None
    if S.agent_ws is not None:
        await S.agent_ws.close()
        S.agent_ws = None
    S.debian = None


# ================================================================ penemuan otomatis

class BeaconProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        try:
            d = json.loads(data.decode())
        except Exception:
            return
        if d.get("ld") != 1 or not d.get("id"):
            return
        asyncio.ensure_future(on_discovered({
            "id": d["id"], "name": d.get("name") or addr[0], "host": addr[0], "port": int(d.get("port", AGENT_PORT)),
            "transport": "bt" if addr[0].startswith("192.168.44.") else "wifi", "serial": None,
            "fp": d.get("fp", "")}))


async def on_discovered(entry: dict) -> None:
    entry["seen"] = time.time()
    entry["paired"] = entry["id"] in S.pairings and bool(S.pairings[entry["id"]].get("pin"))
    entry["fp_short"] = short_fp(entry.get("fp", ""))
    old = S.discovered.get(entry["id"])
    # kabel lebih diutamakan daripada jaringan untuk perangkat yang sama
    if old and old["transport"] == "usb" and entry["transport"] != "usb" and time.time() - old["seen"] < 10:
        old["seen"] = time.time()
        return
    S.discovered[entry["id"]] = entry
    if not old or {k: old.get(k) for k in ("host", "transport", "paired")} != \
            {k: entry.get(k) for k in ("host", "transport", "paired")}:
        await broadcast_discovered()
    await maybe_autoconnect(entry)


async def broadcast_discovered() -> None:
    items = [{k: v for k, v in e.items() if k != "fp"} for e in S.discovered.values()]
    await broadcast({"type": "discovered", "items": items})


async def maybe_autoconnect(entry: dict) -> None:
    if not S.settings.get("autoconnect") or S.debian or S.connecting or not entry.get("paired"):
        return
    S.connecting = True
    try:
        await connect_debian(entry["transport"], entry["host"], entry.get("serial"), "")
        await broadcast({"type": "autoconnected", "debian": public_debian()})
    except ValueError as e:
        await log(f"Sambung otomatis gagal: {e}", "warn")
        entry["paired"] = False
    finally:
        S.connecting = False


async def discovery_loop() -> None:
    loop = asyncio.get_running_loop()
    try:
        await loop.create_datagram_endpoint(BeaconProtocol, local_addr=("0.0.0.0", BEACON_PORT),
                                            reuse_port=hasattr(socket, "SO_REUSEPORT") or None,
                                            allow_broadcast=True)
    except Exception as e:
        print("beacon:", e, flush=True)
    while True:
        await asyncio.sleep(4)
        # HP lewat kabel: coba agen lewat adb forward
        if not S.debian:
            for dev in S.devices:
                if dev["transport"] != "usb" or dev["state"] != "device":
                    continue
                c, _, _ = await run("adb", "-s", dev["serial"], "forward", f"tcp:{LOCAL_AGENT_PORT}",
                                    f"tcp:{AGENT_PORT}", timeout=5)
                if c:
                    continue
                try:
                    info = await agent_info("127.0.0.1", LOCAL_AGENT_PORT, timeout=2)
                    await on_discovered({"id": info["id"], "name": info.get("name") or dev["model"],
                                         "host": "127.0.0.1", "port": LOCAL_AGENT_PORT, "transport": "usb",
                                         "serial": dev["serial"], "fp": info.get("fp", "")})
                except Exception:
                    pass
                break
        expired = [k for k, v in S.discovered.items() if time.time() - v["seen"] > 9]
        for k in expired:
            del S.discovered[k]
        if expired:
            await broadcast_discovered()


# ================================================================ sinkron folder

def local_manifest() -> dict:
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for f in SYNC_DIR.rglob("*"):
        if f.is_file() and not f.name.startswith(".") and f.stat().st_size <= MAX_AGENT_FILE:
            st = f.stat()
            out[f.relative_to(SYNC_DIR).as_posix()] = [st.st_size, int(st.st_mtime)]
    return out


def _same(a, b) -> bool:
    return a and b and a[0] == b[0] and abs(a[1] - b[1]) <= 2


async def sync_once() -> int:
    """Sinkron dua arah: yang lebih baru menang, hapus ikut tersebar. Mengembalikan jumlah aksi."""
    aid = S.debian["id"]
    res = await agent_request({"type": "sync_list"}, "sync_list", timeout=15)
    if res is None:
        return 0
    remote = res.get("files", {})
    local = await asyncio.to_thread(local_manifest)
    prev = S.sync_state.get(aid, {})
    actions = 0
    for path in sorted(set(remote) | set(local)):
        r, l, p = remote.get(path), local.get(path), prev.get(path)
        if r and l:
            if _same(r, l):
                continue
            if l[1] > r[1]:
                await push_file(path)
            else:
                await pull_file(path)
        elif l and not r:
            if p and _same(p, l):
                (SYNC_DIR / path).unlink(missing_ok=True)       # dihapus di Debian
            else:
                await push_file(path)
        elif r and not l:
            if p and _same(p, r):
                await send_agent({"type": "sync_del", "path": path})  # dihapus di PC
            else:
                await pull_file(path)
        actions += 1
    if actions:
        res = await agent_request({"type": "sync_list"}, "sync_list", timeout=15)
        remote = res.get("files", {}) if res else remote
    S.sync_state[aid] = {k: v for k, v in remote.items()}
    save_json(user_data_dir() / "sync-state.json", S.sync_state)
    return actions


async def push_file(path: str) -> None:
    f = SYNC_DIR / path
    await send_agent({"type": "sync_put", "path": path, "mtime": int(f.stat().st_mtime),
                      "data": base64.b64encode(f.read_bytes()).decode()})


async def pull_file(path: str) -> None:
    d = await agent_request({"type": "sync_get", "path": path}, "sync_file:" + path, timeout=60)
    if not d:
        return
    dest = (SYNC_DIR / path).resolve()
    if not str(dest).startswith(str(SYNC_DIR.resolve()) + os.sep):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.part")
    tmp.write_bytes(base64.b64decode(d["data"]))
    os.utime(tmp, (time.time(), int(d["mtime"])))
    tmp.replace(dest)


async def sync_loop() -> None:
    while True:
        await asyncio.sleep(5)
        if not (S.settings.get("sync") and S.debian and S.agent_ws):
            continue
        try:
            n = await sync_once()
            S.sync_info = {"last": time.time(), "count": S.sync_info["count"] + n, "error": None,
                           "dir": str(SYNC_DIR), "remote": (S.debian or {}).get("sync_dir")}
            if n:
                await broadcast({"type": "sync", "info": S.sync_info, "changed": n})
        except Exception as e:
            S.sync_info["error"] = str(e)


# ================================================================ notifikasi Android

async def notif_loop() -> None:
    while True:
        await asyncio.sleep(2)
        if not S.settings.get("notif"):
            continue
        for dev in list(S.devices):
            if dev["state"] != "device":
                continue
            serial = dev["serial"]
            if not due("notif:" + serial, POLL.get(dev["transport"], POLL["wifi"])["notif"]):
                continue
            # disaring di HP supaya yang terkirim hanya beberapa KB (penting untuk Bluetooth)
            c, out, _ = await run("adb", "-s", serial, "shell", NOTIF_CMD, timeout=15)
            if c:
                continue
            items = notif.parse(out)
            first = serial not in S.notif_seen
            seen = S.notif_seen.setdefault(serial, set())
            labels = {a["pkg"]: a["label"] for a in S.apps.get(serial, [])}
            fresh = []
            for n in items:
                if n["id"] in seen:
                    continue
                seen.add(n["id"])
                item = {"id": n["id"], "serial": serial, "pkg": n["pkg"],
                        "app": labels.get(n["pkg"]) or n["pkg"].rsplit(".", 1)[-1].capitalize(),
                        "title": n["title"][:200], "text": n["text"][:500], "t": time.time(), "quiet": first}
                S.notifs.insert(0, item)
                fresh.append(item)
            del S.notifs[60:]
            if len(seen) > 2000:
                S.notif_seen[serial] = {n["id"] for n in items}
            if fresh:
                await broadcast({"type": "notif", "items": fresh})


# ================================================================ satu mouse & keyboard

_kvm_acc = {"dx": 0, "dy": 0, "pending": False}


def _kvm_flush() -> None:
    dx, dy = _kvm_acc["dx"], _kvm_acc["dy"]
    _kvm_acc.update(dx=0, dy=0, pending=False)
    if dx or dy:
        asyncio.ensure_future(send_agent({"type": "in", "k": "move", "dx": dx, "dy": dy}))


def _kvm_queue(obj: dict) -> None:
    if obj.get("k") == "move":
        # gabungkan gerakan mouse: maks ~60 paket/detik (Wi-Fi/kabel) atau ~30 (Bluetooth)
        _kvm_acc["dx"] += obj["dx"]
        _kvm_acc["dy"] += obj["dy"]
        if not _kvm_acc["pending"]:
            _kvm_acc["pending"] = True
            gap = 0.033 if (S.debian or {}).get("transport") == "bt" else 0.016
            S.loop.call_later(gap, _kvm_flush)
        return
    _kvm_flush()                      # klik/tombol: kirim gerakan tertunda dulu agar urutannya benar
    asyncio.ensure_future(send_agent(obj))


def kvm_send(obj: dict) -> None:
    if S.loop:
        S.loop.call_soon_threadsafe(_kvm_queue, obj)


def kvm_state(captured: bool) -> None:
    if S.loop:
        S.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(
            broadcast({"type": "kvm", "on": S.kvm_on, "captured": captured})))


async def h_kvm(req: web.Request) -> web.Response:
    d = await req.json()
    if d.get("on"):
        if not S.agent_ws:
            return fail("Hubungkan desktop Debian dulu.")
        try:
            import kvm
            if S.kvm is None:
                S.kvm = kvm.KVM(kvm_send, kvm_state)
            await asyncio.to_thread(S.kvm.start, d.get("edge", "right"))
        except Exception as e:
            return fail(str(e))
        S.kvm_on = True
    else:
        if S.kvm:
            await asyncio.to_thread(S.kvm.stop)
        S.kvm_on = False
    await broadcast({"type": "kvm", "on": S.kvm_on, "captured": False})
    return ok(on=S.kvm_on)


# ================================================================ HTTP: umum

async def h_index(req: web.Request) -> web.Response:
    html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__LD_TOKEN__", TOKEN)
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-store"})


def find_agent_deb() -> Path | None:
    for d in (ROOT / "phone", ROOT / "dist"):
        found = sorted(d.glob("linkdeck-agent*.deb")) if d.is_dir() else []
        if found:
            return found[-1]
    return None


async def h_state(req: web.Request) -> web.Response:
    await refresh_devices()
    return ok(tools=S.tools, devices=S.devices, clips=S.clips, debian=public_debian(),
              save_dir=str(SAVE_DIR), sync_dir=str(SYNC_DIR), sessions=public_sessions(),
              version=VERSION, agent_pkg=find_agent_deb() is not None, settings=S.settings,
              pairings=public_pairings(), notifs=S.notifs[:30],
              discovered=[{k: v for k, v in e.items() if k != "fp"} for e in S.discovered.values()],
              sync=S.sync_info, kvm={"on": S.kvm_on, "captured": bool(S.kvm and S.kvm.captured)})


async def h_tools(req: web.Request) -> web.Response:
    return ok(tools=await detect_tools())


async def h_settings(req: web.Request) -> web.Response:
    d = await req.json()
    for k in DEFAULT_SETTINGS:
        if k in d:
            S.settings[k] = bool(d[k])
    save_json(user_data_dir() / "settings.json", S.settings)
    return ok(settings=S.settings)


async def h_agent_push(req: web.Request) -> web.Response:
    d = await req.json()
    serial, deb = d.get("serial", ""), find_agent_deb()
    if not deb:
        return fail("Paket agen tidak ditemukan. Jalankan: python build/build_agent_deb.py")
    if not serial:
        return fail("Sambungkan HP lewat kabel atau Wi-Fi dulu (bagian Android).")
    await run("adb", "-s", serial, "shell", "mkdir", "-p", ANDROID_DROP)
    dest = f"{ANDROID_DROP}/linkdeck-agent.deb"
    c, _, e = await run("adb", "-s", serial, "push", str(deb), dest, timeout=120)
    if c:
        return fail(f"Gagal mengirim paket: {e.strip()[:200]}")
    return ok(path=dest, cmd=f"sudo apt install {dest}")


# ================================================================ HTTP: Android

async def h_pair(req: web.Request) -> web.Response:
    d = await req.json()
    host, code = d.get("host", "").strip(), d.get("code", "").strip()
    if not re.match(r"^[\w.\-]+:\d+$", host) or not code.isdigit():
        return fail("Isi IP:port dan kode 6 digit dari layar Debugging nirkabel.")
    c, out, err = await run("adb", "pair", host, code, timeout=30)
    msg = (out + err).strip()
    if c or "Successfully" not in msg:
        return fail(f"Pairing gagal: {msg or 'adb tidak memberi pesan'}")
    return ok(msg=msg)


async def h_connect(req: web.Request) -> web.Response:
    d = await req.json()
    host = d.get("host", "").strip()
    if not re.match(r"^[\w.\-]+(:\d+)?$", host):
        return fail("Alamat tidak valid. Contoh: 192.168.1.23:37199")
    if ":" not in host:
        host += ":5555"
    _, out, err = await run("adb", "connect", host, timeout=15)
    msg = (out + err).strip()
    if "connected to" not in msg:
        return fail(f"Tidak tersambung: {msg}")
    await refresh_devices()
    return ok(msg=msg, serial=host)


async def h_disconnect(req: web.Request) -> web.Response:
    serial = (await req.json()).get("serial", "")
    if classify(serial) == "usb":
        return fail("Perangkat USB diputus dengan mencabut kabel.")
    await run("adb", "disconnect", serial, timeout=10)
    if S.adb_targets.pop(serial, None):
        save_json(user_data_dir() / "adb-targets.json", S.adb_targets)
    await refresh_devices()
    return ok()


SKIP_IFACES = ("lo", "rmnet", "r_rmnet", "v4-rmnet", "ccmni", "dummy", "tun", "ip6tnl", "sit", "ifb", "seth")


def parse_ifaces(text: str) -> list[tuple[str, str]]:
    """Ambil (antarmuka, IPv4) dari keluaran `ip -o -4 addr` atau `ifconfig` Android."""
    out = []
    for m in re.finditer(r"^\d+:\s+(\S+?)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/\d+", text, re.M):
        out.append((m.group(1), m.group(2)))
    if not out:   # format ifconfig
        cur = None
        for line in text.splitlines():
            if line and not line[0].isspace():
                cur = line.split()[0]
            m = re.search(r"inet addr:(\d+\.\d+\.\d+\.\d+)", line)
            if cur and m:
                out.append((cur, m.group(1)))
    return [(i, a) for i, a in out if not i.startswith(SKIP_IFACES) and not a.startswith("127.")]


def iface_kind(name: str) -> str:
    return "bt" if name.startswith(("bt-pan", "bnep", "bt")) else "wifi"


def local_ip_for(ip: str) -> str:
    """IP laptop yang dipakai untuk menuju `ip` (tanpa mengirim paket)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
            u.connect((ip, 9))
            return u.getsockname()[0]
    except OSError:
        return ""


def same_net(a: str, b: str) -> bool:
    return a.rsplit(".", 1)[0] == b.rsplit(".", 1)[0]


async def h_tcpip(req: web.Request) -> web.Response:
    """Satu tombol: lewat kabel, pindahkan adb ke jaringan (Bluetooth/Wi-Fi) lalu sambungkan."""
    d = await req.json()
    prefer = d.get("prefer", "bt")
    usb = [x for x in S.devices if x["state"] == "device" and x["transport"] == "usb"]
    serial = d.get("serial") if any(x["serial"] == d.get("serial") for x in usb) else (usb[0]["serial"] if usb else "")
    if not serial:
        return fail("Colok HP ke laptop pakai kabel dulu (sekali saja), lalu klik tombol ini lagi.")
    _, out, _ = await run("adb", "-s", serial, "shell", "ip", "-o", "-4", "addr", "show", timeout=10)
    ifaces = parse_ifaces(out)
    if not ifaces:
        _, out, _ = await run("adb", "-s", serial, "shell", "ifconfig", timeout=10)
        ifaces = parse_ifaces(out)
    if not ifaces:
        msg = ("Tethering Bluetooth di HP belum menyala." if prefer == "bt"
               else "HP belum tersambung ke Wi-Fi.")
        return fail(f"HP belum punya jaringan yang bisa dijangkau laptop. {msg}")
    # bisa dijangkau langsung = laptop punya alamat di jaringan yang sama dengan antarmuka HP itu
    direct = {ip for _, ip in ifaces if same_net(local_ip_for(ip), ip)}
    ifaces.sort(key=lambda t: (iface_kind(t[0]) != prefer, t[1] not in direct))
    reachable = [t for t in ifaces if t[1] in direct]

    c, out, err = await run("adb", "-s", serial, "tcpip", "5555", timeout=15)
    if c:
        return fail(f"HP menolak mode jaringan: {(out + err).strip()[:200]}")
    await asyncio.sleep(2.5)

    tried = []
    for name, ip in (reachable or ifaces):
        addr = f"{ip}:5555"
        tried.append(addr)
        for _ in range(3 if reachable else 1):
            _, out, err = await run("adb", "connect", addr, timeout=8)
            if "connected to" in (out + err):
                kind = iface_kind(name)
                S.adb_targets[addr] = kind
                save_json(user_data_dir() / "adb-targets.json", S.adb_targets)
                await refresh_devices()
                await log(f"Android siap lewat {'Bluetooth' if kind == 'bt' else 'Wi-Fi'} di {addr}. Kabel boleh dicabut.")
                return ok(serial=addr, transport=kind)
            await asyncio.sleep(1.5)
    if not reachable:
        hint = ("Laptop belum tergabung ke jaringan Bluetooth HP. Tekan Win+R, ketik control printers, "
                "klik kanan HP → Connect using → Access point, lalu klik tombol ini lagi."
                if prefer == "bt" else
                "Laptop dan HP belum di Wi-Fi yang sama. Sambungkan keduanya ke Wi-Fi yang sama, lalu coba lagi.")
        return fail(hint)
    return fail(f"HP sudah siap di {', '.join(tried)}, tapi laptop belum bisa menyambung. Coba lagi beberapa detik lagi.")


async def adb_reconnect_loop() -> None:
    """Sambungkan ulang otomatis ke HP yang pernah disiapkan lewat tombol (sampai HP di-restart)."""
    while True:
        await asyncio.sleep(10)
        if not S.tools.get("adb") or not S.adb_targets:
            continue
        present = {d["serial"] for d in S.devices}
        for addr in list(S.adb_targets):
            if addr not in present:
                await run("adb", "connect", addr, timeout=5)


async def h_apps(req: web.Request) -> web.Response:
    d = await req.json()
    serial = d.get("serial", "")
    if not serial:
        return fail("Pilih perangkat Android dulu.")
    if serial in S.apps and not d.get("refresh"):
        return ok(apps=S.apps[serial])
    apps = []
    if S.tools.get("scrcpy"):
        _, out, err = await run("scrcpy", f"--serial={serial}", "--list-apps", timeout=40)
        apps = notif.parse_apps(out + "\n" + err)
    if not apps:
        _, out, _ = await run("adb", "-s", serial, "shell", "pm", "list", "packages", "-3", timeout=15)
        apps = [{"label": p.split(":", 1)[1].rsplit(".", 1)[-1].capitalize(), "pkg": p.split(":", 1)[1],
                 "system": False} for p in out.split() if p.startswith("package:")]
    S.apps[serial] = apps
    return ok(apps=apps)


async def watch_session(sid: str, proc: asyncio.subprocess.Process) -> None:
    tail: list[str] = []
    assert proc.stdout
    async for raw in proc.stdout:
        line = raw.decode(errors="replace").rstrip()
        if not line:
            continue
        tail = (tail + [line])[-8:]
        if line.startswith(("ERROR", "WARN")):
            await log(f"scrcpy: {line}", "error" if line.startswith("ERROR") else "warn")
    code = await proc.wait()
    sess = S.sessions.pop(sid, None)
    stopped = sid in S.stopping
    S.stopping.discard(sid)
    if code != 0 and not stopped:
        await log(f"Tampilan '{(sess or {}).get('label', sid)}' berhenti (kode {code}). "
                  + (tail[-1] if tail else ""), "error")
    await broadcast({"type": "sessions", "sessions": public_sessions()})
    await refresh_devices()


def build_scrcpy_args(d: dict, label: str) -> list[str]:
    serial, mode, preset = d["serial"], d.get("mode", "virtual"), d.get("preset", "wifi")
    args = ["scrcpy", f"--serial={serial}", f"--window-title=LinkDeck – {label}"]
    args += [a for a in PRESETS.get(preset, PRESETS["wifi"])
             if not (mode == "camera" and a.startswith("--max-size"))]
    if mode == "camera":
        args += ["--video-source=camera", f"--camera-facing={d.get('facing', 'back')}"]
        size = str(d.get("camera_size") or "1920x1080")
        if re.match(r"^\d+x\d+$", size):
            args.append(f"--camera-size={size}")
        if d.get("torch"):
            args.append("--camera-torch")
        zoom = float(d.get("zoom") or 1)
        if zoom > 1:
            args.append(f"--camera-zoom={zoom:.1f}")
        sink = d.get("v4l2")
        if sink and sys.platform.startswith("linux") and re.match(r"^/dev/video\d+$", sink):
            args += [f"--v4l2-sink={sink}"]
            if d.get("hide_window"):
                args.append("--no-video-playback")
        if not d.get("audio"):
            args.append("--no-audio")
    else:
        if mode == "virtual":
            w = max(320, min(7680, int(d.get("width", 1920))))
            h = max(240, min(4320, int(d.get("height", 1080))))
            dpi = max(80, min(640, int(d.get("dpi", 160))))
            args.append(f"--new-display={w}x{h}/{dpi}")
            if d.get("flex") and S.tools.get("flex") and preset != "bt":
                args.append("--flex-display")
            app = (d.get("app") or "").strip()
            if app:
                if not re.match(r"^[+?]{0,2}[\w.\- ]+$", app):
                    raise ValueError("Nama aplikasi tidak valid, contoh: com.whatsapp")
                args.append(f"--start-app={app}")
            if d.get("no_decor"):
                args.append("--no-vd-system-decorations")
        elif d.get("screen_off"):
            args.append("--turn-screen-off")
        if d.get("keep_active"):
            args.append("--keep-active" if S.tools.get("flex") else "--stay-awake")
        if d.get("gamepad"):
            args.append("--gamepad=uhid")
        if not d.get("audio", True) and "--no-audio" not in args:
            args.append("--no-audio")
    if d.get("window_x") is not None and d.get("window_y") is not None:
        args += [f"--window-x={int(d['window_x'])}", f"--window-y={int(d['window_y'])}"]
    if d.get("fullscreen"):
        args.append("--fullscreen")
    if d.get("record"):
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        args.append(f"--record={SAVE_DIR / time.strftime('rekaman-%Y%m%d-%H%M%S.mp4')}")
    return args


async def h_mirror_start(req: web.Request) -> web.Response:
    if not S.tools.get("scrcpy"):
        return fail("scrcpy belum terpasang.")
    d = await req.json()
    serial, mode = d.get("serial", ""), d.get("mode", "virtual")
    if not serial:
        return fail("Pilih perangkat Android dulu.")
    if mode == "virtual" and not S.tools.get("virtual_display"):
        return fail("Layar virtual butuh scrcpy 3.0 atau lebih baru.")
    if mode in ("mirror", "camera") and any(s["serial"] == serial and s["mode"] == mode
                                            for s in S.sessions.values()):
        return fail("Mode ini sudah berjalan untuk perangkat ini.")
    dev = next((x for x in S.devices if x["serial"] == serial), {})
    label = d.get("label") or {"camera": "Kamera", "mirror": "Cermin"}.get(mode) or dev.get("model", serial)
    try:
        args = build_scrcpy_args(d, label)
    except ValueError as e:
        return fail(str(e))
    proc = await asyncio.create_subprocess_exec(*args, stdout=PIPE, stderr=STDOUT, creationflags=NOWIN)
    sid = secrets.token_hex(4)
    S.sessions[sid] = {"serial": serial, "mode": mode, "label": label, "proc": proc}
    asyncio.create_task(watch_session(sid, proc))
    print("scrcpy:", " ".join(shlex.quote(a) for a in args[1:]), flush=True)
    await broadcast({"type": "sessions", "sessions": public_sessions()})
    await refresh_devices()
    return ok(id=sid)


async def h_mirror_stop(req: web.Request) -> web.Response:
    d = await req.json()
    ids = [d["id"]] if d.get("id") else [k for k, v in S.sessions.items() if v["serial"] == d.get("serial")]
    if not ids:
        return fail("Tidak ada tampilan yang berjalan.")
    for sid in ids:
        sess = S.sessions.get(sid)
        if sess:
            S.stopping.add(sid)
            sess["proc"].terminate()
    return ok()


async def h_screenshot(req: web.Request) -> web.Response:
    serial = (await req.json()).get("serial", "")
    if not serial:
        return fail("Pilih perangkat Android dulu.")
    c, png = await run_bytes("adb", "-s", serial, "exec-out", "screencap", "-p", timeout=20)
    if c or not png.startswith(b"\x89PNG"):
        return fail("Tangkapan layar gagal. Pastikan HP tidak terkunci.")
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = unique_path(SAVE_DIR / time.strftime("layar-%Y%m%d-%H%M%S.png"))
    path.write_bytes(png)
    return ok(path=str(path), data="data:image/png;base64," + base64.b64encode(png).decode())


# ================================================================ HTTP: Debian

async def h_debian_connect(req: web.Request) -> web.Response:
    d = await req.json()
    if d.get("id") and d["id"] in S.discovered:
        e = S.discovered[d["id"]]
        transport, host, serial = e["transport"], e["host"], e.get("serial")
    else:
        transport, host, serial = d.get("transport", "wifi"), d.get("host", "").strip(), d.get("serial")
    S.connecting = True
    try:
        deb = await connect_debian(transport, host, serial, str(d.get("pin", "")).strip(),
                                   remember=d.get("remember", True))
    except ValueError as e:
        return fail(str(e))
    finally:
        S.connecting = False
    return ok(debian=deb)


async def h_debian_disconnect(req: web.Request) -> web.Response:
    await stop_debian()
    await broadcast({"type": "debian", "debian": None})
    return ok()


async def h_pairing_password(req: web.Request) -> web.Response:
    """POST {password, remember}: simpan sandi VNC untuk perangkat yang sedang tersambung.
       POST {} : ambil sandi tersimpan."""
    d = await req.json()
    if not S.debian:
        return fail("Debian belum tersambung.")
    entry = S.pairings.setdefault(S.debian["id"], {"name": S.debian["name"], "fp": S.debian["fp"]})
    if "password" in d:
        if d.get("remember", True):
            entry["password"] = d["password"]
        else:
            entry.pop("password", None)
        save_pairings()
        return ok()
    return ok(password=entry.get("password", ""))


async def h_pairing_forget(req: web.Request) -> web.Response:
    aid = (await req.json()).get("id", "")
    S.pairings.pop(aid, None)
    S.sync_state.pop(aid, None)
    save_pairings()
    save_json(user_data_dir() / "sync-state.json", S.sync_state)
    if aid in S.discovered:
        S.discovered[aid]["paired"] = False
    await broadcast({"type": "pairings", "pairings": public_pairings()})
    await broadcast_discovered()
    return ok()


async def relay_ws(req: web.Request, path: str, query: str = "", count: bool = False) -> web.StreamResponse:
    """Teruskan WebSocket browser <-> agen Debian (wss)."""
    if not S.debian:
        return web.Response(status=409, text="Debian belum terhubung")
    ws = web.WebSocketResponse(protocols=("binary",), max_msg_size=0)
    await ws.prepare(req)
    try:
        async with ClientSession() as sess:
            async with sess.ws_connect(agent_url(path) + query, ssl=agent_ssl(S.debian["fp"]),
                                       max_msg_size=0, timeout=8) as up:
                async def down():
                    async for m in up:
                        if m.type == WSMsgType.BINARY:
                            if count:
                                S.vnc_bytes += len(m.data)
                            await ws.send_bytes(m.data)
                        elif m.type == WSMsgType.TEXT:
                            await ws.send_str(m.data)
                        else:
                            break
                    await ws.close()

                task = asyncio.create_task(down())
                try:
                    async for m in ws:
                        if m.type == WSMsgType.BINARY:
                            await up.send_bytes(m.data)
                        elif m.type == WSMsgType.TEXT:
                            await up.send_str(m.data)
                        else:
                            break
                finally:
                    task.cancel()
    except Exception as e:
        if not ws.closed:
            await ws.close(message=str(e)[:100].encode())
    return ws


async def ws_vnc(req):
    return await relay_ws(req, "/vnc", count=True)


async def ws_term(req):
    return await relay_ws(req, "/term")


async def ws_audio(req):
    q = req.query.get("q", "high")
    return await relay_ws(req, "/audio", f"&q={q if q in ('low', 'mid', 'high') else 'high'}")


async def ext_vnc_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Jembatan TCP lokal -> terowongan VNC TLS (untuk TigerVNC viewer)."""
    try:
        async with ClientSession() as sess:
            async with sess.ws_connect(agent_url("/vnc"), ssl=agent_ssl(S.debian["fp"]), max_msg_size=0) as up:
                async def down():
                    async for m in up:
                        if m.type != WSMsgType.BINARY:
                            break
                        writer.write(m.data)
                        await writer.drain()
                    writer.close()
                task = asyncio.create_task(down())
                while data := await reader.read(65536):
                    await up.send_bytes(data)
                task.cancel()
    except Exception:
        pass
    finally:
        writer.close()


async def h_debian_external(req: web.Request) -> web.Response:
    if not S.debian:
        return fail("Hubungkan desktop Debian dulu.")
    if not S.tools.get("vncviewer"):
        return fail("TigerVNC viewer (vncviewer) belum terpasang di PC.")
    if not S.ext_vnc:
        S.ext_vnc = await asyncio.start_server(ext_vnc_client, "127.0.0.1", EXT_VNC_PORT)
    d = await req.json()
    args = ["vncviewer", f"127.0.0.1::{EXT_VNC_PORT}"]
    if d.get("fullscreen"):
        args.append("-FullScreen")
        mon = int(d.get("monitor") or 0)
        if mon > 0:
            args += ["-FullScreenMode=Selected", f"-FullScreenSelectedMonitors={mon}"]
    await asyncio.create_subprocess_exec(*args, creationflags=NOWIN)
    return ok()


async def h_resolution(req: web.Request) -> web.Response:
    size = str((await req.json()).get("size", ""))
    if not re.match(r"^\d{3,4}x\d{3,4}$", size):
        return fail("Format resolusi tidak valid.")
    if not await send_agent({"type": "resolution", "size": size}):
        return fail("Agen Debian belum tersambung.")
    return ok()


async def h_sync_now(req: web.Request) -> web.Response:
    if not S.agent_ws:
        return fail("Agen Debian belum tersambung.")
    n = await sync_once()
    S.sync_info.update({"last": time.time(), "dir": str(SYNC_DIR)})
    return ok(changed=n, dir=str(SYNC_DIR))


async def h_open_sync(req: web.Request) -> web.Response:
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(SYNC_DIR))  # noqa: S606
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(SYNC_DIR)])
    return ok()


# ================================================================ HTTP: clipboard, berkas, tautan

async def h_clipboard(req: web.Request) -> web.Response:
    d = await req.json()
    text = str(d.get("text", ""))
    if not text:
        return fail("Teks kosong.")
    if d.get("src") == "debian-viewer":
        if text != S.last_clip:
            S.last_clip = text
            await set_pc_clip(text)
            await add_clip(text, "debian")
        return ok()
    S.last_clip = text
    await set_pc_clip(text)
    sent = await send_agent({"type": "clip", "text": text})
    await add_clip(text, "pc")
    return ok(debian=sent)


async def h_files(req: web.Request) -> web.Response:
    reader = await req.multipart()
    target, serial, done = "android", None, []
    tmp_dir = SAVE_DIR / ".kirim"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    async for part in reader:
        if part.name == "target":
            target = (await part.text()).strip()
            continue
        if part.name == "serial":
            serial = (await part.text()).strip()
            continue
        if part.name != "file" or not part.filename:
            continue
        name = safe_name(part.filename)
        tmp = tmp_dir / f"{secrets.token_hex(4)}-{name}"
        size = 0
        with tmp.open("wb") as fh:
            while chunk := await part.read_chunk(1 << 20):
                size += len(chunk)
                fh.write(chunk)
        try:
            if target == "android":
                if not serial:
                    return fail("Pilih perangkat Android dulu.")
                await run("adb", "-s", serial, "shell", "mkdir", "-p", ANDROID_DROP)
                c, _, e = await run("adb", "-s", serial, "push", str(tmp), f"{ANDROID_DROP}/{name}", timeout=600)
                if c:
                    return fail(f"Gagal mengirim {name}: {e.strip()[:200]}")
            else:
                if size > MAX_AGENT_FILE:
                    return fail(f"{name} lebih dari 48 MB. Kirim ke Android, lalu buka dari /sdcard di Debian.")
                if not await send_agent({"type": "file", "name": name,
                                         "data": base64.b64encode(tmp.read_bytes()).decode()}):
                    return fail("Agen Debian belum tersambung.")
            done.append(name)
        finally:
            tmp.unlink(missing_ok=True)
    if not done:
        return fail("Tidak ada berkas yang diterima.")
    where = ANDROID_DROP if target == "android" else "~/Downloads/LinkDeck (Debian)"
    return ok(files=done, where=where)


async def h_link(req: web.Request) -> web.Response:
    d = await req.json()
    url = d.get("url", "").strip()
    if not re.match(r"^https?://\S+$", url):
        return fail("Tautan harus diawali http:// atau https://")
    if d.get("target") == "debian":
        return ok() if await send_agent({"type": "open", "url": url}) else fail("Agen Debian belum tersambung.")
    serial = d.get("serial", "")
    if not serial:
        return fail("Pilih perangkat Android dulu.")
    c, _, e = await run("adb", "-s", serial, "shell", "am", "start", "-a", "android.intent.action.VIEW",
                        "-d", shlex.quote(url))
    return fail(f"Tautan gagal dibuka: {e.strip()[:200]}") if c else ok()


async def ws_events(req: web.Request) -> web.StreamResponse:
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(req)
    S.ui.add(ws)
    try:
        async for _ in ws:
            pass
    finally:
        S.ui.discard(ws)
    return ws


# ================================================================ tugas latar

def due(key: str, every: float) -> bool:
    now = time.time()
    if now - S.polled.get(key, 0) >= every:
        S.polled[key] = now
        return True
    return False


async def stats_loop() -> None:
    tick = 0
    while True:
        try:
            await refresh_devices()
            payload = {}
            for dev in S.devices:
                if dev["state"] != "device":
                    continue
                s = S.stats.setdefault(dev["serial"], {"lat": [], "bat": [], "temp": None})
                poll = POLL.get(dev["transport"], POLL["wifi"])
                if due("lat:" + dev["serial"], poll["lat"]):
                    t0 = time.perf_counter()
                    c, _, _ = await run("adb", "-s", dev["serial"], "shell", "echo", "1", timeout=8)
                    if c == 0:
                        s["lat"] = (s["lat"] + [round((time.perf_counter() - t0) * 1000)])[-30:]
                if due("bat:" + dev["serial"], poll["bat"]):
                    _, out, _ = await run("adb", "-s", dev["serial"], "shell", "dumpsys", "battery", timeout=6)
                    lv, tp = re.search(r"level:\s*(\d+)", out), re.search(r"temperature:\s*(\d+)", out)
                    if lv:
                        s["bat"] = (s["bat"] + [int(lv.group(1))])[-30:]
                    if tp:
                        s["temp"] = int(tp.group(1)) / 10
                payload[dev["serial"]] = s
            S.vnc_rate = (S.vnc_rate + [round(S.vnc_bytes / 3 / 1024, 1)])[-40:]
            S.vnc_bytes = 0
            await broadcast({"type": "stats", "devices": payload, "vnc": S.vnc_rate, "debian": S.debian_info})
        except Exception as e:
            print("stats:", e, flush=True)
        tick += 1
        await asyncio.sleep(3)


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "linkdeck"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _download_novnc() -> None:
    if (NOVNC_DIR / "core" / "rfb.js").exists():
        return
    data = _fetch(NOVNC_URL)
    prefix = f"noVNC-{NOVNC_VERSION}/"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.startswith(prefix):
                continue
            rel = m.name[len(prefix):]
            if ".." in rel or not (rel.startswith(("core/", "vendor/")) or rel == "LICENSE.txt"):
                continue
            dest = NOVNC_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(m)
            if src:
                dest.write_bytes(src.read())


def _download_xterm() -> None:
    if (XTERM_DIR / "xterm.js").exists():
        return
    XTERM_DIR.mkdir(parents=True, exist_ok=True)
    for url, files in XTERM_PKGS.values():
        with tarfile.open(fileobj=io.BytesIO(_fetch(url)), mode="r:gz") as tf:
            for src, dst in files.items():
                (XTERM_DIR / dst).write_bytes(tf.extractfile(src).read())


def download_assets() -> None:
    _download_novnc()
    _download_xterm()


async def assets_task() -> None:
    if S.tools.get("novnc") and S.tools.get("xterm"):
        return
    try:
        await asyncio.to_thread(download_assets)
        S.tools["novnc"] = S.tools["xterm"] = True
        await broadcast({"type": "tools", "tools": S.tools})
    except Exception as e:
        await log(f"Komponen penampil gagal diunduh ({e}). Desktop & terminal Debian di jendela "
                  "ini belum tersedia.", "warn")


async def on_startup(app: web.Application) -> None:
    S.loop = asyncio.get_running_loop()
    await detect_tools()
    S.tasks = [asyncio.create_task(t()) for t in (clip_watcher, stats_loop, assets_task, discovery_loop,
                                                  sync_loop, notif_loop, adb_reconnect_loop)]
    if OPEN_BROWSER and "--no-browser" not in sys.argv:
        asyncio.get_running_loop().call_later(0.8, webbrowser.open, f"http://{HOST}:{PORT}/")


async def on_shutdown(app: web.Application) -> None:
    for sid, sess in list(S.sessions.items()):
        S.stopping.add(sid)
        sess["proc"].terminate()
    await stop_debian()
    for t in S.tasks:
        t.cancel()
    for ws in list(S.ui):
        await ws.close()
    if S.tools.get("adb"):
        await run("adb", "forward", "--remove", f"tcp:{LOCAL_AGENT_PORT}", timeout=5)
        if FROZEN:
            await run("adb", "kill-server", timeout=5)


@web.middleware
async def guard(req: web.Request, handler):
    if req.path.startswith("/api/") and req.headers.get("X-LinkDeck-Token") != TOKEN:
        return fail("Token sesi tidak cocok. Muat ulang halaman.", 403)
    if req.path.startswith("/ws/") and req.query.get("t") != TOKEN:
        return web.Response(status=403)
    return await handler(req)


def build_app() -> web.Application:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    for d in (NOVNC_DIR, XTERM_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    app = web.Application(middlewares=[guard], client_max_size=4 * 1024 ** 3)
    r = app.router
    r.add_get("/", h_index)
    r.add_get("/api/state", h_state)
    r.add_post("/api/tools", h_tools)
    r.add_post("/api/settings", h_settings)
    r.add_post("/api/adb/pair", h_pair)
    r.add_post("/api/adb/connect", h_connect)
    r.add_post("/api/adb/disconnect", h_disconnect)
    r.add_post("/api/adb/tcpip", h_tcpip)
    r.add_post("/api/apps", h_apps)
    r.add_post("/api/mirror/start", h_mirror_start)
    r.add_post("/api/mirror/stop", h_mirror_stop)
    r.add_post("/api/screenshot", h_screenshot)
    r.add_post("/api/agent/push", h_agent_push)
    r.add_post("/api/debian/connect", h_debian_connect)
    r.add_post("/api/debian/disconnect", h_debian_disconnect)
    r.add_post("/api/debian/external", h_debian_external)
    r.add_post("/api/pairing/password", h_pairing_password)
    r.add_post("/api/pairing/forget", h_pairing_forget)
    r.add_post("/api/sync/now", h_sync_now)
    r.add_post("/api/debian/resolution", h_resolution)
    r.add_post("/api/sync/open", h_open_sync)
    r.add_post("/api/kvm", h_kvm)
    r.add_post("/api/clipboard", h_clipboard)
    r.add_post("/api/files", h_files)
    r.add_post("/api/link", h_link)
    r.add_get("/ws/events", ws_events)
    r.add_get("/ws/vnc", ws_vnc)
    r.add_get("/ws/term", ws_term)
    r.add_get("/ws/audio", ws_audio)
    r.add_static("/novnc", NOVNC_DIR)
    r.add_static("/xterm", XTERM_DIR)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


def main() -> None:
    print(f"LinkDeck {VERSION} berjalan di http://{HOST}:{PORT}/  (Ctrl+C untuk berhenti)")
    web.run_app(build_app(), host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    main()
