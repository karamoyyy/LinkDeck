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
import subprocess
import termios
import time
from pathlib import Path

from aiohttp import WSMsgType, web

VERSION = "1.2.0"
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

clients: set = set()
last_clip = None


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

def clip_get():
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard", "-o"], env=ENV,
                           capture_output=True, timeout=2)
        return r.stdout.decode(errors="replace") if r.returncode == 0 else None
    except Exception:
        return None


def clip_set(text: str) -> None:
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard", "-i"], env=ENV,
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        p.communicate(text.encode(), timeout=3)
    except Exception as e:
        log("clip_set:", e)


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
    elif t == "clip":
        text = d.get("text", "")
        if text and text != last_clip:
            last_clip = text
            await asyncio.to_thread(clip_set, text)
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
                                  "sync_dir": str(SYNC)}))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                await handle(ws, json.loads(msg.data))
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


# ------------------------------------------------------------------ tugas latar

async def clip_loop() -> None:
    global last_clip
    last_clip = await asyncio.to_thread(clip_get)
    while True:
        await asyncio.sleep(0.7)
        if not clients:
            continue
        text = await asyncio.to_thread(clip_get)
        if text and text != last_clip:
            last_clip = text
            await send_all({"type": "clip", "text": text})


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
        await send_all({"type": "info", "load": load, "mem": mem_used_pct(), "host": os.uname().nodename})


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
    while True:
        for target in ("255.255.255.255", "192.168.44.255"):
            try:
                sock.sendto(msg, (target, BEACON_PORT))
            except OSError:
                pass
        await asyncio.sleep(2)


async def on_startup(app):
    for fn in (clip_loop, info_loop, outbox_loop, beacon_loop):
        asyncio.create_task(fn())


def main() -> None:
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
