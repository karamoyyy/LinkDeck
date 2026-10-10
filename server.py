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
import queue
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
import pcclip  # noqa: E402
import richclip  # noqa: E402
import debiantools  # noqa: E402
import mediadev  # noqa: E402
import companionlink  # noqa: E402

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
# HP ini sendiri (LinkDeck di Debian HP): encoder & tampilan berbagi satu prosesor, jadi dibuat ringan
PRESETS["local"] = ["--video-bit-rate=4M", "--max-size=1280", "--max-fps=30"]
# Kualitas VNC (noVNC) per jalur: (kualitas JPEG 0-9, kompresi 0-9)
VNC_QUALITY = {"usb": (8, 1), "wifi": (6, 2), "bt": (2, 9), "local": (8, 1)}
# Seberapa sering adb ditanya (detik) per jalur: Bluetooth jauh lebih jarang agar tidak memakan bandwidth
POLL = {"usb": {"lat": 3, "bat": 15, "notif": 6}, "wifi": {"lat": 3, "bat": 30, "notif": 8},
        "local": {"lat": 5, "bat": 30, "notif": 8},
        "bt": {"lat": 15, "bat": 120, "notif": 25}}
NOTIF_CMD = r"dumpsys notification --noredact | grep -E '^  [^ ]|NotificationRecord\(|android\.(title|text|bigText)='"
DEVICE_GRACE = 10   # detik: perangkat yang hilang sesaat tetap ditampilkan (cegah UI berkedip)
DEFAULT_SETTINGS = {"autoconnect": True, "sync": True, "notif": True, "clip_android": True, "clip_rich": True}
# pengaturan tahap 1 (diubah lewat /api/prefs di features.py)
EXTRA_SETTINGS = {"theme": "auto", "zoom": 1, "privacy": False, "auto_privacy": True, "auto_update": True,
                  "hotkeys": False, "sendto": False, "dock": [], "onboarded": False, "tray": True, "lang": "",
                  "mic_target": "virtual", "mic_clean": True, "mic_monitor": False, "companion": True,
                  "wiz_what": "android"}
DESKTOP = None          # app.Desktop: jendela & ikon tray (None bila dijalankan lewat python server.py)


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
        saved = load_json(user_data_dir() / "settings.json", {})
        self.settings: dict = {**DEFAULT_SETTINGS, **EXTRA_SETTINGS, **saved}
        if saved and not saved.get("lang"):
            self.settings["lang"] = "id"   # pengguna lama (sebelum 1.11): tetap Bahasa Indonesia
        self.update_info: dict | None = None
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
        self.android_clips: dict = {}
        self.clip_recent: dict[str, float] = {}
        self.pcclip = None                 # pcclip.PCClipboard, dibuat saat start
        self.sdk: dict[str, int] = {}      # versi API Android per perangkat
        self.camera_info: dict[str, dict] = {}
        self.games: dict = {}
        self.welcomed = False              # notifikasi panduan: sekali per aplikasi dibuka
        self.net_cache: tuple[float, list] = (0.0, [])
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
    if serial.startswith(("127.0.0.1:", "localhost:")):
        return "local"                  # LinkDeck di Debian pada HP yang sama
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

def bundled_scrcpy() -> bool:
    exe = shutil.which("scrcpy")
    return bool(exe) and Path(exe).resolve().parent == BIN.resolve()


async def scrcpy_version(timeout: float = 15) -> str | None:
    """Versi scrcpy. Untuk scrcpy bawaan LinkDeck dibaca dari berkas VERSION (tanpa menjalankan apa pun);
    selain itu dari `scrcpy --version` dengan batas waktu longgar (pemindai antivirus bisa memperlambat run pertama)."""
    vf = BIN / "VERSION"
    if bundled_scrcpy() and vf.is_file():
        v = vf.read_text().strip()
        if re.match(r"^\d+(\.\d+)+$", v):
            return v
    _, out, err = await run("scrcpy", "--version", timeout=timeout)
    m = re.search(r"scrcpy v?(\d+(?:\.\d+)+)", out + err)
    return m.group(1) if m else None


async def detect_tools() -> dict:
    t = {k: bool(shutil.which(k)) for k in ("adb", "scrcpy", "vncviewer")}
    t["clipboard"] = bool(S.pcclip and S.pcclip.available)
    t["scrcpy_version"] = None
    t["virtual_display"] = t["flex"] = False
    t["scrcpy_version_full"] = None
    if t["scrcpy"]:
        t["scrcpy_version_full"] = await scrcpy_version()
        m = re.match(r"(\d+)\.(\d+)", t["scrcpy_version_full"] or "")
        if m:
            major = int(m.group(1))
            t["scrcpy_version"] = f"{m.group(1)}.{m.group(2)}"
            t["virtual_display"] = major >= 3
            t["flex"] = major >= 4
    t["scrcpy_build_cmd"] = bool(shutil.which("linkdeck-scrcpy-build"))   # paket linkdeck-debian (mis. di HP)
    t["novnc"] = (NOVNC_DIR / "core" / "rfb.js").exists()
    t["xterm"] = (XTERM_DIR / "xterm.js").exists()
    t["v4l2"] = sorted(glob.glob("/dev/video*")) if sys.platform.startswith("linux") else []
    t["platform"] = sys.platform
    S.tools = t
    return t


async def scrcpy_version_retry() -> None:
    """Bila versi scrcpy belum terbaca saat start (mis. run pertama dipindai antivirus), coba lagi di latar."""
    while S.tools.get("scrcpy") and not S.tools.get("scrcpy_version_full"):
        await asyncio.sleep(20)
        v = await scrcpy_version(timeout=60)
        if v:
            await detect_tools()
            await broadcast({"type": "tools", "tools": S.tools})
            await log(f"scrcpy {v} siap.")


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
    pc = S.pcclip
    if not pc or not pc.available:
        return
    try:
        await asyncio.to_thread(pc.set, text)
        pc.error = None
    except Exception as e:
        pc.error = f"Tidak bisa menulis clipboard PC: {e}"
        if not S.clip_warned:
            S.clip_warned = True
            hint = " Pasang xclip atau wl-clipboard." if sys.platform.startswith("linux") else ""
            await log(pc.error + hint, "warn")
        await broadcast_clip_status()


ECHO_WINDOW = 6.0   # detik: isi lama yang muncul lagi dalam jendela ini dianggap gema, bukan salinan baru


def mark_current(text: str) -> None:
    S.last_clip = text
    now = time.time()
    S.clip_recent[text] = now
    for k in [k for k, t in S.clip_recent.items() if now - t > 60]:
        del S.clip_recent[k]


def is_stale_echo(text: str) -> bool:
    """True bila teks ini baru saja jadi isi clipboard lalu diganti — perangkat lain memantulkannya balik."""
    t = S.clip_recent.get(text)
    return t is not None and text != S.last_clip and time.time() - t < ECHO_WINDOW


async def add_clip(text: str, src: str, label: str | None = None) -> None:
    text = text[:20000]
    if S.clips and S.clips[0]["text"] == text:
        return
    item = {"id": secrets.token_hex(4), "text": text, "src": src, "label": label, "t": time.time()}
    S.clips.insert(0, item)
    del S.clips[40:]
    await broadcast({"type": "clip", "item": item})


