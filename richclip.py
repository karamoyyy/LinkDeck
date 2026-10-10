"""
Clipboard gambar & berkas (tahap 2): laptop/PC <-> Debian.

  * Gambar  : PNG. Windows (CF_DIB + format "PNG"), Linux (xclip/wl-clipboard), Debian (xclip image/png).
  * Berkas  : berkas yang disalin di Explorer / pengelola berkas dikirim ke perangkat lain, lalu clipboard di sana
              diisi berkas yang sama sehingga tinggal ditempel (Ctrl+V).
  * Android : clipboard Android lewat scrcpy hanya mendukung teks, jadi gambar/berkas tidak dikirim ke HP.

Didaftarkan oleh server.build_app() lewat register(router, core, app).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

from aiohttp import web

core = None
MAX_FILE = 48 * 1024 * 1024          # sama dengan batas per berkas di agen
MAX_IMAGE = 20 * 1024 * 1024
STATE = {"present": False, "sig": None, "set_at": 0.0, "sent": {}, "own": None}
IMAGES: dict[str, bytes] = {}        # id riwayat -> PNG (hanya beberapa terakhir, di memori)
FILESETS: dict[str, list[str]] = {}  # id riwayat -> jalur berkas
BATCHES: dict[str, dict] = {}


def enabled() -> bool:
    return core.S.settings.get("clip_rich", True)


def agent_ok() -> bool:
    """Agen Debian tersambung DAN mendukung gambar/berkas (1.10+); agen lama tidak dikirimi."""
    return core.S.agent_ws is not None and "rich" in (core.S.debian_info.get("features") or [])


def sig_of(kind: str, val) -> str:
    """Sidik isi: gambar = hash PNG; berkas = nama + ukuran (jalurnya beda di tiap perangkat)."""
    if kind == "image":
        return "img:" + hashlib.sha1(val).hexdigest()
    keys = sorted(f"{Path(p).name}\t{os.path.getsize(p) if os.path.exists(p) else 0}" for p in val)
    return "files:" + hashlib.sha1("\n".join(keys).encode()).hexdigest()


def image_size(png: bytes) -> tuple[int, int]:
    if png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 24:
        return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    return 0, 0


def bounced(sig: str) -> bool:
    """True bila isi dari Debian ini hanyalah pantulan isi yang baru saja kita kirim ke Debian."""
    t = STATE["sent"].get(sig)
    return t is not None and time.time() - t < 4


def mark_sent(sig: str) -> None:
    now = time.time()
    STATE["sent"][sig] = now
    for k in [k for k, v in STATE["sent"].items() if now - v > 60]:
        del STATE["sent"][k]


async def add_item(kind: str, src: str, payload, label: str | None = None) -> None:
    item_id = secrets.token_hex(4)
    item = {"id": item_id, "kind": kind, "src": src, "label": label, "t": time.time(), "text": ""}
    if kind == "image":
        IMAGES[item_id] = payload
        w, h = image_size(payload)
        item.update(w=w, h=h, size=len(payload), text=f"Gambar {w}×{h}")
        for old in list(IMAGES)[:-6]:                 # simpan 6 gambar terakhir saja
            IMAGES.pop(old, None)
    else:
        FILESETS[item_id] = payload
        names = [Path(p).name for p in payload]
        item.update(files=names, text=f"{len(names)} berkas: " + ", ".join(names[:3]) + ("…" if len(names) > 3 else ""))
    core.S.clips.insert(0, item)
    del core.S.clips[40:]
    core.S.last_clip = None          # teks yang sama yang disalin lagi nanti tetap terdeteksi
    core.S.clip_recent.clear()       # ...dan tidak dianggap gema
    await core.broadcast({"type": "clip", "item": item})


# ---------------------------------------------------------------- PC -> Debian

async def send_files_to_agent(paths: list[str]) -> int:
    files = [p for p in paths if os.path.getsize(p) <= MAX_FILE]
    batch = secrets.token_hex(5)
    for i, p in enumerate(files):
        data = await asyncio.to_thread(Path(p).read_bytes)
        ok = await core.send_agent({"type": "clip_files", "batch": batch, "index": i, "total": len(files),
                                    "name": Path(p).name, "data": base64.b64encode(data).decode()})
        if not ok:
            break
    skipped = len(paths) - len(files)
    if skipped:
        await core.log(f"{skipped} berkas lebih dari {MAX_FILE // 1048576} MB tidak ikut disalin ke Debian.", "warn")
    return len(files)


async def scan() -> bool:
    """Dipanggil pemantau clipboard PC. True bila clipboard PC berisi gambar/berkas (teks tidak diproses)."""
    pc = core.S.pcclip
    if not (enabled() and pc and pc.rich):
        STATE["present"] = False
        return False
    kind = await asyncio.to_thread(pc.rich_kind)
    if kind == "?":
        return STATE["present"]                      # tidak diketahui: biarkan status
    if not kind:
        STATE["present"], STATE["sig"] = False, None
        return False
    STATE["present"] = True
    val = await asyncio.to_thread(pc.get_files if kind == "files" else pc.get_image)
    if not val:
        return True
    if kind == "image" and len(val) > MAX_IMAGE:
        return True
    sig = sig_of(kind, val)
    if sig == STATE["sig"]:
        return True
    STATE["sig"] = sig
    if sig == STATE["own"] or time.time() - STATE["set_at"] < 1.5:
        return True                                  # isi yang kita pasang sendiri (dari Debian / Salin lagi)
    STATE["own"] = None
    mark_sent(sig)
    if kind == "image":
        await add_item("image", "pc", val)
        if agent_ok():
            await core.send_agent({"type": "clip_image", "png": base64.b64encode(val).decode()})
    else:
        await add_item("files", "pc", val)
        if agent_ok():
            await send_files_to_agent(val)
    return True


# ---------------------------------------------------------------- Debian -> PC

async def set_pc(kind: str, val) -> None:
    pc = core.S.pcclip
    if not (pc and pc.rich):
        return
    sig = sig_of(kind, val)
    STATE["sig"], STATE["set_at"], STATE["present"], STATE["own"] = sig, time.time(), True, sig
    try:
        await asyncio.to_thread(pc.set_files if kind == "files" else pc.set_image, val)
    except Exception as e:
        await core.log(f"Tidak bisa mengisi clipboard PC dengan {'berkas' if kind == 'files' else 'gambar'}: {e}", "warn")


async def from_agent(d: dict) -> None:
    if not enabled():
        return
    if d.get("type") == "clip_image":
        try:
            png = base64.b64decode(d.get("png", ""))
        except ValueError:
            return
        if not png or len(png) > MAX_IMAGE:
            return
        if bounced(sig_of("image", png)):
            return
        await set_pc("image", png)
        await add_item("image", "debian", png)
        return
    key = str(d.get("batch", "x"))[:16]
    b = BATCHES.setdefault(key, {"files": [], "t": time.time(),
                                 "dir": core.SAVE_DIR / "Clipboard" / (time.strftime("%Y%m%d-%H%M%S-") + core.safe_name(key))})
    b["dir"].mkdir(parents=True, exist_ok=True)
    try:
        data = base64.b64decode(d.get("data", ""))
    except ValueError:
        return
    dest = core.unique_path(b["dir"] / core.safe_name(d.get("name", "berkas")))
    await asyncio.to_thread(dest.write_bytes, data)
    b["files"].append(str(dest))
    if int(d.get("index", 0)) + 1 >= int(d.get("total", 1)):
        BATCHES.pop(key, None)
        if bounced(sig_of("files", b["files"])):
            return                                   # berkas yang baru saja kita kirim ke Debian memantul balik
        await set_pc("files", b["files"])
        await add_item("files", "debian", b["files"])
    for k in [k for k, v in BATCHES.items() if time.time() - v["t"] > 300]:
        BATCHES.pop(k, None)


# ---------------------------------------------------------------- endpoint

async def h_image(req: web.Request) -> web.Response:
    png = IMAGES.get(req.query.get("id", ""))
    if not png:
        return web.Response(status=404)
    return web.Response(body=png, content_type="image/png", headers={"Cache-Control": "no-store"})


async def h_again(req: web.Request) -> web.Response:
    """'Salin lagi' untuk riwayat gambar/berkas: isi clipboard PC dan Debian lagi."""
    d = await req.json()
    item_id = d.get("id", "")
    if item_id in IMAGES:
        png = IMAGES[item_id]
        mark_sent(sig_of("image", png))
        await set_pc("image", png)
        sent = agent_ok() and await core.send_agent({"type": "clip_image", "png": base64.b64encode(png).decode()})
        return core.ok(debian=bool(sent))
    if item_id in FILESETS:
        paths = [p for p in FILESETS[item_id] if os.path.isfile(p)]
        if not paths:
            return core.fail("Berkasnya sudah tidak ada.")
        mark_sent(sig_of("files", paths))
        await set_pc("files", paths)
        n = await send_files_to_agent(paths) if agent_ok() else 0
        return core.ok(debian=bool(n))
    return core.fail("Item ini sudah tidak tersimpan. Salin ulang dari perangkat asalnya.")


async def h_reveal(req: web.Request) -> web.Response:
    """Buka folder berisi berkas dari riwayat clipboard."""
    paths = FILESETS.get((await req.json()).get("id", ""), [])
    if not paths:
        return core.fail("Berkasnya sudah tidak ada.")
    folder = str(Path(paths[0]).parent)
    try:
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        return core.fail(f"Folder tidak bisa dibuka otomatis ({e}). Lokasinya: {folder}")
    return core.ok(path=folder)


def register(router, core_module, app) -> None:
    global core
    core = core_module
    router.add_get("/api/clip/image", h_image)
    router.add_post("/api/clip/again", h_again)
    router.add_post("/api/clip/reveal", h_reveal)
