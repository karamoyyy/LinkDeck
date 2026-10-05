# LinkDeck

Aplikasi desktop untuk menyambungkan HP ke laptop, monitor, atau TV tanpa mengganggu layar yang sedang terbuka di masing-masing perangkat.

**Android** (lewat scrcpy 4)
- Layar virtual baru di PC; layar HP tetap seperti semula. Ukuran jendela bisa diubah bebas.
- Aplikasi HP di jendela sendiri (WhatsApp, Chrome, dll. masing-masing satu jendela).
- Cermin layar, HP jadi kamera/webcam (senter, zoom, webcam virtual di Linux), gamepad PC ke HP.
- Notifikasi HP muncul di PC; klik untuk membuka aplikasinya.

**Debian 13 XFCE di HP**
- Desktop XFCE tampil di jendela LinkDeck, atau sesi yang sedang terbuka dibagikan.
- Terminal Debian langsung di LinkDeck dan suara desktop Debian ikut ke PC.
- Satu mouse & keyboard: geser kursor ke tepi layar PC untuk mengontrol Debian (eksperimental).
- Folder sinkron dua arah `~/LinkDeck-Sinkron`.

**Bersama**
- Sambung otomatis: HP terdeteksi sendiri lewat Wi-Fi, kabel, atau tethering Bluetooth; PIN cukup sekali.
- Semua jalur ke Debian terenkripsi TLS dengan sertifikat yang dikunci.
- Clipboard dua arah dengan riwayat, kirim berkas, buka tautan, tangkap layar, rekam MP4.
- Mode TV satu klik dan pantauan baterai, jeda, aliran data, serta beban CPU.

## Terbitkan ke GitHub (sekali saja)

Folder ini sudah berupa repo git lengkap: kode sudah di-commit dan tag versi terbaru sudah ada. Tinggal jalankan satu perintah:

- **Windows**: klik dua kali `terbitkan.bat`
- **Linux/macOS**: `bash terbitkan.sh`

Skrip akan membuka browser untuk login GitHub, membuat repo di akunmu (atau memperbarui repo yang sudah ada), mengunggah kode, lalu memicu pembuatan installer versi terbaru. Setelah 10–15 menit semua installer ada di halaman **Releases** repo-mu.

Butuh Git dan GitHub CLI. Di Windows skrip memasangnya otomatis lewat winget; di Linux `sudo apt install git gh`; di macOS `brew install gh`.

## Unduh dan pasang

Ambil berkas dari halaman **Releases** repo ini.

| Perangkat | Berkas | Cara pasang |
|---|---|---|
| Windows 10/11 | `LinkDeck-<versi>-windows-setup.exe` | Jalankan. Jika muncul SmartScreen: *More info → Run anyway* |
| macOS (Apple Silicon) | `LinkDeck-<versi>-macos-arm64.dmg` | Seret ke Applications. Saat pertama buka: klik kanan → *Open* |
| Linux (Debian 12+/Ubuntu 22.04+) | `linkdeck_<versi>_amd64.deb` | `sudo apt install ./linkdeck_<versi>_amd64.deb` |
| Linux lain | `LinkDeck-<versi>-x86_64.AppImage` | `chmod +x` lalu jalankan |
| **HP: Debian 13** | `linkdeck-agent_<versi>_all.deb` | `sudo apt install ./linkdeck-agent_<versi>_all.deb` |

adb, scrcpy, dan penampil desktop Debian sudah ada di dalam aplikasi, tidak perlu dipasang terpisah. Paket agen HP juga ikut di dalam aplikasi: setelah HP tersambung, klik *Agen belum terpasang di HP? Kirim paketnya lewat adb* di panel Debian.

Jika macOS menyebut aplikasi "rusak": `xattr -dr com.apple.quarantine /Applications/LinkDeck.app`.

## Pakai

1. **HP Android**: aktifkan *Opsi pengembang → Debugging USB* (kabel) atau *Debugging nirkabel* (Wi-Fi, pairing lewat tombol *Sambungkan perangkat*).
2. **Debian di HP**: jalankan `linkdeck-start`. Pertama kali, kamu akan ditanya resolusi dan sandi VNC, lalu muncul PIN dan sidik jari.
3. **Di LinkDeck**: HP muncul sendiri di panel Debian. Pilih, isi PIN dan sandi sekali, lalu *Hubungkan*. Berikutnya tersambung otomatis.
4. Cocokkan sidik jari yang tampil di LinkDeck dengan yang tampil di `linkdeck-start` saat pertama kali menyambung.

Perintah di Debian:

```bash
linkdeck-start                 # desktop baru seukuran monitor; layar HP tidak berubah
linkdeck-start baru 3840x2160  # untuk TV 4K
linkdeck-start bagikan         # bagikan sesi XFCE :0 yang sedang terbuka (mis. Termux:X11)
linkdeck-setup                 # ubah resolusi atau sandi
linkdeck-cert --baru           # ganti sertifikat (lupakan perangkat di LinkDeck setelahnya)
linkdeck-stop
```

