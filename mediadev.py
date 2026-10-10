"""
HP sebagai perangkat laptop (tahap 3):

  * Mikrofon HP  : scrcpy-server merekam mikrofon HP (PCM mentah 48 kHz stereo) lalu LinkDeck memutarnya ke
                   "kabel audio virtual" sehingga aplikasi meeting melihatnya sebagai mikrofon.
                     - Linux   : dibuat otomatis lewat PulseAudio/PipeWire (pactl + pacat), tanpa pasang apa pun.
                     - Windows : VB-CABLE (gratis) — LinkDeck memutar ke "CABLE Input", aplikasi memilih "CABLE Output".
                     - macOS   : BlackHole 2ch (gratis) — aplikasi memilih "BlackHole 2ch".
  * Webcam HP    : (Windows/macOS) video kamera HP (H.264) didekode PyAV lalu dikirim ke OBS Virtual Camera
                   lewat pyvirtualcam. Linux tetap memakai scrcpy --v4l2-sink.

Kedua sesi didaftarkan di S.sessions seperti jendela scrcpy, sehingga muncul di daftar sesi dan bisa dihentikan
dengan cara yang sama. Didaftarkan oleh server.build_app() lewat register(router, core, app).
"""
from __future__ import annotations

import asyncio
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading

core = None
JAR = "/data/local/tmp/linkdeck-media.jar"
RATE, CHANNELS = 48000, 2
PULSE_SINK, PULSE_SOURCE = "linkdeck_mic", "linkdeck_mic_src"
VIRTUAL_PATTERNS = {"win32": ("CABLE Input", "VoiceMeeter Input", "VoiceMeeter VAIO", "VB-Audio"),
                    "darwin": ("BlackHole", "Loopback Audio", "VB-Cable")}
GUIDE = {
    "win32": "Pasang VB-CABLE (gratis) dari vb-audio.com/Cable, mulai ulang komputer, lalu coba lagi. "
             "Di aplikasi meeting pilih mikrofon \"CABLE Output\".",
    "darwin": "Pasang BlackHole 2ch (gratis) dari existential.audio/blackhole, lalu coba lagi. "
              "Di aplikasi meeting pilih mikrofon \"BlackHole 2ch\".",
    "linux": "Pasang pulseaudio-utils (sudo apt install pulseaudio-utils) agar perintah pactl/pacat tersedia.",
}


def plat() -> str:
    return "linux" if sys.platform.startswith("linux") else sys.platform


# ================================================================ sambungan scrcpy-server

async def open_server(serial: str, args: list[str]):
    """Jalankan scrcpy-server dengan SATU soket (audio saja atau video saja). Mengembalikan (proc, port, reader, writer)."""
    jar, version = core.server_jar()
    if not jar or not version:
        raise ValueError("scrcpy-server tidak ditemukan.")
    c, _, e = await core.run("adb", "-s", serial, "push", str(jar), JAR, timeout=60)
    if c:
        raise ValueError(f"Gagal mengirim server ke HP: {e.strip()[:150]}")
    scid = f"{secrets.randbelow(0x7FFFFFFF):08x}"
    c, out, e = await core.run("adb", "-s", serial, "forward", "tcp:0", f"localabstract:scrcpy_{scid}", timeout=10)
    if c or not out.strip().isdigit():
        raise ValueError(f"adb forward gagal: {(out + e).strip()[:150]}")
    port = int(out.strip())
    cmd = (f"CLASSPATH={JAR} app_process / com.genymobile.scrcpy.Server {version} scid={scid} log_level=warn "
           "tunnel_forward=true send_device_meta=false control=false cleanup=true " + " ".join(args))
    proc = await asyncio.create_subprocess_exec("adb", "-s", serial, "shell", cmd, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT, creationflags=core.NOWIN)
    for _ in range(60):
        if proc.returncode is not None:
            out = (await proc.stdout.read()).decode(errors="replace").strip()
            await core.run("adb", "-s", serial, "forward", "--remove", f"tcp:{port}", timeout=5)
            raise ValueError("Server di HP berhenti. " + (out.splitlines()[-1] if out else ""))
        try:
            r, w = await asyncio.open_connection("127.0.0.1", port)
            await asyncio.wait_for(r.readexactly(1), 2)          # byte penanda koneksi
            return proc, port, r, w
        except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            await asyncio.sleep(0.25)
    proc.kill()
    await core.run("adb", "-s", serial, "forward", "--remove", f"tcp:{port}", timeout=5)
    raise ValueError("Server di HP tidak menjawab.")