async def clip_watcher() -> None:
    """Pantau clipboard PC. Di Windows/macOS hanya membaca saat penanda perubahan bergeser."""
    pc = S.pcclip
    if not pc or not pc.available:
        await broadcast_clip_status()
        return
    last_token = object()
    try:
        S.last_clip = await asyncio.to_thread(pc.get)
        last_token = await asyncio.to_thread(pc.token)
    except Exception:
        pass
    failing = False
    tick = 0
    try:
        await richclip.scan()                   # catat isi gambar/berkas yang sudah ada (tidak dikirim)
    except Exception:
        pass
    while True:
        await asyncio.sleep(0.5)
        tick += 1
        try:
            token = await asyncio.to_thread(pc.token)
            if token is not None and token == last_token:
                continue
            last_token = token
            # Windows: dicek tiap kali isi berubah; Linux (tanpa penanda): tiap 1 detik
            if token is not None or tick % 2 == 0:
                if await richclip.scan():
                    continue
            elif richclip.STATE["present"]:
                continue                        # masih berisi gambar/berkas: jangan kirim teks jalurnya
            text = await asyncio.to_thread(pc.get)
            if failing:
                failing, pc.error = False, None
                await broadcast_clip_status()
            if text and text != S.last_clip and not is_stale_echo(text):
                mark_current(text)
                richclip.STATE["own"] = None
                await add_clip(text, "pc")
                await send_agent({"type": "clip", "text": text})
                await android_set_clip(text)
        except asyncio.CancelledError:
            raise
        except Exception as e:      # jangan pernah berhenti memantau karena satu kegagalan
            if not failing:
                failing, pc.error = True, f"Tidak bisa membaca clipboard PC: {e}"
                print("[warn]", pc.error, flush=True)
                await broadcast_clip_status()
            await asyncio.sleep(1)


# ================================================================ jaringan laptop (untuk Bluetooth/Wi-Fi ke HP)

IPV4 = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")


def parse_ipconfig(text: str) -> list[dict]:
    """Baca keluaran `ipconfig` Windows (Inggris maupun Indonesia)."""
    nets, cur, want_gw = [], None, False
    for line in text.splitlines():
        if line and not line[0].isspace() and line.rstrip().endswith(":"):
            cur = {"name": line.strip().rstrip(":"), "ip": None, "gateway": None}
            cur["bt"] = "bluetooth" in cur["name"].lower()
            nets.append(cur)
            want_gw = False
            continue
        if cur is None:
            continue
        low = line.lower()
        if "ipv4" in low:
            m = IPV4.search(line.split(":", 1)[-1])
            if m:
                cur["ip"] = m.group(1)
            want_gw = False
        elif "gateway" in low:
            m = IPV4.search(line.split(":", 1)[-1])
            cur["gateway"] = m.group(1) if m else None
            want_gw = m is None                     # gateway IPv4 bisa ada di baris berikutnya
        elif want_gw and ":" not in line.strip()[:20]:
            m = IPV4.search(line)
            if m:
                cur["gateway"], want_gw = m.group(1), False
        else:
            want_gw = False
    return [n for n in nets if n["ip"]]


def linux_networks_fallback() -> list[dict]:
    """Tanpa perintah `ip`: IP lewat ioctl SIOCGIFCONF, gateway dari /proc/net/route."""
    import array
    import fcntl
    import struct
    nets = []
    try:
        gws = {}
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            f = line.split()
            if len(f) > 2 and f[1] == "00000000":
                gws[f[0]] = socket.inet_ntoa(struct.pack("<L", int(f[2], 16)))
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        size = 40 if struct.calcsize("P") == 8 else 32
        buf = array.array("B", b"\0" * size * 32)
        n = struct.unpack("iL", fcntl.ioctl(sk.fileno(), 0x8912, struct.pack("iL", len(buf), buf.buffer_info()[0])))[0]
        raw = buf.tobytes()[:n]
        for i in range(0, n, size):
            dev = raw[i:i + 16].split(b"\0", 1)[0].decode(errors="replace")
            ip = socket.inet_ntoa(raw[i + 20:i + 24])
            if dev != "lo":
                nets.append({"name": dev, "ip": ip, "gateway": gws.get(dev),
                             "bt": dev.startswith(("bnep", "bt-pan", "pan"))})
        sk.close()
    except OSError:
        pass
    return nets


async def pc_networks() -> list[dict]:
    """Daftar jaringan laptop: nama, IP, gateway, dan apakah itu jaringan Bluetooth."""
    if time.time() - S.net_cache[0] < 8:
        return S.net_cache[1]
    nets: list[dict] = []
    try:
        if sys.platform == "win32":
            _, out, _ = await run("ipconfig", timeout=10)
            nets = parse_ipconfig(out)
        elif sys.platform.startswith("linux") and not shutil.which("ip"):
            nets = linux_networks_fallback()
        elif sys.platform.startswith("linux"):
            _, out, _ = await run("ip", "-4", "-o", "addr", "show", timeout=5)
            _, rt, _ = await run("ip", "-4", "route", timeout=5)
            for m in re.finditer(r"^\d+:\s+(\S+)\s+inet\s+(\S+)/", out, re.M):
                dev, ip = m.group(1), m.group(2)
                if dev == "lo":
                    continue
                gw = re.search(rf"default via (\S+) dev {re.escape(dev)}\b", rt)
                nets.append({"name": dev, "ip": ip, "gateway": gw.group(1) if gw else None,
                             "bt": dev.startswith(("bnep", "bt-pan", "pan"))})
        else:
            _, out, _ = await run("ifconfig", timeout=5)
            for m in re.finditer(r"^(\S+): .*?\n(?:\s+.*\n)*?\s+inet (\S+)", out, re.M):
                if m.group(1) != "lo0":
                    nets.append({"name": m.group(1), "ip": m.group(2), "gateway": None, "bt": False})
    except Exception as e:
        print("pc_networks:", e, flush=True)
    for n in nets:                                   # tethering Bluetooth Android biasanya 192.168.44.x
        if n["ip"].startswith("192.168.44."):
            n["bt"] = True
        if n["bt"] and not n["gateway"]:
            n["gateway"] = n["ip"].rsplit(".", 1)[0] + ".1"
    S.net_cache = (time.time(), nets)
    return nets


