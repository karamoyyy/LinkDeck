"""
Satu mouse & keyboard untuk PC dan Debian (eksperimental).

Kursor PC menyentuh tepi layar yang dipilih -> input "ditangkap" dan dikirim ke Debian.
Kursor Debian menyentuh tepi seberangnya -> kembali ke PC. Darurat: Ctrl+Alt+Home.

Backend:
  Windows : hook low-level pynput + suppress_event per kejadian
  macOS   : event tap pynput (butuh izin Aksesibilitas) + kursor dibekukan
  Linux   : X11 (pynput/RECORD); saat ditangkap pointer & keyboard di-grab, kursor dijaga di tengah
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time

WIN_VK = {
    0x08: "BackSpace", 0x09: "Tab", 0x0D: "Return", 0x10: "Shift_L", 0x11: "Control_L", 0x12: "Alt_L",
    0x13: "Pause", 0x14: "Caps_Lock", 0x1B: "Escape", 0x20: "space", 0x21: "Prior", 0x22: "Next",
    0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down", 0x2C: "Print",
    0x2D: "Insert", 0x2E: "Delete", 0x5B: "Super_L", 0x5C: "Super_R", 0x5D: "Menu",
    0x6A: "KP_Multiply", 0x6B: "KP_Add", 0x6D: "KP_Subtract", 0x6E: "KP_Decimal", 0x6F: "KP_Divide",
    0x90: "Num_Lock", 0x91: "Scroll_Lock", 0xA0: "Shift_L", 0xA1: "Shift_R", 0xA2: "Control_L",
    0xA3: "Control_R", 0xA4: "Alt_L", 0xA5: "Alt_R", 0xBA: "semicolon", 0xBB: "equal", 0xBC: "comma",
    0xBD: "minus", 0xBE: "period", 0xBF: "slash", 0xC0: "grave", 0xDB: "bracketleft",
    0xDC: "backslash", 0xDD: "bracketright", 0xDE: "apostrophe",
    **{0x60 + i: f"KP_{i}" for i in range(10)}, **{0x70 + i: f"F{i + 1}" for i in range(24)},
}

MAC_KC = {
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x", 8: "c", 9: "v", 11: "b", 12: "q",
    13: "w", 14: "e", 15: "r", 16: "y", 17: "t", 18: "1", 19: "2", 20: "3", 21: "4", 22: "6", 23: "5",
    24: "equal", 25: "9", 26: "7", 27: "minus", 28: "8", 29: "0", 30: "bracketright", 31: "o", 32: "u",
    33: "bracketleft", 34: "i", 35: "p", 36: "Return", 37: "l", 38: "j", 39: "apostrophe", 40: "k",
    41: "semicolon", 42: "backslash", 43: "comma", 44: "slash", 45: "n", 46: "m", 47: "period",
    48: "Tab", 49: "space", 50: "grave", 51: "BackSpace", 53: "Escape", 54: "Control_R", 55: "Control_L",
    56: "Shift_L", 57: "Caps_Lock", 58: "Alt_L", 59: "Control_L", 60: "Shift_R", 61: "Alt_R",
    62: "Control_R", 65: "KP_Decimal", 67: "KP_Multiply", 69: "KP_Add", 75: "KP_Divide",
    76: "KP_Enter", 78: "KP_Subtract", 82: "KP_0", 83: "KP_1", 84: "KP_2", 85: "KP_3", 86: "KP_4",
    87: "KP_5", 88: "KP_6", 89: "KP_7", 91: "KP_8", 92: "KP_9", 96: "F5", 97: "F6", 98: "F7", 99: "F3",
    100: "F8", 101: "F9", 103: "F11", 109: "F10", 111: "F12", 114: "Insert", 115: "Home", 116: "Prior",
    117: "Delete", 118: "F4", 119: "End", 120: "F2", 121: "Next", 122: "F1", 123: "Left", 124: "Right",
    125: "Down", 126: "Up",
}
# Command di Mac dipetakan ke Control agar Cmd+C / Cmd+V tetap terasa wajar di Debian
MAC_FLAG = {56: 0x20000, 60: 0x20000, 59: 0x40000, 62: 0x40000, 58: 0x80000, 61: 0x80000,
            55: 0x100000, 54: 0x100000, 57: 0x10000}

PYNPUT_KEYS = {
    "alt": "Alt_L", "alt_l": "Alt_L", "alt_r": "Alt_R", "alt_gr": "ISO_Level3_Shift",
    "backspace": "BackSpace", "caps_lock": "Caps_Lock", "cmd": "Super_L", "cmd_l": "Super_L",
    "cmd_r": "Super_R", "ctrl": "Control_L", "ctrl_l": "Control_L", "ctrl_r": "Control_R",
    "delete": "Delete", "down": "Down", "end": "End", "enter": "Return", "esc": "Escape", "home": "Home",
    "left": "Left", "page_down": "Next", "page_up": "Prior", "right": "Right", "shift": "Shift_L",
    "shift_l": "Shift_L", "shift_r": "Shift_R", "space": "space", "tab": "Tab", "up": "Up",
    "insert": "Insert", "menu": "Menu", "num_lock": "Num_Lock", "pause": "Pause",
    "print_screen": "Print", "scroll_lock": "Scroll_Lock",
    **{f"f{i}": f"F{i}" for i in range(1, 25)},
}


def desktop_bounds() -> tuple[int, int, int, int]:
    """(kiri, atas, kanan, bawah) seluruh desktop gabungan semua monitor."""
    if sys.platform == "win32":
        u = ctypes.windll.user32
        u.SetProcessDPIAware()
        x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        return x, y, x + u.GetSystemMetrics(78), y + u.GetSystemMetrics(79)
    if sys.platform == "darwin":
        import Quartz
        err, ids, n = Quartz.CGGetActiveDisplayList(16, None, None)
        rects = [Quartz.CGDisplayBounds(i) for i in ids[:n]]
        return (int(min(r.origin.x for r in rects)), int(min(r.origin.y for r in rects)),
                int(max(r.origin.x + r.size.width for r in rects)),
                int(max(r.origin.y + r.size.height for r in rects)))
    from Xlib import display
    g = display.Display().screen().root.get_geometry()
    return 0, 0, g.width, g.height


class KVM:
    def __init__(self, send, on_state):
        """send(dict) dipanggil dari thread listener; on_state(bool) saat status tangkap berubah."""
        self.send = send
        self.on_state = on_state
        self.edge = "right"
        self.running = False
        self.captured = False
        self.mods: set[str] = set()
        self._lock = threading.Lock()
        self._listeners = []
        self._grab = []
        self._anchor = (0, 0)
        self._last_cap = 0.0

    # ---------------------------------------------------------- umum
    def start(self, edge: str = "right") -> None:
        if self.running:
            self.stop()
        try:
            from pynput import keyboard, mouse  # noqa: F401
        except Exception as e:
            raise RuntimeError(f"Kontrol input tidak tersedia di sistem ini ({e}). "
                               "Di Linux butuh sesi X11 (Wayland belum didukung).")
        self.edge = edge if edge in ("left", "right") else "right"
        self.bounds = desktop_bounds()
        self.running = True
        if sys.platform == "win32":
            self._start_windows()
        elif sys.platform == "darwin":
            self._start_mac()
        else:
            self._start_x11()

    def stop(self) -> None:
        self.release(None)
        self.running = False
        for lst in self._listeners + self._grab:
            try:
                lst.stop()
            except Exception:
                pass
        self._listeners, self._grab = [], []

    def _at_edge(self, x, y) -> bool:
        l, t, r, b = self.bounds
        if time.time() - self._last_cap < 0.6:     # cegah langsung tertangkap lagi setelah kembali
            return False
        return x >= r - 1 if self.edge == "right" else x <= l

    def _fy(self, y) -> float:
        l, t, r, b = self.bounds
        return min(1.0, max(0.0, (y - t) / max(1, b - t - 1)))

    def capture(self, x, y) -> None:
        with self._lock:
            if self.captured:
                return
            self.captured = True
        self._anchor = (int(x), int(y))
        self.mods.clear()
        self.send({"type": "in", "k": "enter", "edge": "left" if self.edge == "right" else "right",
                   "fy": self._fy(y)})
        self._platform_capture()
        self.on_state(True)

    def release(self, fy: float | None) -> None:
        with self._lock:
            if not self.captured:
                return
            self.captured = False
        self._last_cap = time.time()
        self._platform_release()
        self.send({"type": "in", "k": "reset"})
        try:
            from pynput import mouse
            l, t, r, b = self.bounds
            y = t + (fy if fy is not None else self._fy(self._anchor[1])) * (b - t - 1)
            mouse.Controller().position = ((r - 40) if self.edge == "right" else (l + 40), int(y))
        except Exception:
            pass
        self.on_state(False)

    def _key(self, sym: str | None, down: bool) -> None:
        if not sym:
            return
        base = sym.split("_")[0]
        (self.mods.add if down else self.mods.discard)(base)
        if down and sym == "Home" and {"Control", "Alt"} <= self.mods:
            threading.Thread(target=self.release, args=(None,), daemon=True).start()
            return
        self.send({"type": "in", "k": "key", "sym": sym, "down": down})

    def _platform_capture(self):
        if sys.platform == "darwin":
            import Quartz
            Quartz.CGAssociateMouseAndMouseCursorPosition(False)
        elif sys.platform.startswith("linux"):
            self._x11_grab(True)

    def _platform_release(self):
        if sys.platform == "darwin":
            import Quartz
            Quartz.CGAssociateMouseAndMouseCursorPosition(True)
        elif sys.platform.startswith("linux"):
            self._x11_grab(False)

    # ---------------------------------------------------------- Windows
    def _start_windows(self):
        from pynput import keyboard, mouse
        BTN = {0x201: (1, True), 0x202: (1, False), 0x204: (3, True), 0x205: (3, False),
               0x207: (2, True), 0x208: (2, False)}

        def mfilter(msg, data):
            if not self.captured:
                if msg == 0x200 and self._at_edge(data.pt.x, data.pt.y):
                    self.capture(data.pt.x, data.pt.y)
                return True
            if msg == 0x200:
                dx, dy = data.pt.x - self._anchor[0], data.pt.y - self._anchor[1]
                if dx or dy:
                    self.send({"type": "in", "k": "move", "dx": dx, "dy": dy})
            elif msg in BTN:
                b, down = BTN[msg]
                self.send({"type": "in", "k": "btn", "b": b, "down": down})
            elif msg in (0x20A, 0x20E):
                delta = ctypes.c_short(data.mouseData >> 16).value // 120
                self.send({"type": "in", "k": "scroll", "dx": delta if msg == 0x20E else 0,
                           "dy": delta if msg == 0x20A else 0})
            ml.suppress_event()

        def kfilter(msg, data):
            if not self.captured:
                return True
            vk = data.vkCode
            sym = WIN_VK.get(vk) or (chr(vk).lower() if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39 else None)
            self._key(sym, msg in (0x100, 0x104))
            kl.suppress_event()

        ml = mouse.Listener(win32_event_filter=mfilter)
        kl = keyboard.Listener(win32_event_filter=kfilter)
        ml.start()
        kl.start()
        self._listeners = [ml, kl]

    # ---------------------------------------------------------- macOS
    def _start_mac(self):
        import Quartz
        from pynput import keyboard, mouse
        BTN = {1: (1, True), 2: (1, False), 3: (3, True), 4: (3, False), 25: (2, True), 26: (2, False)}
        MOVES = (5, 6, 7, 27)   # moved, left/right/other dragged

        def mintercept(etype, event):
            if not self.captured:
                if etype in MOVES:
                    loc = Quartz.CGEventGetLocation(event)
                    if self._at_edge(loc.x, loc.y):
                        self.capture(loc.x, loc.y)
                return event
            if etype in MOVES:
                dx = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventDeltaX)
                dy = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventDeltaY)
                if dx or dy:
                    self.send({"type": "in", "k": "move", "dx": dx, "dy": dy})
            elif etype in BTN:
                b, down = BTN[etype]
                self.send({"type": "in", "k": "btn", "b": b, "down": down})
            elif etype == 22:
                dy = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGScrollWheelEventDeltaAxis1)
                dx = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGScrollWheelEventDeltaAxis2)
                self.send({"type": "in", "k": "scroll", "dx": -dx, "dy": dy})
            return None

        def kintercept(etype, event):
            if not self.captured:
                return event
            kc = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            sym = MAC_KC.get(kc)
            if etype == 12:   # perubahan tombol modifier
                down = bool(Quartz.CGEventGetFlags(event) & MAC_FLAG.get(kc, 0))
                self._key(sym, down)
            elif etype in (10, 11):
                self._key(sym, etype == 10)
            return None

        ml = mouse.Listener(darwin_intercept=mintercept)
        kl = keyboard.Listener(darwin_intercept=kintercept)
        ml.start()
        kl.start()
        self._listeners = [ml, kl]

    # ---------------------------------------------------------- Linux X11
    def _start_x11(self):
        from pynput import mouse

        def on_move(x, y):
            if not self.captured and self._at_edge(x, y):
                self.capture(x, y)

        ml = mouse.Listener(on_move=on_move)
        ml.start()
        self._listeners = [ml]

    def _x11_grab(self, on: bool):
        from pynput import keyboard, mouse
        if not on:
            for lst in self._grab:
                lst.stop()
            self._grab = []
            return
        l, t, r, b = self.bounds
        cx, cy = (l + r) // 2, (t + b) // 2
        ctl = mouse.Controller()
        ctl.position = (cx, cy)

        def on_move(x, y):
            if not self.captured:
                return
            dx, dy = x - cx, y - cy
            if dx or dy:
                self.send({"type": "in", "k": "move", "dx": dx, "dy": dy})
                ctl.position = (cx, cy)

        def on_click(x, y, button, pressed):
            if self.captured:
                b = {mouse.Button.left: 1, mouse.Button.middle: 2, mouse.Button.right: 3}.get(button)
                if b:
                    self.send({"type": "in", "k": "btn", "b": b, "down": pressed})

        def on_scroll(x, y, dx, dy):
            if self.captured:
                self.send({"type": "in", "k": "scroll", "dx": dx, "dy": dy})

        def keysym(key):
            name = getattr(key, "name", None)
            if name:
                return PYNPUT_KEYS.get(name)
            ch = getattr(key, "char", None)
            return ch if ch else None

        gm = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll, suppress=True)
        gk = keyboard.Listener(on_press=lambda k: self._key(keysym(k), True),
                               on_release=lambda k: self._key(keysym(k), False), suppress=True)
        gm.start()
        gk.start()
        self._grab = [gm, gk]
