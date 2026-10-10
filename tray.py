"""
Ikon tray dan jalan otomatis saat login.

  * Ikon tray      : Windows (menu lengkap) dan Linux (menu bila ada AppIndicator; selain itu klik ikon = buka).
                     macOS tidak memakai ikon tray (jendela dibuka dari Dock).
  * Jalan otomatis : Windows (registry Run pengguna), Linux (~/.config/autostart), macOS (LaunchAgent).
                     LinkDeck dijalankan dengan --tray: diam di tray tanpa membuka jendela.

Modul ini tidak mengimpor server; nilai yang dibutuhkan diberikan lewat parameter.
"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import threading
from pathlib import Path

APP_NAME = "LinkDeck"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MAC_LABEL = "io.github.karamoyyy.linkdeck"


# ================================================================ perintah peluncur

def launch_command(frozen: bool, root: Path) -> list[str]:
    """Perintah untuk menjalankan LinkDeck diam-diam di tray (dipakai jalan otomatis)."""
    if frozen:
        if os.environ.get("APPIMAGE"):
            return [os.environ["APPIMAGE"], "--tray"]
        return [sys.executable, "--tray"]
    if Path(root) == Path("/usr/lib/linkdeck") and shutil.which("linkdeck"):
        return [shutil.which("linkdeck"), "--tray"]               # paket linkdeck-debian
    py = Path(sys.executable)
    if sys.platform == "win32" and (py.parent / "pythonw.exe").exists():
        py = py.parent / "pythonw.exe"                            # tanpa jendela konsol
    return [str(py), str(Path(root) / "app.py"), "--tray"]


def desktop_quote(arg: str) -> str:
    """Kutip satu argumen untuk baris Exec= berkas .desktop (Desktop Entry Specification)."""
    arg = arg.replace("%", "%%")
    if any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        for c in ('\\', '"', '`', '$'):                 # aturan kutip Exec
            arg = arg.replace(c, "\\" + c)
        arg = f'"{arg}"'
    return arg.replace("\\", "\\\\")               # aturan escape nilai string (diterapkan lebih dulu oleh pembaca)


# ================================================================ jalan otomatis

def _linux_file() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "autostart" / "linkdeck.desktop"


def _mac_file() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def autostart_supported() -> bool:
    return sys.platform in ("win32", "darwin") or sys.platform.startswith("linux")


def autostart_status() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, APP_NAME)
            return True
        except OSError:
            return False
    if sys.platform == "darwin":
        return _mac_file().exists()
    return _linux_file().exists()


def autostart_set(on: bool, frozen: bool, root: Path) -> None:
    """Nyalakan/matikan jalan otomatis. Melempar OSError bila gagal."""
    cmd = launch_command(frozen, root)
    if sys.platform == "win32":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            if on:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
        return
    if sys.platform == "darwin":
        f = _mac_file()
        if not on:
            f.unlink(missing_ok=True)
            return
        exe = Path(sys.executable)
        bundle = next((p for p in exe.parents if p.suffix == ".app"), None)
        args = ["/usr/bin/open", "-a", str(bundle), "--args", "--tray"] if frozen and bundle else cmd
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(plistlib.dumps({"Label": MAC_LABEL, "ProgramArguments": args, "RunAtLoad": True,
                                      "ProcessType": "Interactive"}))
        return
    f = _linux_file()
    if not on:
        f.unlink(missing_ok=True)
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("[Desktop Entry]\nType=Application\nName=LinkDeck\n"
                 "Comment=Jalankan LinkDeck di tray saat login\n"
                 f"Exec={' '.join(desktop_quote(a) for a in cmd)}\n"
                 "Icon=linkdeck\nTerminal=false\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")


# ================================================================ ikon tray

def tray_supported() -> bool:
    return sys.platform == "win32" or (sys.platform.startswith("linux") and bool(os.environ.get("DISPLAY")
                                                                                    or os.environ.get("WAYLAND_DISPLAY")))


def icon_image(size: int = 64):
    """Logo LinkDeck (laptop + HP) digambar dengan Pillow, tanpa berkas gambar."""
    from PIL import Image, ImageDraw
    s = size / 32
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3 * s, 6 * s, 22 * s, 20 * s], radius=4 * s, fill=(236, 198, 245, 255))
    d.rounded_rectangle([17 * s, 11 * s, 28 * s, 28 * s], radius=3.5 * s, fill=(191, 230, 248, 255),
                        outline=(29, 32, 48, 255), width=max(1, round(2 * s)))
    return im


class Tray:
    """Ikon tray dengan menu: Buka LinkDeck (bawaan, juga klik ikon), Tampilkan layar Android, Keluar."""

    LABELS = {"id": ("Buka LinkDeck", "Tampilkan layar Android", "Keluar dari LinkDeck"),
              "en": ("Open LinkDeck", "Show Android screen", "Quit LinkDeck")}

    def __init__(self, on_open, on_quit, on_mirror=None, lang: str = "id") -> None:
        self.on_open, self.on_quit, self.on_mirror = on_open, on_quit, on_mirror
        self.labels = self.LABELS.get(lang, self.LABELS["id"])
        self.icon = None
        self.error: str | None = None
        self.has_menu = False
        self.has_notify = False

    def create(self) -> bool:
        if not tray_supported():
            self.error = "sistem ini tidak punya area tray"
            return False
        try:
            import pystray                       # di Linux tanpa layar, impor ini sudah gagal
        except Exception as e:
            self.error = f"pystray tidak tersedia: {e}"
            return False
        open_l, mirror_l, quit_l = self.labels
        items = [pystray.MenuItem(open_l, lambda *_: self.on_open(), default=True)]
        if self.on_mirror:
            items.append(pystray.MenuItem(mirror_l, lambda *_: self.on_mirror()))
        items += [pystray.Menu.SEPARATOR, pystray.MenuItem(quit_l, lambda *_: self.on_quit())]
        try:
            self.icon = pystray.Icon("linkdeck", icon_image(64), "LinkDeck", menu=pystray.Menu(*items))
        except Exception as e:
            self.error = f"ikon tray gagal dibuat: {e}"
            return False
        if type(self.icon).__module__.endswith("_xorg"):
            self._fix_xorg_clicks()
        self.has_menu = getattr(self.icon, "HAS_MENU", False)
        self.has_notify = getattr(self.icon, "HAS_NOTIFICATION", False)
        return True

    def _fix_xorg_clicks(self) -> None:
        """Backend Xorg pystray tidak meminta event klik untuk jendela ikonnya, jadi klik diabaikan."""
        try:
            import Xlib.X
            win = self.icon._window
            win.change_attributes(event_mask=Xlib.X.ExposureMask | Xlib.X.StructureNotifyMask | Xlib.X.ButtonPressMask)
            self.icon._display.flush()
        except Exception as e:
            print("[tray] klik ikon mungkin tidak berfungsi:", e, flush=True)

    def run(self) -> None:
        """Blok sampai stop(). Dipanggil di thread utama (Linux) atau thread sendiri (Windows)."""
        try:
            self.icon.run()
        except Exception as e:
            self.error = f"ikon tray berhenti: {e}"
            print("[tray]", self.error, flush=True)

    def run_in_thread(self) -> threading.Thread:
        t = threading.Thread(target=self.run, name="linkdeck-tray", daemon=True)
        t.start()
        return t

    def visible(self) -> bool:
        """True bila ikon benar-benar tampil. Backend Xorg tanpa area tray tidak bisa menampilkan ikon."""
        if not self.icon:
            return False
        if type(self.icon).__module__.endswith("_xorg"):
            return getattr(self.icon, "_systray_manager", None) is not None
        return True

    def notify(self, message: str) -> None:
        if self.icon and self.has_notify:
            try:
                self.icon.notify(message, "LinkDeck")
            except Exception:
                pass

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