**Bluetooth**:
1. Di HP nyalakan *Tethering Bluetooth*.
2. Di laptop Windows tekan `Win + R`, ketik `control printers`, klik kanan HP → *Connect using → Access point*.
3. Debian terdeteksi otomatis. Untuk Android: colok kabel sekali, buka *Sambungkan perangkat → Bluetooth*, klik **Siapkan Android lewat Bluetooth**, lalu cabut kabel.

Kecepatannya sekitar 1–2 Mbps: cocok untuk clipboard, terminal, berkas kecil, dan desktop ringan. Supaya lebih lancar, pilih resolusi **1280×720** di menu *Lainnya* pada panel Debian, dan gunakan wallpaper polos di XFCE.

**Suara Debian** memakai PulseAudio (`parec`). Kalau Debian-mu memakai PulseAudio milik Termux, pastikan `PULSE_SERVER` sudah diatur sebelum `linkdeck-start`.

**Satu mouse** di macOS butuh izin *Aksesibilitas* dan *Pemantauan Input* untuk LinkDeck. Di Linux butuh sesi X11 (Wayland belum didukung). Darurat: `Ctrl+Alt+Home` mengembalikan mouse ke PC.

**Webcam**: di Linux pasang `v4l2loopback` agar kamera HP muncul sebagai webcam di Zoom/Meet. Di Windows/macOS rekam jendela kamera dengan OBS Virtual Camera.

**Notifikasi** dibaca lewat adb tanpa aplikasi tambahan di HP. Membalas pesan dari PC belum didukung; klik notifikasi untuk membuka aplikasinya di jendela sendiri.

## Membangun installer lewat GitHub Actions (cara manual)

1. Buat repo baru di GitHub, lalu push isi folder ini:
   ```bash
   git init && git add . && git commit -m "LinkDeck 1.1.0"
   git branch -M main
   git remote add origin https://github.com/<akun>/linkdeck.git
   git push -u origin main
   ```
2. Buat rilis dengan tag versi:
   ```bash
   git tag v1.1.0 && git push origin v1.1.0
   ```
3. Tunggu sekitar 10–15 menit di tab **Actions**. Semua installer (Windows, macOS, Linux, dan paket agen HP) otomatis muncul di **Releases → v1.1.0**.

Tanpa tag, buka *Actions → Build LinkDeck → Run workflow*; hasilnya ada di bagian *Artifacts* tiap run.

Yang dikerjakan workflow (`.github/workflows/build.yml`): unduh scrcpy (termasuk adb) dan noVNC dengan cek SHA-256, bangun paket agen HP, bekukan aplikasi dengan PyInstaller, lalu kemas jadi `.exe` (Inno Setup), `.dmg`, `.deb`, `.AppImage`, dan `.tar.gz`. Versi scrcpy dikunci lewat `SCRCPY_VERSION` di workflow.

Mac Intel: tambahkan baris `- { os: macos-15-intel, target: macos-x86_64 }` di matrix bila runner tersebut tersedia di akunmu.

## Menjalankan dari kode (pengembangan)

```bash
./jalankan.sh            # Linux/macOS  (jalankan.bat di Windows)
python server.py         # hanya server, buka sendiri http://127.0.0.1:8740
```

Mode ini memakai adb dan scrcpy dari `vendor/` bila ada (jalankan `python build/fetch_deps.py <os>` sekali), atau dari PATH.

Bangun lokal tanpa Actions (di OS yang sama dengan target):

```bash
pip install -r requirements.txt -r build/requirements-build.txt
python build/fetch_deps.py linux          # windows | macos-arm64 | macos-x86_64
python build/build_agent_deb.py
pyinstaller build/linkdeck.spec --noconfirm
python build/package.py linux             # hasil di out/
```

## Struktur

```
app.py                 aplikasi desktop: server di latar + jendela (WebView2/WKWebView/Chrome)
server.py              backend: adb, scrcpy, penemuan, terowongan TLS, sinkron, notifikasi
kvm.py                 satu mouse & keyboard lintas PC dan Debian
notif.py               pembaca notifikasi Android dan daftar aplikasi
static/index.html      antarmuka
phone/agent.py         agen di Debian HP
phone/bin/             linkdeck-start, linkdeck-stop, linkdeck-setup, linkdeck-cert
build/                 skrip unduh dependensi, spec PyInstaller, pengemasan, ikon, installer Windows
.github/workflows/     build otomatis semua OS
```

## Catatan keamanan

Server PC hanya mendengarkan di `127.0.0.1` dan setiap permintaan butuh token sesi. Semua lalu lintas ke Debian (desktop, terminal, suara, clipboard, berkas) lewat TLS dengan sertifikat yang dikunci saat pertama tersambung, dilindungi PIN; server VNC di HP hanya mendengarkan di localhost. LinkDeck juga mendengarkan beacon UDP port 47823 di jaringan lokal untuk penemuan otomatis; Windows mungkin meminta izin firewall sekali.