async def read_codec(r) -> bytes:
    codec = await asyncio.wait_for(r.readexactly(4), 15)
    if codec == b"\x00\x00\x00\x00":
        raise ValueError("HP menolak merekam (butuh Android 11 ke atas; di Android 11 buka kunci layar dulu).")
    if codec == b"\x00\x00\x00\x01":
        raise ValueError("Pengaturan perekaman tidak didukung HP ini.")
    return codec


async def packets(r):
    """Paket scrcpy: [pts+flag u64][ukuran u32][data]. Meta sesi (bit tertinggi) dilewati, ukuran dikembalikan."""
    while True:
        head = await r.readexactly(12)
        if head[0] & 0x80:
            yield "size", (int.from_bytes(head[4:8], "big"), int.from_bytes(head[8:12], "big"))
            continue
        flags = int.from_bytes(head[0:8], "big")
        data = await r.readexactly(int.from_bytes(head[8:12], "big"))
        yield ("config" if flags & (1 << 62) else "key" if flags & (1 << 61) else "frame"), data


# ================================================================ keluaran audio

class PulseOut:
    """Linux (PulseAudio/PipeWire lewat pactl & pacat).
    mode 'virtual': buat mikrofon virtual "Mikrofon HP (LinkDeck)" dan putar ke sana (+ speaker bila monitor).
    mode 'speaker': putar ke speaker laptop saja."""

    def __init__(self, mode: str = "virtual", monitor: bool = False) -> None:
        self.mode, self.monitor = mode, monitor
        self.procs: list[subprocess.Popen] = []
        self.modules: list[str] = []
        self.name = "Mikrofon HP (LinkDeck)" if mode == "virtual" else "speaker laptop"

    @staticmethod
    def available() -> bool:
        return bool(shutil.which("pactl") and shutil.which("pacat"))

    @staticmethod
    def _pactl(*args: str) -> str:
        r = subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=10)
        if r.returncode:
            raise OSError((r.stderr or r.stdout).strip() or f"pactl {args[0]} gagal")
        return r.stdout

    def ensure_device(self) -> None:
        if not re.search(rf"^\S+\t{PULSE_SINK}\t", self._pactl("list", "short", "sinks"), re.M):
            self.modules.append(self._pactl(
                "load-module", "module-null-sink", f"sink_name={PULSE_SINK}",
                "sink_properties=\"device.description='LinkDeck (saluran mikrofon HP)'\"").strip())
        if not re.search(rf"^\S+\t{PULSE_SOURCE}\t", self._pactl("list", "short", "sources"), re.M):
            self.modules.append(self._pactl(
                "load-module", "module-remap-source", f"master={PULSE_SINK}.monitor", f"source_name={PULSE_SOURCE}",
                "source_properties=\"device.description='Mikrofon HP (LinkDeck)'\"").strip())

    def start(self) -> None:
        if not self.available():
            raise ValueError(GUIDE["linux"])
        targets: list[str | None] = [None]
        if self.mode == "virtual":
            try:
                self.ensure_device()
            except OSError as e:
                raise ValueError(f"Mikrofon virtual tidak bisa dibuat (PulseAudio/PipeWire berjalan?): {e}")
            targets = [PULSE_SINK] + ([None] if self.monitor else [])
        for dev in targets:
            cmd = ["pacat", "--playback", "--format=s16le", f"--rate={RATE}", f"--channels={CHANNELS}",
                   "--latency-msec=40", "--client-name=LinkDeck", "--stream-name=Mikrofon HP"]
            if dev:
                cmd.append(f"--device={dev}")
            self.procs.append(subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL))

    def write(self, pcm: bytes) -> None:
        for p in self.procs:
            try:
                p.stdin.write(pcm)
                p.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass

    def stop(self) -> None:
        for p in self.procs:
            try:
                p.stdin.close()
            except Exception:
                pass
            p.terminate()
        self.procs.clear()
        for m in reversed(self.modules):                # hanya modul yang dibuat sesi ini
            try:
                self._pactl("unload-module", m)
            except OSError:
                pass
        self.modules.clear()