async def port_open(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        w.close()
        return True
    except Exception:
        return False


async def adb_probe_once() -> None:
    """
    Temukan Android yang adb-nya sudah aktif lewat jaringan (setelah "Siapkan lewat Bluetooth/Wi-Fi"),
    lalu sambungkan otomatis — termasuk lewat tethering Bluetooth tanpa perlu klik apa pun.
    """
    nets = await pc_networks()
    cands: dict[str, str] = {}
    if ON_PHONE:                         # Debian di HP: adb HP ini sendiri (setelah adb tcpip 5555)
        cands["127.0.0.1:5555"] = "local"
    for n in nets:
        if n["bt"] and n["gateway"]:
            cands[f"{n['gateway']}:5555"] = "bt"
    for e in S.discovered.values():
        if e["transport"] in ("wifi", "bt") and e.get("host"):
            cands.setdefault(f"{e['host']}:5555", e["transport"])
    present = {d["serial"] for d in S.devices if d["state"] == "device"}
    have_phone = any(d["transport"] in ("bt", "wifi") for d in S.devices if d["state"] == "device")
    for addr, kind in cands.items():
        if addr in present or (have_phone and addr not in S.adb_targets):
            continue
        host = addr.rsplit(":", 1)[0]
        if not await port_open(host, 5555):
            continue
        _, out, err = await run("adb", "connect", addr, timeout=10)
        if "connected to" in out + err:
            S.adb_targets[addr] = kind
            save_json(user_data_dir() / "adb-targets.json", S.adb_targets)
            await refresh_devices()
            await log(f"Android tersambung otomatis lewat "
                      f"{ {'bt': 'Bluetooth', 'local': 'HP ini (adb lokal)'}.get(kind, 'Wi-Fi') } ({addr}).")
    await broadcast({"type": "networks", "networks": nets})


async def adb_probe_loop() -> None:
    while True:
        await asyncio.sleep(6)
        if not S.tools.get("adb"):
            continue
        try:
            await adb_probe_once()
        except Exception as e:
            print("adb_probe_loop:", e, flush=True)


# ================================================================ clipboard Android (tanpa jendela)

ANDROID_CLIP_JAR = "/data/local/tmp/linkdeck-clip.jar"
CLIP_MAX = 200_000


ON_PHONE = sys.platform.startswith("linux") and os.uname().machine in ("aarch64", "armv7l", "armv8l", "arm64")


def server_jar() -> tuple[Path | None, str | None]:
    """scrcpy-server untuk Mode Game & jembatan clipboard, beserta versinya.
    Salinan bawaan LinkDeck (bin/scrcpy-server + bin/VERSION) diutamakan, sehingga fitur ini jalan
    apa pun versi scrcpy sistem — penting untuk paket Debian di HP (arm64)."""
    jar, ver = BIN / "scrcpy-server", BIN / "VERSION"
    if jar.is_file() and ver.is_file():
        return jar, ver.read_text().strip()
    return scrcpy_server_path(), S.tools.get("scrcpy_version_full")


def scrcpy_server_path() -> Path | None:
    cands = [os.environ.get("SCRCPY_SERVER_PATH", ""), str(BIN / "scrcpy-server")]
    exe = shutil.which("scrcpy")
    if exe:
        d = Path(exe).resolve().parent
        cands += [str(d / "scrcpy-server"), str(d.parent / "share" / "scrcpy" / "scrcpy-server")]
    cands += ["/usr/share/scrcpy/scrcpy-server", "/usr/local/share/scrcpy/scrcpy-server",
              "/opt/homebrew/share/scrcpy/scrcpy-server"]
    return next((Path(c) for c in cands if c and Path(c).is_file()), None)


class AndroidClip:
    """
    Menjalankan scrcpy-server di HP hanya dengan kanal kontrol (tanpa video, audio, atau jendela).
    Server itu punya izin shell untuk membaca clipboard Android dan mengirim setiap salinan baru;
    sebaliknya LinkDeck bisa mengisi clipboard HP. Protokol: scrcpy 4.x control channel.
    """

    def __init__(self, serial: str) -> None:
        self.serial = serial
        self.ok = False
        self.pushed = False
        self.writer: asyncio.StreamWriter | None = None
        self.proc: asyncio.subprocess.Process | None = None
        self.port: int | None = None
        self.error: str | None = None
        self.tail: list[str] = []          # keluaran terakhir server di HP, untuk diagnosa
        self.task = asyncio.create_task(self.run())

    async def _read_output(self) -> None:
        try:
            async for raw in self.proc.stdout:
                line = raw.decode(errors="replace").strip()
                if line:
                    self.tail = (self.tail + [line])[-6:]
                    print(f"[clip {self.serial}] {line}", flush=True)
        except Exception:
            pass

    async def run(self) -> None:
        delay = 2.0
        while True:
            try:
                await self.session()
                delay = 2.0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                msg = str(e) or e.__class__.__name__
                if self.tail:
                    msg += " | " + self.tail[-1]
                self.error = msg[:240]
            finally:
                await self.close()
            await broadcast_clip_status()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

    async def session(self) -> None:
        jar, version = server_jar()
        if not jar or not version:
            raise RuntimeError("scrcpy-server tidak ditemukan")
        if not self.pushed:
            c, _, e = await run("adb", "-s", self.serial, "push", str(jar), ANDROID_CLIP_JAR, timeout=60)
            if c:
                raise RuntimeError(f"gagal mengirim server: {e.strip()[:120]}")
            self.pushed = True
        scid = f"{secrets.randbelow(0x7FFFFFFF):08x}"
        c, out, e = await run("adb", "-s", self.serial, "forward", "tcp:0", f"localabstract:scrcpy_{scid}", timeout=10)
        if c or not out.strip().isdigit():
            raise RuntimeError(f"adb forward gagal: {(out + e).strip()[:120]}")
        self.port = int(out.strip())
        cmd = (f"CLASSPATH={ANDROID_CLIP_JAR} app_process / com.genymobile.scrcpy.Server {version} "
               f"scid={scid} log_level=warn video=false audio=false control=true tunnel_forward=true "
               "send_device_meta=false clipboard_autosync=true power_on=false cleanup=false")
        self.tail = []
        self.proc = await asyncio.create_subprocess_exec("adb", "-s", self.serial, "shell", cmd,
                                                         stdout=PIPE, stderr=STDOUT, creationflags=NOWIN)
        out_task = asyncio.create_task(self._read_output())
        reader = None
        for _ in range(50):                       # server butuh sebentar untuk siap
            if self.proc.returncode is not None:
                await asyncio.sleep(0.2)
                raise RuntimeError("server clipboard di HP berhenti")
            try:
                r, w = await asyncio.open_connection("127.0.0.1", self.port)
                await asyncio.wait_for(r.readexactly(1), 2)   # byte penanda koneksi
                reader, self.writer = r, w
                break
            except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError):
                await asyncio.sleep(0.25)
        if reader is None:
            raise RuntimeError("server clipboard tidak menjawab")
        self.ok, self.error = True, None
        await broadcast_clip_status()
        while True:
            try:
                t = (await reader.readexactly(1))[0]
            except asyncio.IncompleteReadError:
                await asyncio.sleep(0.3)
                out_task.cancel()
                raise RuntimeError("sambungan clipboard HP terputus")
            if t == 0:                                        # clipboard dari HP
                n = int.from_bytes(await reader.readexactly(4), "big")
                text = (await reader.readexactly(n)).decode("utf-8", errors="replace")
                await on_android_clip(self.serial, text)
            elif t == 1:                                      # ack setel clipboard
                await reader.readexactly(8)
            elif t == 2:                                      # keluaran UHID (tidak dipakai)
                head = await reader.readexactly(4)
                await reader.readexactly(int.from_bytes(head[2:4], "big"))
            else:
                raise RuntimeError(f"pesan tidak dikenal: {t}")

    async def set_clip(self, text: str) -> bool:
        if not (self.ok and self.writer):
            return False
        data = text.encode("utf-8")[:CLIP_MAX]
        # TYPE_SET_CLIPBOARD(9) | sequence u64 (0 = tanpa ack) | paste u8 | panjang u32 | teks
        msg = bytes([9]) + (0).to_bytes(8, "big") + b"\x00" + len(data).to_bytes(4, "big") + data
        try:
            self.writer.write(msg)
            await self.writer.drain()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        self.ok = False
        if self.writer:
            self.writer.close()
            self.writer = None
        if self.proc and self.proc.returncode is None:
            self.proc.kill()
        self.proc = None
        if self.port:
            await run("adb", "-s", self.serial, "forward", "--remove", f"tcp:{self.port}", timeout=5)
            self.port = None

    async def stop(self) -> None:
        self.task.cancel()
        await self.close()


def device_label(serial: str) -> str:
    dev = next((d for d in S.devices if d["serial"] == serial), None)
    return dev["model"] if dev else serial


async def on_android_clip(serial: str, text: str) -> None:
    text = pcclip.normalize(text)
    if not text or text == S.last_clip or is_stale_echo(text):
        return
    mark_current(text)
    await set_pc_clip(text)
    await add_clip(text, "android", device_label(serial))
    await send_agent({"type": "clip", "text": text})
    await android_set_clip(text, exclude=serial)


async def android_set_clip(text: str, exclude: str | None = None) -> int:
    n = 0
    for serial, b in list(S.android_clips.items()):
        if serial != exclude and await b.set_clip(text):
            n += 1
    return n


def clip_status() -> dict:
    pc = S.pcclip
    return {"pc": bool(pc and pc.available and not pc.error), "pc_backend": pc.name if pc else None,
            "pc_error": pc.error if pc else "belum siap", "debian": S.agent_ws is not None,
            "debian_displays": S.debian_info.get("clip_displays"),
            "debian_error": (None if S.debian_info.get("clip_ok", True) or not S.agent_ws
                             else "xclip belum terpasang di Debian (sudo apt install xclip)"),
            "enabled": S.settings.get("clip_android", True),
            "rich": S.settings.get("clip_rich", True), "rich_pc": bool(pc and pc.rich),
            "rich_debian": "rich" in (S.debian_info.get("features") or []),
            "android": [{"serial": s, "model": device_label(s), "ok": b.ok, "error": b.error}
                        for s, b in S.android_clips.items()]}


