"""
Alat Debian (tahap 2), semuanya lewat agen LinkDeck (TLS) di Debian HP:
  * Berkas Debian  : jelajahi, unggah, unduh, pratinjau, buat folder, ganti nama, hapus (ubah: hanya di ~)
  * Toko aplikasi  : cari, pasang, copot paket apt; keluaran apt tampil langsung
  * Pemantau sistem: CPU, RAM, swap, penyimpanan, waktu nyala, daftar proses, hentikan proses

Butuh agen 1.10.0 atau lebih baru. Didaftarkan oleh server.build_app() lewat register(router, core, app).
"""
from __future__ import annotations

import base64
import mimetypes
import re
import secrets

from aiohttp import web

core = None
NEED = (1, 10, 0)
PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+.\-]{0,100}$")
# aplikasi populer yang tersedia di repositori Debian 13 (trixie)
POPULAR = ["firefox-esr", "chromium", "libreoffice", "gimp", "inkscape", "vlc", "thunderbird", "geany",
           "mousepad", "ristretto", "git", "htop", "fastfetch", "nodejs", "python3-pip", "build-essential"]


def vtuple(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:3]) or (0,)


def check_agent() -> str | None:
    if core.S.agent_ws is None:
        return "Debian belum tersambung. Hubungkan dulu di panel Debian."
    ver = core.S.debian_info.get("version")
    if vtuple(ver) < NEED:
        return (f"Agen Debian {ver or 'lama'} belum mendukung fitur ini. Perbarui agen ke "
                f"{'.'.join(map(str, NEED))} atau lebih baru (lihat README bagian 4.1).")
    return None


async def call(obj: dict, timeout: float = 30) -> dict:
    """Kirim permintaan ber-rid ke agen dan tunggu jawabannya. Melempar ValueError bila gagal."""
    err = check_agent()
    if err:
        raise ValueError(err)
    rid = secrets.token_hex(6)
    res = await core.agent_request({**obj, "rid": rid}, "rid:" + rid, timeout=timeout)
    if res is None:
        raise ValueError("Agen Debian tidak menjawab. Periksa sambungan, lalu coba lagi.")
    if not res.get("ok"):
        raise ValueError(res.get("error") or "Gagal.")
    return res


def wrap(fn):
    async def handler(req):
        try:
            return await fn(req)
        except ValueError as e:
            return core.fail(str(e))
    return handler


# ---------------------------------------------------------------- berkas

async def h_fs(req):
    d = await req.json()
    r = await call({"type": "fs_list", "path": str(d.get("path") or "~")})
    return core.ok(path=r["path"], home=r["home"], writable=r["writable"], items=r["items"])


async def h_fs_op(req):
    d = await req.json()
    if d.get("op") not in ("mkdir", "rename", "delete"):
        raise ValueError("Aksi tidak dikenal.")
    await call({"type": "fs_op", "op": d["op"], "path": str(d.get("path", "")), "name": str(d.get("name", ""))})
    return core.ok()


async def h_fs_pull(req):
    d = await req.json()
    r = await call({"type": "fs_get", "path": str(d.get("path", ""))}, timeout=180)
    core.SAVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = core.unique_path(core.SAVE_DIR / core.safe_name(r["name"]))
    dest.write_bytes(base64.b64decode(r["data"]))
    return core.ok(path=str(dest))


async def h_fs_raw(req):
    try:
        r = await call({"type": "fs_get", "path": req.query.get("path", "")}, timeout=120)
    except ValueError as e:
        return web.Response(status=400, text=str(e))
    ctype = mimetypes.guess_type(r["name"])[0] or "application/octet-stream"
    return web.Response(body=base64.b64decode(r["data"]), headers={"Content-Type": ctype, "Cache-Control": "no-store"})


async def h_fs_upload(req):
    reader = await req.multipart()
    folder, done = "~", []
    async for part in reader:
        if part.name == "dir":
            folder = (await part.text()).strip() or "~"
            continue
        if part.name != "file" or not part.filename:
            continue
        data = bytearray()
        while chunk := await part.read_chunk(1 << 20):
            data += chunk
            if len(data) > 48 * 1024 * 1024:
                raise ValueError(f"{part.filename} lebih dari 48 MB. Pakai folder sinkron untuk berkas besar.")
        r = await call({"type": "fs_put", "dir": folder, "name": part.filename,
                        "data": base64.b64encode(bytes(data)).decode()}, timeout=180)
        done.append(r["name"])
    if not done:
        raise ValueError("Tidak ada berkas.")
    return core.ok(files=done)


# ---------------------------------------------------------------- toko aplikasi

async def h_apt_search(req):
    d = await req.json()
    q = str(d.get("q", "")).strip()
    if q:
        r = await call({"type": "apt_search", "q": q}, timeout=60)
    else:
        r = await call({"type": "apt_info", "pkgs": POPULAR}, timeout=60)
    return core.ok(items=r["items"], popular=not q, root=bool(core.S.debian_info.get("root")))


async def h_apt_run(req):
    d = await req.json()
    action, pkg = d.get("action"), str(d.get("pkg", ""))
    if action not in ("install", "remove", "update") or (action != "update" and not PKG_RE.match(pkg)):
        raise ValueError("Paket tidak valid.")
    r = await call({"type": "apt_run", "action": action, "pkg": pkg, "password": str(d.get("password", ""))})
    return core.ok(root=r.get("root"))


# ---------------------------------------------------------------- sistem

async def h_sys(req):
    r = await call({"type": "sys_info"}, timeout=30)
    return core.ok(**{k: v for k, v in r.items() if k not in ("type", "rid", "ok")})


async def h_kill(req):
    d = await req.json()
    await call({"type": "proc_kill", "pid": int(d.get("pid", 0)), "force": bool(d.get("force"))})
    return core.ok()


async def on_agent_event(d: dict) -> bool:
    """Pesan agen untuk modul ini. True bila sudah ditangani."""
    t = d.get("type")
    if t == "reply":
        fut = core.S.waiters.get("rid:" + str(d.get("rid")))
        if fut and not fut.done():
            fut.set_result(d)
        return True
    if t in ("apt_log", "apt_done"):
        await core.broadcast(d)
        return True
    return False


def register(router, core_module, app) -> None:
    global core
    core = core_module
    r = router
    r.add_post("/api/deb/fs", wrap(h_fs))
    r.add_post("/api/deb/fs/op", wrap(h_fs_op))
    r.add_post("/api/deb/fs/pull", wrap(h_fs_pull))
    r.add_get("/api/deb/fs/raw", h_fs_raw)
    r.add_post("/api/deb/fs/upload", wrap(h_fs_upload))
    r.add_post("/api/deb/apt/search", wrap(h_apt_search))
    r.add_post("/api/deb/apt/run", wrap(h_apt_run))
    r.add_post("/api/deb/sys", wrap(h_sys))
    r.add_post("/api/deb/sys/kill", wrap(h_kill))
