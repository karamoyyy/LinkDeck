"""
Clipboard PC lintas OS untuk LinkDeck.

Windows : API Win32 langsung (ctypes). Perubahan dideteksi lewat GetClipboardSequenceNumber,
          jadi clipboard hanya dibuka saat benar-benar berubah — tidak mengganggu aplikasi lain.
macOS   : NSPasteboard (changeCount) bila pyobjc ada, selain itu pbcopy/pbpaste.
Linux   : pyperclip (xclip, xsel, atau wl-clipboard).
Semua teks dinormalkan ke baris baru "\\n" supaya PC, Android, dan Debian membandingkan isi yang sama.
"""
from __future__ import annotations

import sys
import time


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
        return self.p.paste()

    def set(self, text: str) -> None:
        self.p.copy(text)


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