async def broadcast_clip_status() -> None:
    await broadcast({"type": "clipstatus", "status": clip_status()})


async def android_clip_loop() -> None:
    """Pertahankan satu jembatan clipboard untuk setiap HP Android yang tersambung."""
    while True:
        await asyncio.sleep(3)
        try:
            want = set()
            if S.settings.get("clip_android", True) and S.tools.get("adb") and all(server_jar()):
                want = {d["serial"] for d in S.devices if d["state"] == "device"}
            changed = False
            for serial in list(S.android_clips):
                if serial not in want:
                    await S.android_clips.pop(serial).stop()
                    changed = True
            for serial in want - set(S.android_clips):
                S.android_clips[serial] = AndroidClip(serial)
                changed = True
            if changed:
                await broadcast_clip_status()
        except Exception as e:
            print("android_clip_loop:", e, flush=True)


# ================================================================ Mode Game (video di LinkDeck + pemetaan tombol)

GAME_JAR = "/data/local/tmp/linkdeck-game.jar"
GAME_BITRATE = {"usb": 12_000_000, "wifi": 6_000_000, "bt": 900_000, "local": 4_000_000}
GAME_FPS = {"usb": 60, "wifi": 60, "bt": 20, "local": 30}


class GameSession:
    """
    Satu sesi scrcpy-server yang videonya ditampilkan di LinkDeck (WebCodecs) dan kanal kontrolnya
    dipakai LinkDeck untuk menyuntikkan sentuhan dari keyboard/mouse (pemetaan tombol game).
    """

    def __init__(self, serial: str, opts: dict) -> None:
        self.id = secrets.token_hex(4)
        self.serial, self.opts = serial, opts
        self.proc = self.audio_proc = None
        self.port = None
        self.video_r = self.ctrl_w = None
        self.ctrl_r = None
        self.size = None
        self.tail: list[str] = []
        self.app_sent = False
        # cadangan bila peramban tidak bisa memutar H.264: dekode di laptop (PyAV) lalu kirim JPEG
        self.jpeg = False
        self.jq: queue.Queue | None = None
        self.jthread: threading.Thread | None = None
        self.jws: web.WebSocketResponse | None = None
        self.jloop: asyncio.AbstractEventLoop | None = None
        self.jsending = False
        self.jneed_key = True

    async def start(self) -> None:
        jar, version = server_jar()
        if not jar or not version:
            raise ValueError("scrcpy-server tidak ditemukan.")
        c, _, e = await run("adb", "-s", self.serial, "push", str(jar), GAME_JAR, timeout=60)
        if c:
            raise ValueError(f"Gagal mengirim server ke HP: {e.strip()[:150]}")
        scid = f"{secrets.randbelow(0x7FFFFFFF):08x}"
        c, out, e = await run("adb", "-s", self.serial, "forward", "tcp:0", f"localabstract:scrcpy_{scid}", timeout=10)
        if c or not out.strip().isdigit():
            raise ValueError(f"adb forward gagal: {(out + e).strip()[:150]}")
        self.port = int(out.strip())
        o = self.opts
        transport = next((d["transport"] for d in S.devices if d["serial"] == self.serial), "usb")
        args = [f"scid={scid}", "log_level=warn", "video=true", "audio=false", "control=true",
                "tunnel_forward=true", "send_device_meta=false", "video_codec=h264",
                f"video_bit_rate={GAME_BITRATE.get(transport, GAME_BITRATE['wifi'])}",
                f"max_fps={GAME_FPS.get(transport, 60)}", "clipboard_autosync=false", "power_on=true"]
        if o.get("mode", "virtual") == "virtual":
            w = max(320, min(7680, int(o.get("width", 1920)))) // 8 * 8
            h = max(240, min(4320, int(o.get("height", 1080)))) // 8 * 8
            dpi = max(80, min(640, int(o.get("dpi", 220))))
            args.append(f"new_display={w}x{h}/{dpi}")
        else:
            args.append("max_size=1920")
        cmd = f"CLASSPATH={GAME_JAR} app_process / com.genymobile.scrcpy.Server {version} " + " ".join(args)
        self.proc = await asyncio.create_subprocess_exec("adb", "-s", self.serial, "shell", cmd,
                                                         stdout=PIPE, stderr=STDOUT, creationflags=NOWIN)
        asyncio.create_task(self._read_output())
        for _ in range(60):                                   # soket video dulu (berisi byte penanda)
            if self.proc.returncode is not None:
                await asyncio.sleep(0.2)
                raise ValueError("Server game di HP berhenti. " + (self.tail[-1] if self.tail else ""))
            try:
                r, w = await asyncio.open_connection("127.0.0.1", self.port)
                await asyncio.wait_for(r.readexactly(1), 2)
                self.video_r, self._video_w = r, w
                break
            except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError):
                await asyncio.sleep(0.25)
        if not self.video_r:
            raise ValueError("Server game di HP tidak menjawab.")
        self.ctrl_r, self.ctrl_w = await asyncio.open_connection("127.0.0.1", self.port)
        codec = await asyncio.wait_for(self.video_r.readexactly(4), 10)
        if codec in (b"\x00\x00\x00\x00", b"\x00\x00\x00\x01"):
            raise ValueError("HP tidak bisa merekam layar untuk Mode Game.")
        asyncio.create_task(self._drain_control())
        if o.get("audio", True) and S.tools.get("virtual_display") and transport not in ("bt", "local"):
            sdk = await get_sdk(self.serial)
            aargs = ["scrcpy", f"--serial={self.serial}", "--no-window", "--audio-buffer=60"]
            if sdk >= 33:
                aargs.append("--audio-source=playback")
            if sdk >= 30:
                self.audio_proc = await asyncio.create_subprocess_exec(*aargs, stdout=asyncio.subprocess.DEVNULL,
                                                                       stderr=asyncio.subprocess.DEVNULL,
                                                                       creationflags=NOWIN)

    async def _read_output(self) -> None:
        try:
            async for raw in self.proc.stdout:
                line = raw.decode(errors="replace").strip()
                if line:
                    self.tail = (self.tail + [line])[-6:]
                    print(f"[game {self.serial}] {line}", flush=True)
        except Exception:
            pass

    async def _drain_control(self) -> None:
        """Pesan dari HP di kanal kontrol (mis. clipboard) dibaca supaya kanal tidak macet."""
        try:
            while True:
                t = (await self.ctrl_r.readexactly(1))[0]
                if t == 0:
                    n = int.from_bytes(await self.ctrl_r.readexactly(4), "big")
                    await self.ctrl_r.readexactly(n)
                elif t == 1:
                    await self.ctrl_r.readexactly(8)
                elif t == 2:
                    head = await self.ctrl_r.readexactly(4)
                    await self.ctrl_r.readexactly(int.from_bytes(head[2:4], "big"))
                else:
                    return
        except Exception:
            return

    async def pump(self, ws: web.WebSocketResponse) -> None:
        """Baca paket video scrcpy dan teruskan ke browser.
        Format pesan ke browser: [jenis u8] + isi
          1 = ukuran layar (lebar u32, tinggi u32) | 2 = konfigurasi (SPS/PPS) | 3 = frame kunci | 4 = frame biasa"""
        r = self.video_r
        while True:
            head = await r.readexactly(12)
            if head[0] & 0x80:                                 # meta sesi: ukuran berubah
                w, h = int.from_bytes(head[4:8], "big"), int.from_bytes(head[8:12], "big")
                self.size = (w, h)
                await ws.send_bytes(b"\x01" + head[4:12])
                if not self.app_sent and self.opts.get("app"):
                    self.app_sent = True
                    await self.start_app(self.opts["app"])
                continue
            flags = int.from_bytes(head[0:8], "big")
            n = int.from_bytes(head[8:12], "big")
            data = await r.readexactly(n)
            kind = 2 if flags & (1 << 62) else (3 if flags & (1 << 61) else 4)
            if self.jpeg:
                self._jpeg_feed(kind, data)
                continue
            pts = (flags & ((1 << 61) - 1)).to_bytes(8, "big")
            await ws.send_bytes(bytes([kind]) + pts + data)

    # ---------- cadangan JPEG (dekode di laptop)
    async def enable_jpeg(self, ws: web.WebSocketResponse) -> str | None:
        """Mulai mode JPEG. Mengembalikan pesan galat bila komponennya tidak ada."""
        if self.jpeg:
            return None
        try:
            import av  # noqa: F401
            from PIL import Image  # noqa: F401
        except Exception as e:
            return ("Peramban di laptop ini tidak bisa memutar video game, dan komponen cadangan (PyAV) tidak tersedia "
                    f"({e}). Buka LinkDeck lewat Chrome atau Edge, atau pasang PyAV: pip install av")
        self.jws, self.jloop = ws, asyncio.get_running_loop()
        self.jq, self.jneed_key, self.jsending = queue.Queue(), True, False
        self.jthread = threading.Thread(target=self._jpeg_worker, name="linkdeck-game-jpeg", daemon=True)
        self.jthread.start()
        self.jpeg = True
        await self.send_control(bytes([17]))                 # RESET_VIDEO: minta frame kunci baru
        return None

    def _jpeg_feed(self, kind: int, data: bytes) -> None:
        q = self.jq
        if kind in (2, 3):
            self.jneed_key = False
        elif self.jneed_key:
            return                                           # tunggu frame kunci
        if q.qsize() > 24:                                   # laptop tertinggal: buang antrean, minta frame kunci
            with q.mutex:
                q.queue.clear()
            self.jneed_key = True
            asyncio.ensure_future(self.send_control(bytes([17])))
            return
        q.put(data)

    def _jpeg_worker(self) -> None:
        import av
        codec = av.CodecContext.create("h264", "r")
        while True:
            data = self.jq.get()
            if data is None:
                break
            try:
                frames = codec.decode(av.Packet(data))
            except Exception:
                continue                                     # paket rusak: tunggu frame kunci berikutnya
            if not frames or self.jsending or self.jq.qsize() > 2:
                continue                                     # frame tetap didekode, tapi hanya yang terbaru dikirim
            fr = frames[-1]
            k = min(1.0, 1600 / max(fr.width, fr.height))
            img = fr.to_image(width=int(fr.width * k) // 2 * 2, height=int(fr.height * k) // 2 * 2) if k < 1 else fr.to_image()
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=72)
            self.jsending = True
            asyncio.run_coroutine_threadsafe(self._jpeg_send(buf.getvalue()), self.jloop)

    async def _jpeg_send(self, data: bytes) -> None:
        try:
            await self.jws.send_bytes(b"\x05" + data)
        except Exception:
            pass
        finally:
            self.jsending = False

    async def send_control(self, data: bytes) -> None:
        if self.ctrl_w:
            self.ctrl_w.write(data)
            await self.ctrl_w.drain()

    async def start_app(self, name: str) -> None:
        raw = name.encode("utf-8")[:255]
        await self.send_control(bytes([16, len(raw)]) + raw)

    async def stop(self) -> None:
        if self.jq:
            self.jq.put(None)
        for w in (self.ctrl_w, getattr(self, "_video_w", None)):
            if w:
                w.close()
        for p in (self.proc, self.audio_proc):
            if p and p.returncode is None:
                p.kill()
        if self.port:
            await run("adb", "-s", self.serial, "forward", "--remove", f"tcp:{self.port}", timeout=5)
            self.port = None