class DeviceOut:
    """Windows/macOS: putar ke perangkat keluaran (kabel virtual atau speaker) lewat sounddevice/PortAudio."""

    def __init__(self, device, name: str) -> None:
        self.device, self.name = device, name
        self.q: queue.Queue = queue.Queue(maxsize=50)
        self.stream = None
        self.thread = None
        self.channels = CHANNELS

    @staticmethod
    def find(target: str):
        """(indeks perangkat, nama). target: 'virtual' (kabel audio virtual) atau 'speaker' (keluaran bawaan)."""
        import sounddevice as sd
        if target == "speaker":
            idx = sd.default.device[1]
            info = sd.query_devices(idx if idx is not None and idx >= 0 else None, "output")
            return (None if idx is None or idx < 0 else idx), info["name"]
        apis = sd.query_hostapis()
        order = {"win32": ("MME", "Windows DirectSound", "Windows WASAPI"), "darwin": ("Core Audio",)}.get(sys.platform, ())
        rank = {name: i for i, name in enumerate(order)}
        found = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] < 1:
                continue
            if any(p.lower() in d["name"].lower() for p in VIRTUAL_PATTERNS.get(sys.platform, ())):
                found.append((rank.get(apis[d["hostapi"]]["name"], 9), i, d["name"]))
        if not found:
            raise ValueError("Kabel audio virtual tidak ditemukan. " + GUIDE.get(plat(), ""))
        _, idx, name = sorted(found)[0]
        return idx, name

    def start(self) -> None:
        import sounddevice as sd
        info = sd.query_devices(self.device, "output")
        self.channels = min(CHANNELS, int(info["max_output_channels"])) or 1
        self.stream = sd.RawOutputStream(samplerate=RATE, channels=self.channels, dtype="int16",
                                         device=self.device, latency="low")
        self.stream.start()
        self.thread = threading.Thread(target=self._writer, name="linkdeck-mic", daemon=True)
        self.thread.start()

    def _writer(self) -> None:
        import numpy as np
        while True:
            pcm = self.q.get()
            if pcm is None:
                return
            if self.channels == 1:                      # perangkat mono: rata-rata kiri & kanan
                a = np.frombuffer(pcm, dtype="<i2").reshape(-1, 2).astype(np.int32)
                pcm = ((a[:, 0] + a[:, 1]) // 2).astype("<i2").tobytes()
            try:
                self.stream.write(pcm)
            except Exception as e:
                print("[mic] tulis audio:", e, flush=True)

    def write(self, pcm: bytes) -> None:
        try:
            self.q.put_nowait(pcm)
        except queue.Full:                              # tertinggal: buang yang lama agar jeda tidak menumpuk
            try:
                self.q.get_nowait()
                self.q.put_nowait(pcm)
            except queue.Empty:
                pass

    def stop(self) -> None:
        try:
            self.q.put_nowait(None)
        except queue.Full:
            pass
        if self.thread:
            self.thread.join(2)
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass


def make_outputs(target: str, monitor: bool) -> list:
    if plat() == "linux":
        return [PulseOut("speaker" if target == "speaker" else "virtual", monitor)]
    try:
        import sounddevice  # noqa: F401
    except Exception as e:
        raise ValueError(f"Komponen audio (sounddevice) tidak tersedia: {e}")
    idx, name = DeviceOut.find(target)
    outs = [DeviceOut(idx, name)]
    if monitor and target != "speaker":
        sidx, sname = DeviceOut.find("speaker")
        outs.append(DeviceOut(sidx, sname))
    return outs


# ================================================================ sesi mikrofon & webcam

class MicSession:
    def __init__(self, serial: str, opts: dict) -> None:
        self.serial, self.opts = serial, opts
        self.outs: list = []
        self.proc = self.port = self.w = None

    async def start(self) -> str:
        self.outs = await asyncio.to_thread(make_outputs, self.opts.get("target", "virtual"), bool(self.opts.get("monitor")))
        try:
            for o in self.outs:
                await asyncio.to_thread(o.start)
            source = "mic-voice-communication" if self.opts.get("clean", True) else "mic"
            self.proc, self.port, r, self.w = await open_server(self.serial, [
                "video=false", "audio=true", "audio_codec=raw", f"audio_source={source}"])
            await read_codec(r)
        except BaseException:
            await self.cleanup()
            raise
        asyncio.create_task(self.pump(r))
        return self.outs[0].name

    async def pump(self, r) -> None:
        try:
            async for kind, data in packets(r):
                if kind in ("frame", "key") and data:
                    for o in self.outs:
                        o.write(data)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        if self.w:
            self.w.close()
            self.w = None
        if self.proc and self.proc.returncode is None:
            self.proc.kill()
        if self.port:
            await core.run("adb", "-s", self.serial, "forward", "--remove", f"tcp:{self.port}", timeout=5)
            self.port = None
        for o in self.outs:
            await asyncio.to_thread(o.stop)
        self.outs = []


class CamSession:
    """Windows/macOS: kamera HP -> OBS Virtual Camera."""

    def __init__(self, serial: str, opts: dict) -> None:
        self.serial, self.opts = serial, opts
        self.proc = self.port = self.w = None
        self.q: queue.Queue = queue.Queue(maxsize=8)
        self.thread = None
        self.cam_name = "OBS Virtual Camera"
        self.size = (1280, 720)
        self.error: str | None = None
        self.ready = threading.Event()

    @staticmethod
    def check() -> None:
        try:
            import av  # noqa: F401
            import numpy  # noqa: F401
            import pyvirtualcam  # noqa: F401
        except Exception as e:
            raise ValueError(f"Komponen webcam tidak tersedia: {e}")

    async def start(self) -> str:
        await asyncio.to_thread(self.check)
        size = str(self.opts.get("camera_size") or "1280x720")
        if not re.match(r"^\d+x\d+$", size):
            size = "1280x720"
        self.size = tuple(int(x) for x in size.split("x"))
        args = ["video=true", "audio=false", "video_codec=h264", "video_source=camera",
                f"camera_facing={self.opts.get('facing', 'back')}", f"camera_size={size}",
                "max_fps=30", "video_bit_rate=6000000"]
        zoom = float(self.opts.get("zoom") or 1)
        if abs(zoom - 1) >= 0.01:
            args.append(f"camera_zoom={zoom:.2f}")
        if self.opts.get("torch") and self.opts.get("facing", "back") == "back":
            args.append("camera_torch=true")
        self.thread = threading.Thread(target=self._worker, name="linkdeck-webcam", daemon=True)
        self.thread.start()
        await asyncio.to_thread(self.ready.wait, 15)
        if self.error:
            await self.cleanup()
            raise ValueError(self.error)
        try:
            self.proc, self.port, r, self.w = await open_server(self.serial, args)
            await read_codec(r)
        except BaseException:
            await self.cleanup()
            raise
        asyncio.create_task(self.pump(r))
        return self.cam_name

    def _worker(self) -> None:
        """Thread: buka kamera virtual, dekode H.264, kirim frame."""
        try:
            import av
            import pyvirtualcam
            cam = pyvirtualcam.Camera(width=self.size[0], height=self.size[1], fps=30,
                                      fmt=pyvirtualcam.PixelFormat.RGB, print_fps=False)
        except Exception as e:
            self.error = ("Kamera virtual tidak bisa dibuka: " + str(e) + ". Pasang OBS Studio 30 atau lebih baru "
                          "(berisi OBS Virtual Camera), jalankan sekali, lalu tutup OBS dan coba lagi.")
            self.ready.set()
            return
        self.cam_name = getattr(cam, "device", None) or self.cam_name
        self.ready.set()
        codec = av.CodecContext.create("h264", "r")
        w, h = self.size
        try:
            while True:
                data = self.q.get()
                if data is None:
                    break
                try:
                    frames = codec.decode(av.Packet(data))
                except Exception:
                    continue                            # paket rusak/terpotong: tunggu frame kunci berikutnya
                for fr in frames:
                    if fr.width != w or fr.height != h:
                        fr = fr.reformat(width=w, height=h)
                    cam.send(fr.to_ndarray(format="rgb24"))
        finally:
            cam.close()

    async def pump(self, r) -> None:
        try:
            async for kind, data in packets(r):
                if kind == "size":
                    continue
                if kind == "config":
                    self.q.put(data)                    # SPS/PPS selalu masuk
                    continue
                try:
                    self.q.put_nowait(data)
                except queue.Full:                      # dekoder tertinggal: lewati sampai frame kunci
                    if kind == "key":
                        self.q.put(data)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        if self.w:
            self.w.close()
            self.w = None
        if self.proc and self.proc.returncode is None:
            self.proc.kill()
        if self.port:
            await core.run("adb", "-s", self.serial, "forward", "--remove", f"tcp:{self.port}", timeout=5)
            self.port = None
        if self.thread and self.thread.is_alive():
            self.q.put(None)
            await asyncio.to_thread(self.thread.join, 3)


async def start_media(kind: str, d: dict) -> tuple[str, list[str]]:
    """Mulai sesi mikrofon ('mic') atau webcam ('webcam'); didaftarkan di S.sessions. Mengembalikan (id, catatan)."""
    serial = d.get("serial", "")
    if not serial:
        raise ValueError("Pilih perangkat Android dulu.")
    mode = "mic" if kind == "mic" else "camera"
    if any(x["serial"] == serial and x["mode"] == mode for x in core.S.sessions.values()):
        raise ValueError("Mikrofon HP sudah aktif." if kind == "mic" else "Kamera untuk perangkat ini sudah berjalan.")
    sdk = await core.get_sdk(serial)
    if kind == "mic" and sdk and sdk < 30:
        raise ValueError("HP jadi mikrofon butuh Android 11 ke atas.")
    if kind == "webcam" and sdk and sdk < 31:
        raise ValueError("Kamera HP butuh Android 12 ke atas.")
    sess = MicSession(serial, d) if kind == "mic" else CamSession(serial, d)
    name = await sess.start()
    sid = secrets.token_hex(4)
    label = "Mikrofon HP" if kind == "mic" else "Webcam HP"
    core.S.sessions[sid] = {"serial": serial, "mode": mode, "label": label, "proc": sess.proc, "audio": False,
                            "media": sess, "req": {k: v for k, v in d.items() if not k.startswith("_")}}
    asyncio.create_task(core.watch_session(sid, sess.proc))
    await core.broadcast({"type": "sessions", "sessions": core.public_sessions()})
    if kind == "mic":
        app = {"linux": "\"Mikrofon HP (LinkDeck)\"", "win32": "\"CABLE Output\"", "darwin": "\"BlackHole 2ch\""}.get(plat(), name)
        note = (f"Mikrofon HP aktif, diputar ke {name}." if d.get("target") == "speaker"
                else f"Mikrofon HP aktif. Di Zoom/Meet/Discord pilih mikrofon {app}.")
    else:
        note = f"Webcam HP aktif. Di Zoom/Meet pilih kamera \"{name}\"."
    notes = [note]
    if next((x["transport"] for x in core.S.devices if x["serial"] == serial), "") == "bt":
        notes.append("Lewat Bluetooth suara/gambar bisa tersendat (jalurnya sempit). Pakai kabel atau Wi-Fi untuk meeting.")
    return sid, notes


# ================================================================ endpoint

async def h_mic_start(req):
    d = await req.json()
    try:
        sid, notes = await start_media("mic", d)
    except ValueError as e:
        return core.fail(str(e))
    return core.ok(id=sid, notes=notes)


async def h_mic_info(req):
    """Kemampuan sistem ini: apakah mikrofon virtual siap dan apa namanya."""
    p = plat()
    info = {"platform": p, "virtual": None, "ready": False, "guide": GUIDE.get(p, "")}
    if p == "linux":
        info["ready"] = PulseOut.available()
        info["virtual"] = "Mikrofon HP (LinkDeck)" if info["ready"] else None
    else:
        try:
            _, info["virtual"] = await asyncio.to_thread(DeviceOut.find, "virtual")
            info["ready"] = True
        except Exception as e:
            info["error"] = str(e)
    info["webcam"] = p != "linux"
    if info["webcam"]:
        try:
            await asyncio.to_thread(CamSession.check)
            info["webcam_ready"] = True
        except ValueError as e:
            info["webcam_ready"], info["webcam_error"] = False, str(e)
    return core.ok(**info)


def register(router, core_module, app) -> None:
    global core
    core = core_module
    router.add_post("/api/mic/start", h_mic_start)
    router.add_post("/api/mic/info", h_mic_info)
