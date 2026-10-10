"""
Clipboard PC lintas OS untuk LinkDeck.

Windows : API Win32 langsung (ctypes). Perubahan dideteksi lewat GetClipboardSequenceNumber,
          jadi clipboard hanya dibuka saat benar-benar berubah — tidak mengganggu aplikasi lain.
macOS   : NSPasteboard (changeCount) bila pyobjc ada, selain itu pbcopy/pbpaste.
Linux   : pyperclip (xclip, xsel, atau wl-clipboard).
Semua teks dinormalkan ke baris baru "\\n" supaya PC, Android, dan Debian membandingkan isi yang sama.
"""
from __future__ import annotations

import io
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse


FILES_MAX = 20                              # berkas per salinan
TEXT_TYPES = ("UTF8_STRING", "STRING", "TEXT", "text/plain", "text/plain;charset=utf-8", "COMPOUND_TEXT")


def uri_paths(text: str) -> list[str]:
    """Baris file:// (text/uri-list atau x-special/gnome-copied-files) -> jalur berkas yang ada."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("file://"):
            p = unquote(urlparse(line).path)
            if os.path.isfile(p):
                out.append(p)
    return out[:FILES_MAX]


def gnome_files(paths: list[str]) -> bytes:
    return ("copy\n" + "\n".join(Path(p).resolve().as_uri() for p in paths)).encode()


def png_from_any(data: bytes) -> bytes:
    """Gambar apa pun yang dibaca Pillow -> PNG. Alfa yang seluruhnya 0 (DIB Windows) dibuang."""
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode == "RGBA" and im.getextrema()[3] == (0, 0):
        im = im.convert("RGB")
    if im.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        im = im.convert("RGBA")
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def dib_to_png(dib: bytes) -> bytes:
    """CF_DIB Windows (BITMAPINFO + piksel) -> PNG: beri kepala berkas BMP lalu baca dengan Pillow."""
    hsize, bits = struct.unpack_from("<I", dib, 0)[0], struct.unpack_from("<H", dib, 14)[0]
    comp, used = struct.unpack_from("<I", dib, 16)[0], struct.unpack_from("<I", dib, 32)[0]
    table = (used or (1 << bits)) * 4 if bits <= 8 else 0
    if comp in (3, 6) and hsize == 40:
        table += 12 if comp == 3 else 16              # masker BI_BITFIELDS / BI_ALPHABITFIELDS
    bmp = b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, 14 + hsize + table) + dib
    return png_from_any(bmp)


def png_to_dib(png: bytes) -> bytes:
    """PNG -> CF_DIB (24-bit) untuk aplikasi Windows yang tidak mengenal format PNG."""
    from PIL import Image
    im = Image.open(io.BytesIO(png))
    im.load()
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        im = bg
    out = io.BytesIO()
    im.convert("RGB").save(out, "BMP")
    return out.getvalue()[14:]


def normalize(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n")


class _Pyperclip:
    name = "pyperclip"

    def __init__(self) -> None:
        import pyperclip
        self.p = pyperclip

    def token(self):
        return None            # tidak ada penanda perubahan murah: baca setiap kali

    def get(self) -> str | None:
        if self._tool():
            t = self.targets()
            if t and not any(x in t for x in TEXT_TYPES):
                return None          # isinya gambar/berkas saja: jangan dibaca sebagai teks
        return self.p.paste()

    def set(self, text: str) -> None:
        self.p.copy(text)

    # gambar & berkas (Linux; macOS lewat pyperclip hanya teks)
    def _tool(self):
        if sys.platform.startswith("linux"):
            if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste") and shutil.which("wl-copy"):
                return "wl"
            if shutil.which("xclip") and os.environ.get("DISPLAY"):
                return "xclip"
        return None

    @property
    def rich(self) -> bool:
        return self._tool() is not None

    def _read(self, target: str) -> bytes | None:
        tool = self._tool()
        cmd = (["wl-paste", "--no-newline", "-t", target] if tool == "wl"
               else ["xclip", "-selection", "clipboard", "-t", target, "-o"])
        r = subprocess.run(cmd, capture_output=True, timeout=5)
        return r.stdout if r.returncode == 0 else None

    def _write(self, target: str, data: bytes) -> None:
        tool = self._tool()
        cmd = ["wl-copy", "-t", target] if tool == "wl" else ["xclip", "-selection", "clipboard", "-t", target, "-i"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p.communicate(data, timeout=5)
        for _ in range(20):                          # tunggu sampai pemilik clipboard berganti
            if target in self.targets():
                break
            time.sleep(0.05)

    def targets(self) -> list[str]:
        tool = self._tool()
        if not tool:
            return []
        if tool == "wl":
            r = subprocess.run(["wl-paste", "--list-types"], capture_output=True, timeout=3)
        else:
            r = subprocess.run(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"], capture_output=True, timeout=3)
        return r.stdout.decode(errors="replace").split() if r.returncode == 0 else []

    def rich_kind(self) -> str | None:
        t = self.targets()
        if not t:
            return "?"                               # gagal baca sesaat: status tidak diketahui
        if "x-special/gnome-copied-files" in t or "text/uri-list" in t:
            if self.get_files():
                return "files"
        if "image/png" in t:
            return "image"
        return None

    def get_image(self) -> bytes | None:
        return self._read("image/png")

    def set_image(self, png: bytes) -> None:
        self._write("image/png", png)

    def get_files(self) -> list[str]:
        t = self.targets()
        for target in ("x-special/gnome-copied-files", "text/uri-list"):
            if target in t:
                paths = uri_paths((self._read(target) or b"").decode(errors="replace"))
                if paths:
                    return paths
        return []

    def set_files(self, paths: list[str]) -> None:
        self._write("x-special/gnome-copied-files", gnome_files(paths))


class _Windows:
    name = "win32"
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        u.OpenClipboard.argtypes = [wintypes.HWND]
        u.OpenClipboard.restype = wintypes.BOOL
        u.CloseClipboard.restype = wintypes.BOOL
        u.EmptyClipboard.restype = wintypes.BOOL
        u.GetClipboardData.argtypes = [wintypes.UINT]
        u.GetClipboardData.restype = wintypes.HANDLE
        u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u.SetClipboardData.restype = wintypes.HANDLE
        u.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        u.IsClipboardFormatAvailable.restype = wintypes.BOOL
        u.GetClipboardSequenceNumber.restype = wintypes.DWORD
        u.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        u.RegisterClipboardFormatW.restype = wintypes.UINT
        k.GlobalSize.argtypes = [wintypes.HGLOBAL]
        k.GlobalSize.restype = ctypes.c_size_t
        sh = ctypes.WinDLL("shell32", use_last_error=True)
        sh.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        sh.DragQueryFileW.restype = wintypes.UINT
        self.sh = sh
        self.CF_PNG = u.RegisterClipboardFormatW("PNG")
        self.CF_DROPEFFECT = u.RegisterClipboardFormatW("Preferred DropEffect")
        k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k.GlobalAlloc.restype = wintypes.HGLOBAL
        k.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k.GlobalLock.restype = wintypes.LPVOID
        k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k.GlobalUnlock.restype = wintypes.BOOL
        k.GlobalFree.argtypes = [wintypes.HGLOBAL]
        k.GlobalFree.restype = wintypes.HGLOBAL
        self.u, self.k = u, k

    def _open(self) -> None:
        for _ in range(25):                     # aplikasi lain mungkin sedang memegang clipboard
            if self.u.OpenClipboard(None):
                return
            time.sleep(0.02)
        raise OSError("clipboard sedang dipakai aplikasi lain")

    def token(self):
        return int(self.u.GetClipboardSequenceNumber())

    def get(self) -> str | None:
        if not self.u.IsClipboardFormatAvailable(self.CF_UNICODETEXT):
            return None                         # isinya bukan teks (gambar, berkas, dll.)
        self._open()
        try:
            h = self.u.GetClipboardData(self.CF_UNICODETEXT)
            if not h:
                return None
            p = self.k.GlobalLock(h)
            if not p:
                return None
            try:
                return self.ct.wstring_at(p)
            finally:
                self.k.GlobalUnlock(h)
        finally:
            self.u.CloseClipboard()

    # ---- gambar & berkas
    rich = True
    CF_DIB, CF_HDROP = 8, 15

    def rich_kind(self) -> str | None:
        if self.u.IsClipboardFormatAvailable(self.CF_HDROP):
            return "files"
        if self.u.IsClipboardFormatAvailable(self.CF_PNG) or self.u.IsClipboardFormatAvailable(self.CF_DIB):
            return "image"
        return None

    def _bytes(self, fmt: int) -> bytes | None:
        h = self.u.GetClipboardData(fmt)
        if not h:
            return None
        size, p = self.k.GlobalSize(h), self.k.GlobalLock(h)
        if not p:
            return None
        try:
            return self.ct.string_at(p, size)
        finally:
            self.k.GlobalUnlock(h)

    def _alloc(self, data: bytes):
        h = self.k.GlobalAlloc(self.GMEM_MOVEABLE, len(data))
        if not h:
            raise OSError("GlobalAlloc gagal")
        p = self.k.GlobalLock(h)
        self.ct.memmove(p, data, len(data))
        self.k.GlobalUnlock(h)
        return h

    def _put(self, fmt: int, data: bytes) -> None:
        h = self._alloc(data)
        if not self.u.SetClipboardData(fmt, h):
            self.k.GlobalFree(h)
            raise OSError("SetClipboardData gagal")

    def get_image(self) -> bytes | None:
        self._open()
        try:
            png = self._bytes(self.CF_PNG) if self.u.IsClipboardFormatAvailable(self.CF_PNG) else None
            dib = None if png else self._bytes(self.CF_DIB)
        finally:
            self.u.CloseClipboard()
        if png:
            return png
        return dib_to_png(dib) if dib and len(dib) >= 40 else None

    def set_image(self, png: bytes) -> None:
        dib = png_to_dib(png)
        self._open()
        try:
            self.u.EmptyClipboard()
            self._put(self.CF_DIB, dib)
            self._put(self.CF_PNG, png)
        finally:
            self.u.CloseClipboard()

    def get_files(self) -> list[str]:
        self._open()
        try:
            h = self.u.GetClipboardData(self.CF_HDROP)
            if not h:
                return []
            n = self.sh.DragQueryFileW(h, 0xFFFFFFFF, None, 0)
            out = []
            for i in range(min(n, FILES_MAX * 5)):
                ln = self.sh.DragQueryFileW(h, i, None, 0)
                buf = self.ct.create_unicode_buffer(ln + 1)
                self.sh.DragQueryFileW(h, i, buf, ln + 1)
                out.append(buf.value)
        finally:
            self.u.CloseClipboard()
        return [p for p in out if os.path.isfile(p)][:FILES_MAX]

    def set_files(self, paths: list[str]) -> None:
        names = ("\0".join(str(Path(p).resolve()) for p in paths) + "\0\0").encode("utf-16-le")
        dropfiles = struct.pack("<IiiII", 20, 0, 0, 0, 1) + names       # DROPFILES, fWide=1
        self._open()
        try:
            self.u.EmptyClipboard()
            self._put(self.CF_HDROP, dropfiles)
            self._put(self.CF_DROPEFFECT, struct.pack("<I", 1))         # DROPEFFECT_COPY
        finally:
            self.u.CloseClipboard()

    def set(self, text: str) -> None:
        buf = self.ct.create_unicode_buffer(text.replace("\n", "\r\n"))
        size = self.ct.sizeof(buf)
        self._open()
        try:
            self.u.EmptyClipboard()
            h = self.k.GlobalAlloc(self.GMEM_MOVEABLE, size)
            if not h:
                raise OSError("GlobalAlloc gagal")
            p = self.k.GlobalLock(h)
            self.ct.memmove(p, buf, size)
            self.k.GlobalUnlock(h)
            if not self.u.SetClipboardData(self.CF_UNICODETEXT, h):
                self.k.GlobalFree(h)
                raise OSError("SetClipboardData gagal")
        finally:
            self.u.CloseClipboard()


class _MacAppKit:
    name = "appkit"

    def __init__(self) -> None:
        from AppKit import NSPasteboard, NSPasteboardTypeString
        self.pb = NSPasteboard.generalPasteboard()
        self.t = NSPasteboardTypeString

    def token(self):
        return int(self.pb.changeCount())

    def get(self) -> str | None:
        v = self.pb.stringForType_(self.t)
        return str(v) if v is not None else None

    def set(self, text: str) -> None:
        self.pb.clearContents()
        self.pb.setString_forType_(text, self.t)


class PCClipboard:
    """Pembungkus dengan cadangan otomatis; .error berisi pesan terakhir bila gagal."""

    def __init__(self) -> None:
        self.backend = None
        self.error: str | None = None
        order = {"win32": [_Windows, _Pyperclip], "darwin": [_MacAppKit, _Pyperclip]}.get(sys.platform, [_Pyperclip])
        problems = []
        for cls in order:
            try:
                self.backend = cls()
                break
            except Exception as e:  # coba yang berikutnya
                problems.append(f"{cls.__name__}: {e}")
        if self.backend is None:
            self.error = "Clipboard PC tidak tersedia (" + "; ".join(problems) + ")"

    @property
    def name(self) -> str:
        return self.backend.name if self.backend else "tidak ada"

    @property
    def available(self) -> bool:
        return self.backend is not None

    def token(self):
        return self.backend.token() if self.backend else None

    def get(self) -> str | None:
        if not self.backend:
            return None
        return normalize(self.backend.get())

    def set(self, text: str) -> None:
        if self.backend:
            self.backend.set(text)

    # gambar & berkas: Windows dan Linux (X11/Wayland); macOS hanya teks
    @property
    def rich(self) -> bool:
        if not self.backend or not getattr(self.backend, "rich", False):
            return False
        try:
            import PIL  # noqa: F401  (dibutuhkan untuk gambar di Windows)
        except ImportError:
            return sys.platform != "win32"
        return True

    def rich_kind(self) -> str | None:
        return self.backend.rich_kind() if self.rich else None

    def get_image(self) -> bytes | None:
        return self.backend.get_image() if self.rich else None

    def set_image(self, png: bytes) -> None:
        if self.rich:
            self.backend.set_image(png)

    def get_files(self) -> list[str]:
        return self.backend.get_files() if self.rich else []

    def set_files(self, paths: list[str]) -> None:
        if self.rich:
            self.backend.set_files(paths)