async def h_game_start(req: web.Request) -> web.Response:
    d = await req.json()
    serial = d.get("serial", "")
    if not serial:
        return fail("Pilih perangkat Android dulu.")
    for gid, g in list(S.games.items()):                     # satu Mode Game per HP
        if g.serial == serial:
            await g.stop()
            S.games.pop(gid, None)
    g = GameSession(serial, d)
    try:
        await g.start()
    except (ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
        await g.stop()
        return fail(str(e) or "Mode Game gagal dimulai.")
    S.games[g.id] = g
    return ok(id=g.id)


async def h_game_stop(req: web.Request) -> web.Response:
    g = S.games.pop((await req.json()).get("id", ""), None)
    if g:
        await g.stop()
    return ok()


async def ws_game(req: web.Request) -> web.StreamResponse:
    g = S.games.get(req.query.get("id", ""))
    if not g:
        return web.Response(status=404, text="Sesi game tidak ada")
    ws = web.WebSocketResponse(max_msg_size=0, heartbeat=20)
    await ws.prepare(req)
    pump = asyncio.create_task(g.pump(ws))
    try:
        async for m in ws:
            if m.type == WSMsgType.BINARY:
                await g.send_control(m.data)                 # pesan kontrol scrcpy (sudah dikodekan browser)
            elif m.type == WSMsgType.TEXT:
                d = json.loads(m.data)
                if d.get("type") == "app" and d.get("name"):
                    await g.start_app(d["name"])
                elif d.get("type") == "jpeg":
                    err = await g.enable_jpeg(ws)
                    await ws.send_str(json.dumps({"type": "jpeg", "ok": err is None, "error": err}))
            else:
                break
    except Exception:
        pass
    finally:
        pump.cancel()
        S.games.pop(g.id, None)
        await g.stop()
    return ws


def keymap_file() -> Path:
    return user_data_dir() / "keymaps.json"


async def h_keymap_get(req: web.Request) -> web.Response:
    key = (await req.json()).get("key", "default")
    maps = load_json(keymap_file(), {})
    return ok(keymap=maps.get(key), keys=sorted(maps))


async def h_keymap_save(req: web.Request) -> web.Response:
    d = await req.json()
    key = str(d.get("key") or "default")[:120]
    items = d.get("items")
    if not isinstance(items, list) or len(items) > 60 or not all(
            isinstance(it, dict) and it.get("type") in ("joy", "tap", "swipe", "aim")
            and isinstance(it.get("x"), (int, float)) and isinstance(it.get("y"), (int, float)) for it in items):
        return fail("Data tombol tidak valid.")
    maps = load_json(keymap_file(), {})
    if items:
        maps[key] = {"items": items, "updated": time.time()}
    else:
        maps.pop(key, None)
    save_json(keymap_file(), maps)
    return ok()


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
    if await debiantools.on_agent_event(d):
        return
    if t in ("clip_image", "clip_files"):
        await richclip.from_agent(d)
    elif t in ("sync_list",):
        fut = S.waiters.get("sync_list")
        if fut and not fut.done():
            fut.set_result(d)
    elif t == "clip_check":
        fut = S.waiters.get("clip_check")
        if fut and not fut.done():
            fut.set_result(d)
    elif t == "sync_file":
        fut = S.waiters.get("sync_file:" + d.get("path", ""))
        if fut and not fut.done():
            fut.set_result(d)
    elif t == "clip":
        text = pcclip.normalize(d.get("text", ""))
        if text and text != S.last_clip and not is_stale_echo(text):
            mark_current(text)
            await set_pc_clip(text)
            await add_clip(text, "debian")
            await android_set_clip(text)
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
        if d.get("clip_displays") and d["clip_displays"] != info.get("clip_displays"):
            info["clip_displays"] = d["clip_displays"]          # mis. Termux:X11 baru dibuka
            await broadcast_clip_status()
    elif t == "battery":
        # baterai HP dibaca agen Debian (pendamping / Termux:API / sysfs): berguna saat HP tidak tersambung adb
        lv = d.get("level")
        if isinstance(lv, int) and 0 <= lv <= 100:
            info = S.debian_info
            info["battery"] = {"level": lv, "charging": bool(d.get("charging")), "plugged": d.get("plugged") or "none",
                               "temp": d.get("temp") if isinstance(d.get("temp"), (int, float)) else None,
                               "source": str(d.get("source") or "")[:20]}
            if not info.get("bat_hist") or info["bat_hist"][-1] != lv:
                info["bat_hist"] = (info.get("bat_hist", []) + [lv])[-30:]
    elif t == "hello":
        S.debian_info["version"] = d.get("version")
        S.debian_info["features"] = d.get("features") or []
        S.debian_info["root"] = d.get("root")
        if "rich" in S.debian_info["features"]:
            await send_agent({"type": "rich", "on": S.settings.get("clip_rich", True)})
        S.debian_info["host"] = d.get("host")
        S.debian_info["screen"] = d.get("screen")
        S.debian_info["clip_displays"] = d.get("clip_displays")
        S.debian_info["clip_ok"] = d.get("clip_ok", True)
        await broadcast_clip_status()
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
                    await broadcast_clip_status()
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
            await broadcast_clip_status()
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
            if companionlink.notif_live(serial):
                continue        # aplikasi pendamping mengirim notifikasi langsung; tidak perlu dumpsys
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

async def h_i18n(req: web.Request) -> web.Response:
    """Kamus bahasa UI. Tipe MIME ditulis sendiri: di Windows .js kadang terdaftar sebagai text/plain."""
    f = STATIC / "i18n" / f"{req.match_info['lang']}.js"
    if not f.is_file():
        raise web.HTTPNotFound()
    return web.Response(body=f.read_bytes(), content_type="text/javascript", charset="utf-8",
                        headers={"Cache-Control": "no-cache"})


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
    welcome, S.welcomed = not S.welcomed, True
    return ok(tools=S.tools, devices=S.devices, clips=S.clips, debian=public_debian(),
              save_dir=str(SAVE_DIR), sync_dir=str(SYNC_DIR), sessions=public_sessions(),
              version=VERSION, agent_pkg=find_agent_deb() is not None, settings=S.settings,
              pairings=public_pairings(), notifs=S.notifs[:30],
              discovered=[{k: v for k, v in e.items() if k != "fp"} for e in S.discovered.values()],
              sync=S.sync_info, kvm={"on": S.kvm_on, "captured": bool(S.kvm and S.kvm.captured)},
              clip_status=clip_status(), networks=await pc_networks(), welcome=welcome,
              companion={x["serial"]: companionlink.status(x["serial"]) for x in S.devices if x["state"] == "device"})


async def h_tools(req: web.Request) -> web.Response:
    return ok(tools=await detect_tools())


async def h_settings(req: web.Request) -> web.Response:
    d = await req.json()
    for k in DEFAULT_SETTINGS:
        if k in d:
            S.settings[k] = bool(d[k])
    save_json(user_data_dir() / "settings.json", S.settings)
    if "clip_rich" in d:
        await send_agent({"type": "rich", "on": S.settings["clip_rich"]})
        await broadcast_clip_status()
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

def parse_mdns(out: str) -> list[dict]:
    svcs = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "_adb-tls-" in parts[1] and ":" in parts[2]:
            svcs.append({"name": parts[0], "type": parts[1].rstrip("."), "addr": parts[2]})
    return svcs


async def mdns_services() -> list[dict]:
    _, out, err = await run("adb", "mdns", "services", timeout=8)
    return parse_mdns(out + "\n" + err)


async def connect_after_pair(ip: str, tries: int = 12) -> str | None:
    """Setelah pairing, HP mengumumkan layanan _adb-tls-connect; sambungkan ke sana."""
    for _ in range(tries):
        await refresh_devices()
        known = next((d["serial"] for d in S.devices if d["state"] == "device" and d["serial"].startswith(ip + ":")), None)
        if known:
            return known
        con = next((x for x in await mdns_services() if "connect" in x["type"] and x["addr"].startswith(ip + ":")), None)
        if con:
            _, out, err = await run("adb", "connect", con["addr"], timeout=15)
            if "connected to" in (out + err):
                await refresh_devices()
                return con["addr"]
        await asyncio.sleep(1.5)
    return None


async def h_pair(req: web.Request) -> web.Response:
    d = await req.json()
    host, code = d.get("host", "").strip(), d.get("code", "").strip()
    if not re.match(r"^[\w.\-]+:\d+$", host) or not code.isdigit():
        return fail("Isi alamat dan kode 6 angka dari layar Debugging nirkabel.")
    c, out, err = await run("adb", "pair", host, code, timeout=30)
    msg = (out + err).strip()
    if c or "Successfully" not in msg:
        return fail(f"Pairing gagal: {msg or 'adb tidak memberi pesan'}")
    serial = await connect_after_pair(host.split(":")[0])
    return ok(msg=msg, serial=serial)


async def h_mdns(req: web.Request) -> web.Response:
    return ok(services=await mdns_services())


def make_qr_svg(text: str) -> str:
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    return svg[svg.index("<svg"):]


async def qr_pair_loop(name: str, pw: str) -> None:
    async def say(state: str, **kw) -> None:
        await broadcast({"type": "qrpair", "state": state, **kw})
    await say("waiting")
    deadline = time.time() + 180
    while time.time() < deadline:
        svc = next((x for x in await mdns_services() if x["name"] == name and "pairing" in x["type"]), None)
        if svc:
            await say("pairing")
            c, out, err = await run("adb", "pair", svc["addr"], pw, timeout=30)
            if "Successfully" not in out + err:
                await say("error", msg=(out + err).strip()[:160])
                return
            await say("connecting")
            serial = await connect_after_pair(svc["addr"].split(":")[0], tries=15)
            if serial:
                await log(f"Android tersambung lewat Wi-Fi tanpa kabel ({serial}).")
                await say("connected", serial=serial)
            else:
                await say("error", msg="terpasang, tetapi belum bisa menyambung. Coba buka ulang Debugging nirkabel.")
            return
        await asyncio.sleep(1.5)
    await say("timeout")


async def h_qr(req: web.Request) -> web.Response:
    """QR seperti Android Studio: WIFI:T:ADB;S:<nama>;P:<sandi>;; lalu dipasangkan lewat mDNS."""
    if not S.tools.get("adb"):
        return fail("adb belum siap.")
    if getattr(S, "qr_task", None):
        S.qr_task.cancel()
    name = "linkdeck-" + secrets.token_hex(3)
    pw = "".join(secrets.choice("0123456789") for _ in range(10))
    try:
        svg = make_qr_svg(f"WIFI:T:ADB;S:{name};P:{pw};;")
    except ImportError:
        return fail("Pustaka qrcode belum terpasang (pip install qrcode). Pakai cara kode 6 angka.")
    if os.environ.get("LINKDECK_DEBUG_QR"):          # hanya untuk pengujian otomatis
        (user_data_dir() / "qr-debug.txt").write_text(f"{name} {pw}")
    S.qr_task = asyncio.create_task(qr_pair_loop(name, pw))
    return ok(svg=svg, name=name)


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
    ready = [x for x in S.devices if x["state"] == "device"]
    usb = [x for x in ready if x["transport"] == "usb"]
    pool = usb or [x for x in ready if not re.match(r"^[\d.]+:5555$", x["serial"])] or ready
    serial = d.get("serial") if any(x["serial"] == d.get("serial") for x in pool) else (pool[0]["serial"] if pool else "")
    if not serial:
        return fail("Sambungkan Android sekali dulu lewat kabel atau Wi-Fi (kode QR), lalu klik tombol ini lagi.")
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
    if mode == "input":
        # keyboard & mouse laptop untuk HP tanpa menampilkan layar (UHID, butuh scrcpy 2.0+)
        return args + ["--no-video", "--no-audio", "--keyboard=uhid", "--mouse=uhid"]
    args += [a for a in PRESETS.get(preset, PRESETS["wifi"])
             if not (mode == "camera" and a.startswith("--max-size"))]
    if mode == "camera":
        args += ["--video-source=camera", f"--camera-facing={d.get('facing', 'back')}"]
        size = str(d.get("camera_size") or "1920x1080")
        if preset == "bt":
            size = "1280x720" if size == "1920x1080" else size
        if re.match(r"^\d+x\d+$", size):
            args.append(f"--camera-size={size}")
        if d.get("torch") and d.get("facing", "back") == "back":
            args.append("--camera-torch")
        zoom = float(d.get("zoom") or 1)
        if abs(zoom - 1) >= 0.01:
            args.append(f"--camera-zoom={zoom:.2f}")
        sink = d.get("v4l2")
        if sink and sys.platform.startswith("linux") and re.match(r"^/dev/video\d+$", sink):
            args += [f"--v4l2-sink={sink}"]
            if d.get("hide_window"):
                args.append("--no-video-playback")
        if not d.get("audio") and "--no-audio" not in args:
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
        want_audio = d.get("audio", True) and "--no-audio" not in args
        sdk = int(d.get("_sdk") or 0)
        if want_audio and (d.get("_audio_busy") or (sdk and sdk < 30)):
            want_audio = False          # sesi lain sudah memegang audio / Android < 11 tidak bisa
        if not want_audio:
            if "--no-audio" not in args:
                args.append("--no-audio")
        elif sdk >= 33:
            # "playback" merutekan suara HANYA ke PC (HP senyap), kecuali diminta tetap di HP juga
            args.append("--audio-source=playback")
            if d.get("audio_dup"):
                args.append("--audio-dup")
        # Android 11-12: sumber bawaan "output" (REMOTE_SUBMIX) juga mematikan suara di HP
    if d.get("window_x") is not None and d.get("window_y") is not None:
        args += [f"--window-x={int(d['window_x'])}", f"--window-y={int(d['window_y'])}"]
    if d.get("fullscreen"):
        args.append("--fullscreen")
    if d.get("record"):
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        args.append(f"--record={SAVE_DIR / time.strftime('rekaman-%Y%m%d-%H%M%S.mp4')}")
    return args


async def get_sdk(serial: str) -> int:
    if serial not in S.sdk:
        _, out, _ = await run("adb", "-s", serial, "shell", "getprop", "ro.build.version.sdk", timeout=8)
        S.sdk[serial] = int(out.strip()) if out.strip().isdigit() else 0
    return S.sdk[serial]


async def start_session(d: dict) -> tuple[str, list[str]]:
    """Mulai satu jendela scrcpy. Mengembalikan (id sesi, catatan untuk pengguna)."""
    serial, mode = d.get("serial", ""), d.get("mode", "virtual")
    if not serial:
        raise ValueError("Pilih perangkat Android dulu.")
    if mode == "virtual" and not S.tools.get("virtual_display"):
        raise ValueError("Layar virtual butuh scrcpy 3.0 atau lebih baru.")
    if mode in ("mirror", "camera", "input") and any(x["serial"] == serial and x["mode"] == mode
                                            for x in S.sessions.values()):
        raise ValueError("Mode ini sudah berjalan untuk perangkat ini.")
    if mode == "camera" and d.get("webcam") and not sys.platform.startswith("linux"):
        return await mediadev.start_media("webcam", d)      # Windows/macOS: kamera HP -> OBS Virtual Camera
    notes = []
    d = dict(d)
    d["_sdk"] = await get_sdk(serial)
    wants_audio = bool(d.get("audio", mode != "camera")) and d.get("preset") != "bt"
    d["_audio_busy"] = mode != "camera" and any(x["serial"] == serial and x.get("audio")
                                                for x in S.sessions.values())
    if wants_audio and mode != "camera":
        if d["_audio_busy"]:
            notes.append("Suara sudah dikirim oleh jendela lain, jadi jendela ini tanpa suara.")
        elif d["_sdk"] and d["_sdk"] < 30:
            notes.append("Android di bawah 11 tidak bisa mengirim suara ke PC; suara tetap di HP.")
        elif d["_sdk"] >= 33 and not d.get("audio_dup"):
            notes.append("Suara HP dipindah ke PC; HP jadi senyap selama jendela ini terbuka.")
    if mode == "camera" and d.get("torch") and d.get("facing", "back") != "back":
        notes.append("Senter hanya tersedia di kamera belakang.")
    dev = next((x for x in S.devices if x["serial"] == serial), {})
    label = d.get("label") or {"camera": "Kamera", "mirror": "Cermin", "input": "Keyboard & mouse"}.get(mode) \
        or dev.get("model", serial)
    args = build_scrcpy_args(d, label)
    proc = await asyncio.create_subprocess_exec(*args, stdout=PIPE, stderr=STDOUT, creationflags=NOWIN)
    sid = secrets.token_hex(4)
    has_audio = "--no-audio" not in args and mode != "camera"
    S.sessions[sid] = {"serial": serial, "mode": mode, "label": label, "proc": proc,
                       "audio": has_audio, "req": {k: v for k, v in d.items() if not k.startswith("_")}}
    asyncio.create_task(watch_session(sid, proc))
    print("scrcpy:", " ".join(shlex.quote(a) for a in args[1:]), flush=True)
    await broadcast({"type": "sessions", "sessions": public_sessions()})
    await refresh_devices()
    return sid, notes


async def h_mirror_start(req: web.Request) -> web.Response:
    if not S.tools.get("scrcpy"):
        return fail("scrcpy belum terpasang.")
    d = await req.json()
    try:
        sid, notes = await start_session(d)
    except ValueError as e:
        return fail(str(e))
    if d.get("mode") in ("virtual", "mirror") and not d.get("app"):
        save_json(user_data_dir() / "last-mirror.json",
                  {k: v for k, v in d.items() if k not in ("serial", "window_x", "window_y", "fullscreen")})
    return ok(id=sid, notes=notes)


async def stop_session(sid: str) -> None:
    sess = S.sessions.get(sid)
    if not sess:
        return
    S.stopping.add(sid)
    sess["proc"].terminate()
    try:
        await asyncio.wait_for(sess["proc"].wait(), 6)
    except asyncio.TimeoutError:
        sess["proc"].kill()


async def h_camera_info(req: web.Request) -> web.Response:
    """Rentang zoom tiap kamera (dari scrcpy --list-cameras)."""
    serial = (await req.json()).get("serial", "")
    if not serial:
        return fail("Pilih perangkat Android dulu.")
    if serial not in S.camera_info:
        _, out, err = await run("scrcpy", f"--serial={serial}", "--list-cameras", timeout=30)
        info = {}
        for m in re.finditer(r"--camera-id=(\S+)\s+\((\w+),([^)]*)\)", out + err):
            facing, rest = m.group(2), m.group(3)
            z = re.search(r"zoom-range=\[([\d.]+),\s*([\d.]+)\]", rest)
            if facing not in info:
                info[facing] = {"id": m.group(1), "zoom": [float(z.group(1)), float(z.group(2))] if z else None}
        S.camera_info[serial] = info
    return ok(cameras=S.camera_info[serial])


async def h_camera_update(req: web.Request) -> web.Response:
    """Terapkan senter/zoom/arah kamera ke sesi kamera yang sedang jalan (dibuka ulang sebentar)."""
    d = await req.json()
    serial = d.get("serial", "")
    sid = next((k for k, v in S.sessions.items() if v["serial"] == serial and v["mode"] == "camera"), None)
    if not sid:
        return ok(applied=False)
    newreq = {**S.sessions[sid]["req"], **{k: d[k] for k in ("torch", "zoom", "facing", "camera_size") if k in d}}
    await stop_session(sid)
    await asyncio.sleep(0.6)                  # beri waktu HP melepas kamera
    try:
        new_sid, notes = await start_session(newreq)
    except ValueError as e:
        return fail(str(e))
    return ok(applied=True, id=new_sid, notes=notes)


async def h_mirror_stop(req: web.Request) -> web.Response:
    d = await req.json()
    ids = [d["id"]] if d.get("id") else [k for k, v in S.sessions.items() if v["serial"] == d.get("serial")]
    if not ids:
        return fail("Tidak ada tampilan yang berjalan.")
    for sid in ids:
        if sid in S.sessions:
            S.stopping.add(sid)
            S.sessions[sid]["proc"].terminate()
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
        msg = str(e)
        if transport == "bt" and "tidak menjawab" in msg:
            bt = [n for n in await pc_networks() if n["bt"]]
            if not bt:
                msg += (" Laptop belum tergabung ke jaringan Bluetooth HP: nyalakan Tethering Bluetooth di HP, "
                        "lalu di laptop Win+R → control printers → klik kanan HP → Connect using → Access point.")
            elif bt[0]["gateway"] and bt[0]["gateway"] != host:
                msg += f" IP HP di jaringan Bluetooth adalah {bt[0]['gateway']} — coba IP itu."
        return fail(msg)
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


async def h_clip_test(req: web.Request) -> web.Response:
    """Tulis teks uji ke clipboard PC, baca lagi, lalu sebarkan ke HP dan Debian."""
    marker = "LinkDeck uji clipboard " + time.strftime("%H:%M:%S")
    pc, result = S.pcclip, {"marker": marker}
    try:
        await asyncio.to_thread(pc.set, marker)
        back = await asyncio.to_thread(pc.get)
        result["pc"] = back == marker
        result["pc_error"] = None if result["pc"] else f"terbaca: {back!r}"[:120]
    except Exception as e:
        result["pc"], result["pc_error"] = False, str(e)
    mark_current(marker)
    await add_clip(marker, "pc")
    result["debian"] = False
    if await send_agent({"type": "clip", "text": marker}):
        await asyncio.sleep(0.8)                      # beri waktu agen mengisi semua layar X
        chk = await agent_request({"type": "clip_check"}, "clip_check", timeout=8)
        if chk is None:
            result["debian_error"] = "agen Debian versi lama (perbarui ke 1.7.0) atau tidak menjawab"
        else:
            got = [d for d, v in (chk.get("displays") or {}).items() if v == marker]
            result["debian"] = bool(got)
            result["debian_displays"] = got
            if not got:
                result["debian_error"] = ("xclip belum terpasang di Debian" if not chk.get("xclip")
                                          else "teks uji tidak terbaca di clipboard Debian")
    result["android"] = await android_set_clip(marker)
    result["android_total"] = len(S.android_clips)
    result["status"] = clip_status()
    return ok(**result)


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
    text = pcclip.normalize(str(d.get("text", "")))
    if not text:
        return fail("Teks kosong.")
    if d.get("src") == "debian-viewer":
        if text != S.last_clip and not is_stale_echo(text):
            mark_current(text)
            await set_pc_clip(text)
            await add_clip(text, "debian")
            await android_set_clip(text)
        return ok()
    mark_current(text)
    await set_pc_clip(text)
    sent = await send_agent({"type": "clip", "text": text})
    n_android = await android_set_clip(text)
    await add_clip(text, "pc")
    return ok(debian=sent, android=n_android)


async def h_files(req: web.Request) -> web.Response:
    reader = await req.multipart()
    target, serial, done, dest_dir = "android", None, [], ""
    tmp_dir = SAVE_DIR / ".kirim"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    async for part in reader:
        if part.name == "target":
            target = (await part.text()).strip()
            continue
        if part.name == "serial":
            serial = (await part.text()).strip()
            continue
        if part.name == "dest":
            dest_dir = (await part.text()).strip()
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
                folder = ANDROID_DROP
                if dest_dir:
                    import features
                    folder = features.safe_phone_path(dest_dir) or ANDROID_DROP
                await run("adb", "-s", serial, "shell", "mkdir", "-p", folder)
                c, _, e = await run("adb", "-s", serial, "push", str(tmp), f"{folder}/{name}", timeout=1800)
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
    if target == "android":
        import features
        where = features.safe_phone_path(dest_dir) if dest_dir else ANDROID_DROP
    else:
        where = "~/Downloads/LinkDeck (Debian)"
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
                if not companionlink.battery_live(dev["serial"]) and due("bat:" + dev["serial"], poll["bat"]):
                    _, out, _ = await run("adb", "-s", dev["serial"], "shell", "dumpsys", "battery", timeout=6)
                    lv, tp = re.search(r"level:\s*(\d+)", out), re.search(r"temperature:\s*(\d+)", out)
                    if lv:
                        s["bat"] = (s["bat"] + [int(lv.group(1))])[-30:]
                    if tp:
                        s["temp"] = int(tp.group(1)) / 10
                    st_ = re.search(r"status:\s*(\d+)", out)
                    if st_:   # 2 = mengisi, 5 = penuh (BatteryManager)
                        plug = next((n for k, n in (("AC", "ac"), ("USB", "usb"), ("Wireless", "wireless"))
                                     if re.search(rf"{k} powered:\s*true", out)), "none")
                        s["charging"] = st_.group(1) == "2" or (st_.group(1) == "5" and plug != "none")
                        s["plugged"] = plug
                    s["via"] = "adb"
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
    S.pcclip = pcclip.PCClipboard()
    print(f"Clipboard PC: {S.pcclip.name}" + (f" ({S.pcclip.error})" if S.pcclip.error else ""), flush=True)
    await detect_tools()
    S.tasks = [asyncio.create_task(t()) for t in (clip_watcher, stats_loop, assets_task, discovery_loop,
                                                  sync_loop, notif_loop, adb_reconnect_loop, android_clip_loop, adb_probe_loop,
                                                  scrcpy_version_retry)]
    if OPEN_BROWSER and "--no-browser" not in sys.argv:
        asyncio.get_running_loop().call_later(0.8, webbrowser.open, f"http://{HOST}:{PORT}/")


async def on_shutdown(app: web.Application) -> None:
    for g in list(S.games.values()):
        await g.stop()
    for b in list(S.android_clips.values()):
        await b.stop()
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


# alamat GET yang dipakai langsung oleh <img>/<video>/<a>, sehingga token boleh lewat ?t=
QUERY_TOKEN_PATHS = {"/api/phone/files/raw", "/api/clip/image", "/api/deb/fs/raw"}


@web.middleware
async def guard(req: web.Request, handler):
    if req.path.startswith("/api/") and req.headers.get("X-LinkDeck-Token") != TOKEN \
            and not (req.path in QUERY_TOKEN_PATHS and req.query.get("t") == TOKEN):
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
    r.add_post("/api/adb/mdns", h_mdns)
    r.add_post("/api/adb/qr", h_qr)
    r.add_post("/api/adb/tcpip", h_tcpip)
    r.add_post("/api/apps", h_apps)
    r.add_post("/api/mirror/start", h_mirror_start)
    r.add_post("/api/mirror/stop", h_mirror_stop)
    r.add_post("/api/camera/info", h_camera_info)
    r.add_post("/api/game/start", h_game_start)
    r.add_post("/api/game/stop", h_game_stop)
    r.add_post("/api/keymap/get", h_keymap_get)
    r.add_post("/api/keymap/save", h_keymap_save)
    r.add_get("/ws/game", ws_game)
    r.add_post("/api/camera/update", h_camera_update)
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
    r.add_post("/api/clipboard/test", h_clip_test)
    r.add_post("/api/files", h_files)
    r.add_post("/api/link", h_link)
    r.add_get("/ws/events", ws_events)
    r.add_get("/ws/vnc", ws_vnc)
    r.add_get("/ws/term", ws_term)
    r.add_get("/ws/audio", ws_audio)
    r.add_get("/i18n/{lang:[a-z]{2}}.js", h_i18n)
    r.add_static("/novnc", NOVNC_DIR)
    r.add_static("/xterm", XTERM_DIR)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    import features
    features.register(r, sys.modules[__name__], app)
    richclip.register(r, sys.modules[__name__], app)
    mediadev.register(r, sys.modules[__name__], app)
    companionlink.register(r, sys.modules[__name__], app)
    debiantools.register(r, sys.modules[__name__], app)
    return app


def main() -> None:
    print(f"LinkDeck {VERSION} berjalan di http://{HOST}:{PORT}/  (Ctrl+C untuk berhenti)")
    web.run_app(build_app(), host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    main()
