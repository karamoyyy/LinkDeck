# LinkDeck

**Sambungkan HP ke laptop, monitor, atau TV — tanpa mengganggu layar yang sedang terbuka di masing-masing perangkat.**

LinkDeck menampilkan **Android** dan **Linux Debian 13 XFCE** dari HP-mu di laptop. Bisa lewat **kabel**, **Wi-Fi**, atau **Bluetooth**.

| Android | Debian 13 XFCE di HP | Bersama |
|---|---|---|
| Layar virtual baru (layar HP tidak berubah) | Desktop XFCE di jendela LinkDeck | Copy-paste dua arah + riwayat |
| Cermin layar HP | Terminal Debian | Kirim berkas & buka tautan |
| Aplikasi HP di jendela sendiri | Suara Debian ke laptop | Folder sinkron otomatis |
| HP jadi kamera / webcam | Satu mouse untuk laptop & Debian | Sambung otomatis, terenkripsi |
| **Mode Game**: WASD, tombol, bidik mouse | | Android tanpa kabel (kode QR) |
| Notifikasi HP muncul di laptop | Pilih resolusi desktop | Mode TV satu klik |

---

## Daftar isi

1. [Yang dibutuhkan](#1-yang-dibutuhkan)
2. [Instalasi](#2-instalasi)
3. [Menyambungkan HP](#3-menyambungkan-hp) — [Kabel](#31-lewat-kabel-paling-mudah) · [Wi-Fi](#32-lewat-wi-fi) · [Bluetooth](#33-lewat-bluetooth)
4. [Cara memakai](#4-cara-memakai)
5. [Daftar perintah](#5-daftar-perintah)
6. [Pintasan keyboard](#6-pintasan-keyboard)
7. [Mengatasi masalah](#7-mengatasi-masalah)
8. [Untuk pengembang](#8-untuk-pengembang)
9. [Keamanan & lisensi](#9-keamanan--lisensi)

---

## 1. Yang dibutuhkan

| Perangkat | Syarat |
|---|---|
| **Laptop/PC** | Windows 10/11, macOS 11+ (Apple Silicon), atau Linux (Debian 12+/Ubuntu 22.04+) |
| **HP Android** | Android 10 ke atas. Mode kamera butuh Android 12+ |
| **Debian di HP** | Debian 13 XFCE (proot/chroot, mis. lewat Termux). Hanya perlu kalau mau menampilkan desktop Debian |
| **Kabel** | Kabel USB yang bisa transfer data (bukan kabel khusus cas) |

Tidak perlu memasang adb atau scrcpy sendiri — semuanya sudah ada di dalam LinkDeck.

---

## 2. Instalasi

Semua berkas instalasi ada di halaman **Releases** repo ini (kolom kanan halaman GitHub → *Releases* → versi terbaru).

### 2.1 Di laptop

**Windows**
1. Unduh `LinkDeck-<versi>-windows-setup.exe`.
2. Klik dua kali. Kalau muncul layar biru *"Windows protected your PC"*, klik **More info → Run anyway**.
3. Ikuti langkahnya sampai selesai, lalu buka **LinkDeck** dari menu Start.
4. Kalau Windows Firewall bertanya, centang **Private networks** lalu **Allow** (dipakai untuk menemukan HP otomatis).

> Tidak mau instal? Pakai `LinkDeck-<versi>-windows-portable.zip`: ekstrak, lalu jalankan `LinkDeck.exe`.

**macOS (Apple Silicon)**
1. Unduh `LinkDeck-<versi>-macos-arm64.dmg`, buka, lalu seret **LinkDeck** ke folder **Applications**.
2. Saat pertama kali membuka: klik kanan LinkDeck → **Open** → **Open**.
3. Kalau muncul pesan "rusak" (damaged), buka **Terminal** dan jalankan:
   ```bash
   xattr -dr com.apple.quarantine /Applications/LinkDeck.app
   ```

**Linux**
```bash
sudo apt install ./linkdeck_<versi>_amd64.deb      # Debian/Ubuntu
linkdeck                                           # menjalankan aplikasi
```
Atau pakai `LinkDeck-<versi>-x86_64.AppImage`:
```bash
chmod +x LinkDeck-*-x86_64.AppImage
./LinkDeck-*-x86_64.AppImage
```

### 2.2 Di HP Android (sekali saja)

1. Buka **Setelan → Tentang ponsel**, ketuk **Nomor versi / Build number** 7 kali sampai muncul *"Anda sekarang developer"*.
2. Buka **Setelan → Sistem → Opsi pengembang** (letaknya bisa berbeda per merek; cari "Opsi pengembang" di kolom pencarian Setelan).
3. Nyalakan **Debugging USB**.

### 2.3 Di Debian 13 HP (sekali saja)

Lewati bagian ini kalau kamu hanya ingin menampilkan Android.

1. Pindahkan berkas `linkdeck-agent_<versi>_all.deb` ke HP. Dua cara:
   - **Paling mudah:** colok HP ke laptop, buka LinkDeck, lalu klik tautan *"Agen belum terpasang di HP? Kirim paketnya lewat adb"* di panel Debian. Berkas akan masuk ke `Download/LinkDeck` di HP.
   - Atau unduh langsung dari halaman Releases lewat browser di HP.
2. Buka terminal Debian, lalu pasang:
   ```bash
   sudo apt install /sdcard/Download/LinkDeck/linkdeck-agent.deb
   ```
   Kalau di Debian kamu sudah login sebagai `root`, hapus kata `sudo`.
   Kalau `/sdcard` tidak ditemukan, jalankan `termux-setup-storage` di Termux dulu, atau sesuaikan dengan lokasi berkasnya.
3. Jalankan pertama kali:
   ```bash
   linkdeck-start
   ```
   Kamu akan ditanya dua hal:
   - **Resolusi desktop** — tekan Enter untuk `1920x1080`, atau ketik mis. `1280x720`.
   - **Sandi VNC** — buat sandi 6–8 karakter. Ingat sandi ini.
4. Setelah itu muncul informasi seperti ini — **catat PIN-nya**:
   ```
     Debian siap untuk LinkDeck (otomatis terlihat di PC pada jaringan yang sama)
     Mode        : baru (DISPLAY :1, 1920x1080)
     PIN agen    : 178778
     Sidik jari  : 3B:33:50:39:B9:55:75:30   (cocokkan dengan yang tampil di LinkDeck)
     IP Wi-Fi    : 192.168.1.57
   ```

---

## 3. Menyambungkan HP

**Android dan Debian disambungkan terpisah.** Android memakai *Debugging USB/nirkabel* (adb); Debian memakai *agen LinkDeck* (`linkdeck-start`). Keduanya bisa lewat jalur berbeda, misalnya Android lewat kabel dan Debian lewat Wi-Fi. Klik **Sambungkan perangkat** lalu pilih **Android** atau **Debian 13 XFCE** untuk panduan masing-masing.

| Jalur | Kecepatan | Cocok untuk |
|---|---|---|
| **Kabel** | Paling cepat, paling stabil | Semua fitur, video lancar, main game |
| **Wi-Fi** | Cepat (tergantung sinyal) | Pemakaian sehari-hari tanpa kabel |
| **Bluetooth** | Lambat (±1–2 Mbps) | Copy-paste, terminal, berkas kecil, desktop ringan |

> **Tips:** Wi-Fi 5 GHz jauh lebih lancar daripada 2.4 GHz. Kalau router-mu punya dua jaringan, pakai yang 5G.

### 3.1 Lewat kabel (paling mudah)

1. Colok HP ke laptop dengan kabel data.
2. Di HP muncul pertanyaan *"Izinkan debugging USB?"* → centang **Selalu izinkan** → **Izinkan**.
3. Buka LinkDeck. HP muncul di kartu **Android** dengan label **Kabel**.
4. Untuk Debian: jalankan `linkdeck-start` di Debian. Debian otomatis muncul di panel **Debian** → pilih → isi **PIN** dan **sandi VNC** → **Hubungkan**.

Selesai. Berikutnya cukup colok kabel dan jalankan `linkdeck-start` — LinkDeck menyambung sendiri.

### 3.2 Lewat Wi-Fi

**Syarat:** HP dan laptop tersambung ke **Wi-Fi yang sama** (bukan data seluler).

**Debian di HP**
1. Jalankan `linkdeck-start`. Pastikan `IP Wi-Fi` yang tampil diawali angka yang sama dengan IP laptop (mis. sama-sama `192.168.1.x`).
2. Di LinkDeck, Debian muncul otomatis di panel Debian → pilih → isi PIN dan sandi → **Hubungkan**.

**Android — tanpa kabel: pindai kode QR (Android 11+)**
1. Di HP: **Opsi pengembang → Debugging nirkabel** → nyalakan → **Sambungkan perangkat dengan kode QR**.
2. Di LinkDeck: **Sambungkan perangkat → Android → Wi-Fi → Tampilkan kode QR**.
3. Arahkan kamera HP ke kode QR. LinkDeck memasangkan dan menyambung sendiri.

**Android — cara cepat lain (pakai kabel sekali)**
1. Colok kabel, pastikan HP terlihat di LinkDeck.
2. Klik **Sambungkan perangkat → Wi-Fi → Siapkan Android lewat Wi-Fi**.
3. Tunggu tulisan *"Selesai"*, lalu cabut kabel. HP tetap tersambung.

Langkah ini perlu diulang hanya kalau HP di-restart.

**Android — tanpa kabel sama sekali (Android 11+)**
1. Di HP: **Opsi pengembang → Debugging nirkabel** → nyalakan.
2. Ketuk **Sambungkan perangkat dengan kode penyambungan**. HP menampilkan alamat (mis. `192.168.1.57:41235`) dan kode 6 angka.
3. Di LinkDeck: **Sambungkan perangkat → Wi-Fi** → isi *Alamat pairing* dan *Kode* → **Pasangkan**.
4. Kembali ke layar **Debugging nirkabel** di HP. Lihat alamat di bagian atas (port-nya berbeda, mis. `192.168.1.57:37199`).
5. Isi alamat itu di *Alamat debugging* → **Sambungkan**.

### 3.3 Lewat Bluetooth

**Langkah 1 — Hubungkan jaringan Bluetooth (setiap kali mau dipakai)**
1. Pasangkan HP dan laptop lewat Bluetooth seperti biasa (cukup sekali seumur hidup).
2. Di HP nyalakan **Tethering Bluetooth**:
   - Umumnya: **Setelan → Jaringan & internet → Hotspot & tethering → Tethering Bluetooth**
   - Samsung: **Setelan → Koneksi → Hotspot seluler dan Tethering → Tethering Bluetooth**
3. Di laptop, gabung ke jaringan HP:
   - **Windows:** tekan `Win + R`, ketik `control printers`, Enter → klik kanan ikon HP → **Connect using → Access point** → tunggu *"Connection successful"*.
   - **Linux:** buka **Blueman** (Bluetooth Manager) → klik kanan HP → **Network Access Point**.
   - **macOS:** buka **System Settings → Network**, pilih **Bluetooth PAN** (kalau belum ada: tombol **⋯ → Add Service → Bluetooth PAN**), pilih HP-mu, lalu **Connect**.
4. Cek berhasil atau tidak (Windows): buka Command Prompt, ketik `ipconfig`. Di bagian **Bluetooth Network Connection** harus ada **IPv4 Address** dan **Default Gateway**. Kalau masih *Media disconnected*, ulangi langkah 3.

**Langkah 2 — Debian**
1. Jalankan `linkdeck-start` di Debian.
2. Debian muncul otomatis di LinkDeck dengan label **Bluetooth** → pilih → **Hubungkan**.
3. Kalau tidak muncul: klik *Isi alamat manual* → pilih **Bluetooth** → isi IP = angka **Default Gateway** dari `ipconfig` (biasanya `192.168.44.1`).
4. Supaya lancar: buka menu **Lainnya** di panel Debian → **Resolusi** → pilih **1280×720**.

**Langkah 3 — Android**
1. Sambungkan Android sekali lewat **Wi-Fi (kode QR)** atau **kabel**, pastikan HP terlihat di LinkDeck.
2. Klik **Lanjut tanpa kabel** di kartu Android (atau **Sambungkan perangkat → Bluetooth → Siapkan Android lewat Bluetooth**).
3. Tunggu tulisan *"Selesai"*. Kabel/Wi-Fi boleh diputus; Android tetap tersambung lewat Bluetooth.

Langkah 3 perlu diulang hanya kalau HP di-restart.

---

## 4. Cara memakai

### Android

| Mode | Fungsi |
|---|---|
| **Layar baru** | Membuat layar Android **tambahan** di laptop. Layar HP tetap seperti semula — bisa dipakai bersamaan |
| **Cermin** | Menampilkan persis apa yang ada di layar HP |
| **Kamera** | Kamera HP tampil di laptop. Senter (kamera belakang), zoom sesuai rentang lensa, dan arah kamera bisa diubah saat kamera sedang tampil |

- **Mulai tampilkan** — membuka jendela Android sesuai mode.
- **Aplikasi HP di jendela sendiri** — ketik nama aplikasi (mis. *WhatsApp*) → **Buka**. Tiap aplikasi dapat jendela sendiri.
- **Tangkap layar** — tersimpan di folder `Downloads/LinkDeck` laptop.
- **Audio ke PC** — suara HP dipindah ke laptop dan HP jadi senyap (Android 13+), supaya suara tidak bertabrakan. Ingin tetap terdengar di HP juga? Nyalakan **Suara juga di HP** di *Pengaturan lain*.
- **Pengaturan lain** — rekam ke MP4, gamepad, suara juga di HP, dan pilih monitor/TV tujuan.
- Kualitas video otomatis menyesuaikan jalur (Kabel/Wi-Fi/Bluetooth); bisa diganti manual lewat tombol di bagian *Kualitas video*.

### Mode Game

1. Di kartu Android pilih **Game**, ketik nama game (mis. *Mobile Legends*), klik **Main**.
2. Layar game terbuka penuh seukuran laptop. Gerakkan mouse ke **atas layar** untuk menu.
3. Klik **Edit tombol** → **Template dasar** (atau tambah sendiri) → seret tanda ke tombol di game → klik tanda lalu tekan tombol keyboard untuk mengganti → **Simpan**. Pengaturan disimpan per game.

| Jenis tanda | Cara kerja |
|---|---|
| **Joystick WASD** | W/A/S/D (atau panah) menggeser jari di lingkaran joystick. Ukurannya bisa diatur |
| **Tombol** | Tombol keyboard = ketukan di titik itu. Bisa juga **Klik kiri/kanan** (saat bidik aktif) |
| **Bidik mouse** | Tekan tombolnya (bawaan `` ` ``) untuk mengunci mouse: gerakan mouse = menggeser kamera/bidikan. Esc untuk melepas |

Tombol yang tidak dipetakan dikirim sebagai ketikan (untuk chat). `Esc` = tombol Kembali Android. Mode Game butuh WebView2 (Windows), Chrome/Edge, atau macOS 13+.

### Debian

- **Desktop / Terminal** — pilih tampilan desktop XFCE atau terminal.
- **Suara** — suara dari Debian diputar di laptop.
- **Satu mouse** — gerakkan kursor melewati tepi kanan layar laptop, kursor pindah ke Debian. Kembali dengan menggerakkan kursor ke tepi kiri Debian, atau tekan `Ctrl + Alt + Home`.
- **Layar penuh** — tampilkan Debian penuh di layar ini atau di monitor/TV yang dipilih di menu **Lainnya**.
- **Lainnya** — ganti resolusi desktop, pilih monitor tujuan, posisi Debian untuk "Satu mouse".

### Fitur bersama

- **Copy-paste** — salin di mana saja (laptop, HP Android, atau Debian), lalu tempel di perangkat lain. Berjalan otomatis selama HP tersambung, **tanpa perlu membuka jendela Android**. Kartu *Clipboard bersama* menampilkan riwayat, asal setiap salinan, dan status tiap perangkat; sakelar **Android** di kartu itu menyalakan/mematikan pemantauan clipboard HP.
- **Kirim berkas** — seret berkas ke kotak biru. Pilih tujuan *Ke Android* (masuk `Download/LinkDeck`) atau *Ke Debian* (masuk `~/Downloads/LinkDeck`).
- **Dari Debian ke laptop** — taruh berkas di folder `~/LinkDeck-Kirim` di Debian; otomatis masuk ke `Downloads/LinkDeck` di laptop.
- **Folder sinkron** — isi folder `LinkDeck-Sinkron` di laptop dan di Debian selalu disamakan otomatis (tambah, ubah, hapus).
- **Notifikasi HP** — notifikasi Android muncul di kartu *Notifikasi HP*. Klik untuk membuka aplikasinya di jendela sendiri.
- **Mode TV** — colok TV ke laptop (HDMI), klik **Mode TV**, pilih isi (Android/Debian/aplikasi) dan layar TV, lalu **Mulai**.

### Lokasi berkas

| Isi | Laptop | Debian |
|---|---|---|
| Berkas masuk | `Downloads/LinkDeck` | `~/Downloads/LinkDeck` |
| Folder sinkron | `LinkDeck-Sinkron` (di folder pengguna) | `~/LinkDeck-Sinkron` |
| Kirim ke laptop | — | `~/LinkDeck-Kirim` |
| Rekaman & tangkapan layar | `Downloads/LinkDeck` | — |
| Pengaturan & log | Windows: `%LOCALAPPDATA%\LinkDeck` · macOS: `~/Library/Application Support/LinkDeck` · Linux: `~/.local/share/LinkDeck` | `~/.linkdeck` |

---

## 5. Daftar perintah

### Di terminal Debian (HP)

| Perintah | Fungsi |
|---|---|
| `linkdeck-start` | Menyalakan LinkDeck di Debian: desktop XFCE **baru** seukuran monitor (layar HP tidak berubah) |
| `linkdeck-start baru 1280x720` | Sama, dengan resolusi tertentu (mis. untuk Bluetooth) |
| `linkdeck-start baru 3840x2160` | Resolusi 4K untuk TV |
| `linkdeck-start bagikan` | Membagikan sesi XFCE yang **sedang terbuka** di HP (mis. Termux:X11, display `:0`) |
| `LINKDECK_SHARE_DISPLAY=:2 linkdeck-start bagikan` | Membagikan sesi di display lain |
| `linkdeck-stop` | Mematikan semua bagian LinkDeck di Debian |
| `linkdeck-setup` | Mengganti resolusi bawaan dan sandi VNC (PIN tetap) |
| `linkdeck-cert` | Menampilkan sidik jari sertifikat |
| `linkdeck-cert --baru` | Membuat sertifikat baru (setelahnya, di LinkDeck: **Pengaturan → Lupakan** perangkat lalu sambungkan ulang) |
| `cat ~/.linkdeck/config` | Melihat PIN yang tersimpan |
| `tail -f ~/.linkdeck/agent.log` | Melihat log agen (tekan `Ctrl + C` untuk keluar) |
| `tail -n 30 ~/.linkdeck/vnc.log` | Melihat log desktop/VNC |
| `pgrep -af "agent.py\|Xtigervnc"` | Mengecek apakah LinkDeck sedang berjalan |
| `sudo apt install ./linkdeck-agent_<versi>_all.deb` | Memasang atau memperbarui agen |
| `sudo apt remove linkdeck-agent` | Menghapus agen |
| `rm -rf ~/.linkdeck` | Menghapus semua pengaturan agen (PIN, sandi, sertifikat) |

**Suara Debian (PulseAudio milik Termux).** Kalau tombol *Suara* memberi pesan error, jalankan ini di **Termux** (bukan di Debian) sebelum masuk ke Debian:
```bash
pulseaudio --start --load="module-native-protocol-tcp auth-ip-acl=127.0.0.1 auth-anonymous=1" --exit-idle-time=-1
```
Lalu di Debian, sebelum `linkdeck-start`:
```bash
export PULSE_SERVER=127.0.0.1
sudo apt install pulseaudio-utils
```

### Di laptop Windows (Command Prompt)

| Perintah | Fungsi |
|---|---|
| `ipconfig` | Melihat IP laptop dan IP HP (Bluetooth: lihat *Default Gateway*) |
| `control printers` (lewat `Win + R`) | Membuka *Devices and Printers* untuk menyambung jaringan Bluetooth HP |
| `ping 192.168.44.1` | Mengecek apakah HP bisa dijangkau (ganti dengan IP HP-mu) |
| `"%LOCALAPPDATA%\LinkDeck\linkdeck.log"` | Membuka log LinkDeck |

### Di laptop Linux

| Perintah | Fungsi |
|---|---|
| `linkdeck` | Menjalankan LinkDeck |
| `sudo apt install xclip` | Wajib untuk copy-paste (atau `wl-clipboard` di Wayland) |
| `sudo apt install v4l2loopback-dkms` | Supaya kamera HP bisa jadi webcam di Zoom/Meet |
| `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Kamera HP"` | Menyalakan webcam virtual (ulangi setiap restart) |
| `ip addr` | Melihat IP laptop |
| `sudo apt remove linkdeck` | Menghapus LinkDeck |

### Pilihan lanjutan (variabel lingkungan)

| Variabel | Fungsi | Bawaan |
|---|---|---|
| `LINKDECK_UI` | Jenis jendela: `webview`, `chromium`, atau `browser` | otomatis |
| `LINKDECK_PORT` | Port antarmuka lokal | `8740` |
| `LINKDECK_SAVE_DIR` | Folder berkas masuk | `Downloads/LinkDeck` |
| `LINKDECK_SYNC_DIR` | Folder sinkron di laptop | `~/LinkDeck-Sinkron` |

---

## 6. Pintasan keyboard

Di jendela **Android** (`Alt` = Alt kiri; bisa juga tombol Windows/⌘):

| Pintasan | Fungsi |
|---|---|
| `Ctrl + C` / `Ctrl + V` | Copy-paste antara laptop dan HP |
| `Alt + F` atau `F11` | Layar penuh |
| `Alt + H` | Tombol Home |
| `Alt + B` atau `Alt + Backspace` | Tombol Kembali |
| `Alt + S` | Daftar aplikasi terbuka |
| `Alt + N` | Buka panel notifikasi |
| `Alt + ↑` / `Alt + ↓` | Volume naik / turun (mode Kamera: zoom) |
| `Alt + P` | Tombol power |
| `Alt + O` | Matikan layar HP, tampilan di laptop tetap jalan |
| `Alt + R` | Putar layar |
| `Alt + Q` | Tutup jendela |
| Seret berkas ke jendela | APK langsung terpasang; berkas lain masuk `Download` |

Lainnya:

| Pintasan | Fungsi |
|---|---|
| `Ctrl + Alt + Home` | Mengambil kembali mouse dari Debian ("Satu mouse") |
| Mode Game: `Esc` | Tombol Kembali Android (atau melepas bidik mouse) |
| Mode Game: `` ` `` | Mengunci/melepas mouse untuk bidik (bisa diganti) |
| `Esc` | Keluar dari layar penuh Debian / menutup panel |

---

## 7. Mengatasi masalah

| Masalah | Solusi |
|---|---|
| HP tidak muncul saat dicolok | Ketuk **Izinkan** di HP. Coba kabel lain (banyak kabel hanya untuk mengecas). Matikan-nyalakan **Debugging USB** |
| HP muncul tapi tertulis *unauthorized* | Cabut-colok kabel, lalu ketuk **Izinkan** di layar HP |
| Debian tidak muncul di LinkDeck | Pastikan `linkdeck-start` sudah dijalankan. Cek HP dan laptop di Wi-Fi yang sama, atau isi IP manual |
| `IP Wi-Fi` di `linkdeck-start` diawali `10.` atau `100.` | HP sedang memakai data seluler. Sambungkan HP ke Wi-Fi yang sama dengan laptop |
| *"Agen Debian tidak menjawab"* | Jalankan `linkdeck-stop` lalu `linkdeck-start`. Lihat log: `tail -n 30 ~/.linkdeck/agent.log` |
| *"PIN agen salah"* | Lihat PIN dengan `cat ~/.linkdeck/config` |
| *"Sandi VNC salah"* | Buat sandi baru dengan `linkdeck-setup`, lalu sambungkan ulang |
| *"Sidik jari sertifikat berubah"* | Kalau kamu baru menjalankan `linkdeck-cert --baru`: **Pengaturan → Lupakan** perangkat, lalu sambungkan ulang. Kalau tidak, jangan lanjutkan — bisa ada yang menyamar di jaringan |
| Bluetooth: *Media disconnected* di `ipconfig` | Tethering Bluetooth belum menyala, atau langkah **Connect using → Access point** belum dilakukan |
| Bluetooth terasa lambat | Normal (±1–2 Mbps). Pakai resolusi 1280×720, matikan *Suara*, pakai wallpaper polos di XFCE |
| Gambar patah-patah lewat Wi-Fi | Pakai Wi-Fi 5 GHz, dekatkan ke router, atau pilih kualitas **Bluetooth** untuk sementara |
| Mode Game layar hitam | Pastikan membuka LinkDeck dari aplikasinya (Windows: WebView2) atau Chrome/Edge — browser lain mungkin tidak bisa memutar video H.264. Keluar lalu klik **Main** lagi |
| Kode QR tidak terdeteksi | HP dan laptop harus di Wi-Fi yang sama; sebagian router memblokir pencarian perangkat (AP isolation). Pakai **kode 6 angka** atau kabel |
| Ada bilah hitam di kiri-kanan jendela Android | Pilih resolusi **Layar ini** di kartu Android. Mode **Cermin** selalu mengikuti bentuk layar HP |
| Layar hitam di desktop Debian | Jalankan `linkdeck-stop`, lalu `linkdeck-start` lagi. Cek `tail -n 30 ~/.linkdeck/xfce.log` |
| Suara Debian tidak keluar | Lihat bagian *Suara Debian* di [Daftar perintah](#di-terminal-debian-hp) |
| Copy-paste tidak jalan (laptop Linux) | `sudo apt install xclip` |
| Salinan tidak muncul di kartu Clipboard | Klik tombol **Uji** di kartu Clipboard. Hasilnya menunjukkan bagian mana yang bermasalah (PC, HP, atau Debian), dan pesan galatnya tampil di bawah daftar perangkat. Pastikan sakelar **Android** menyala dan nama HP bertitik hijau. Yang disalin harus berupa teks (bukan gambar/berkas) |
| Senter tidak menyala | Senter hanya ada di kamera **belakang**. Kalau kamera sedang tampil, perubahan senter/zoom diterapkan dalam ±1 detik |
| Suara keluar dari HP dan laptop sekaligus | Pastikan **Suara juga di HP** (Pengaturan lain) mati. HP dengan Android 11–12 mengikuti pengaturan pabrikan; Android 13+ dijamin senyap |
| Mode kamera gagal | Butuh Android 12+. Tutup aplikasi lain yang sedang memakai kamera |
| "Satu mouse" tidak jalan di macOS | Buka **System Settings → Privacy & Security** → izinkan LinkDeck di **Accessibility** dan **Input Monitoring** |
| "Satu mouse" tidak jalan di Linux | Butuh sesi **X11**; Wayland belum didukung. Pilih "Xorg" di layar login |
| Windows: SmartScreen menghalangi | **More info → Run anyway** (aplikasi belum ditandatangani sertifikat berbayar) |

Masih bermasalah? Buka **Issues** di repo ini dan lampirkan isi log LinkDeck (lihat tabel lokasi berkas) serta `~/.linkdeck/agent.log`.

---

## 8. Untuk pengembang

### Menerbitkan ke GitHub
Folder ini sudah berupa repo git lengkap. Jalankan satu perintah:
- **Windows:** klik dua kali `terbitkan.bat`
- **Linux/macOS:** `bash terbitkan.sh`

Skrip akan membuka browser untuk login GitHub, membuat (atau memperbarui) repo, mengunggah kode, lalu memicu pembuatan installer. Butuh Git dan GitHub CLI (`winget install GitHub.cli`, `sudo apt install git gh`, atau `brew install gh`).

### Membuat installer lewat GitHub Actions
```bash
git tag v1.2.0
git push origin v1.2.0
```
Tunggu 10–15 menit di tab **Actions**. Semua installer (Windows, macOS, Linux, dan paket agen HP) otomatis muncul di **Releases**. Tanpa tag: **Actions → Build LinkDeck → Run workflow** (hasil di *Artifacts*).

> Kalau mengunggah lewat browser, folder tersembunyi `.github` tidak ikut. Buat `.github/workflows/build.yml` lewat **Add file → Create new file**.

### Menjalankan dari kode
```bash
pip install -r requirements.txt
python build/fetch_deps.py windows    # atau linux | macos-arm64 | macos-x86_64 (unduh adb, scrcpy, noVNC, xterm.js)
python app.py                         # aplikasi desktop
python server.py                      # server saja, buka http://127.0.0.1:8740
```

### Membuat installer di komputer sendiri
```bash
pip install -r requirements.txt -r build/requirements-build.txt
python build/fetch_deps.py linux
python build/build_agent_deb.py
pyinstaller build/linkdeck.spec --noconfirm
python build/package.py linux         # hasil di folder out/
```

### Struktur proyek
```
app.py                 aplikasi desktop: server di latar + jendela (WebView2 / WKWebView / Chrome)
server.py              backend: adb, scrcpy, penemuan otomatis, terowongan TLS, sinkron, notifikasi
kvm.py                 "Satu mouse" lintas laptop dan Debian
notif.py               pembaca notifikasi Android dan daftar aplikasi
static/index.html      antarmuka
phone/agent.py         agen di Debian HP
phone/bin/             linkdeck-start, linkdeck-stop, linkdeck-setup, linkdeck-cert
build/                 unduh dependensi, spec PyInstaller, pengemasan, ikon, installer Windows
.github/workflows/     build otomatis semua OS
```

### Port yang dipakai
| Port | Di mana | Fungsi |
|---|---|---|
| `8740` TCP | Laptop (hanya lokal) | Antarmuka LinkDeck |
| `47823` UDP | Laptop | Menerima sinyal penemuan otomatis dari HP |
| `8765` TCP (TLS) | HP | Agen Debian: desktop, terminal, suara, clipboard, berkas |
| `5901` TCP | HP (hanya lokal) | Server VNC desktop Debian |
| `5555` TCP | HP | adb lewat jaringan (setelah tombol "Siapkan lewat Wi-Fi/Bluetooth") |

---

## 9. Keamanan & lisensi

- Antarmuka LinkDeck hanya bisa diakses dari laptop itu sendiri dan dilindungi token sesi.
- Semua lalu lintas ke Debian (desktop, terminal, suara, clipboard, berkas) **terenkripsi TLS**. Sertifikat HP dikunci saat pertama tersambung; kalau berubah, LinkDeck menolak menyambung.
- Agen Debian dilindungi **PIN**; desktop dilindungi **sandi VNC**. Server VNC di HP hanya bisa diakses dari HP itu sendiri.
- adb lewat jaringan (port 5555) tidak terenkripsi dan aktif sampai HP di-restart. Pakai hanya di jaringan yang kamu percayai.

LinkDeck memakai komponen pihak ketiga:
[scrcpy](https://github.com/Genymobile/scrcpy) (Apache 2.0),
[Android platform-tools / adb](https://developer.android.com/tools/releases/platform-tools),
[noVNC](https://github.com/novnc/noVNC) (MPL 2.0),
[xterm.js](https://github.com/xtermjs/xterm.js) (MIT),
[TigerVNC](https://tigervnc.org/) (GPL, di HP),
[aiohttp](https://github.com/aio-libs/aiohttp), [pywebview](https://github.com/r0x0r/pywebview), [pynput](https://github.com/moses-palmer/pynput), [pyperclip](https://github.com/asweigart/pyperclip).

Riwayat perubahan ada di [CHANGELOG.md](CHANGELOG.md).
