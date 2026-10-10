# LinkDeck

**Tampilkan dan kendalikan HP Android di laptop, monitor, atau TV — lewat kabel, Wi-Fi, atau Bluetooth — tanpa mengganggu layar yang sedang terbuka di HP.**

LinkDeck adalah aplikasi desktop (Windows, macOS, Linux) untuk:

- **Layar baru** — membuat layar Android tambahan di laptop; layar HP tetap bisa dipakai seperti biasa.
- **Cermin** — menampilkan persis apa yang ada di layar HP.
- **Kamera** — kamera HP tampil di laptop (senter, zoom, belakang/depan).
- **Mode Game** — main game Android dengan keyboard & mouse atau **stik (gamepad)**: WASD, tombol, tombol geser untuk skill, bidik mouse dengan kurva akselerasi, template game populer, dan kode berbagi tombol — dalam layar penuh seukuran laptop.

**Unduh:** [halaman Releases](https://github.com/karamoyyy/LinkDeck/releases/latest) · **Panduan:** halaman ini.

> **English:** the LinkDeck app is available in English — choose it in the first-run guide or in **Settings → Appearance → Language**. This guide is written in Indonesian.

Ditambah fitur bersama: copy-paste dua arah (teks, serta gambar & berkas antara laptop dan Debian), kirim berkas, notifikasi HP di laptop (bisa **dibalas dari laptop** dengan aplikasi pendamping opsional), **HP jadi mikrofon** dan **webcam** untuk Zoom/Meet/Discord, status baterai & pengisian, dan Mode TV. LinkDeck bisa berjalan diam-diam di **tray** dan menyala sendiri saat komputer dinyalakan. Bila HP-mu juga menjalankan **Debian 13 XFCE** (mis. lewat Termux), LinkDeck bisa menampilkan desktop, terminal, dan suara Debian, serta **Alat Debian** (pengelola berkas, toko aplikasi, dan pemantau sistem) — ini opsional dan disambungkan terpisah dari Android.

---

## Daftar isi

1. [Yang dibutuhkan](#1-yang-dibutuhkan)
2. [Instalasi](#2-instalasi)
3. [Tutorial Android: Layar baru, Cermin, Kamera, dan Game](#3-tutorial-android-layar-baru-cermin-kamera-dan-game)
4. [Debian 13 XFCE di HP (opsional)](#4-debian-13-xfce-di-hp-opsional)
5. [Fitur bersama](#5-fitur-bersama)
6. [Daftar perintah](#6-daftar-perintah)
7. [Pintasan keyboard](#7-pintasan-keyboard)
8. [Mengatasi masalah](#8-mengatasi-masalah)
9. [Untuk pengembang](#9-untuk-pengembang)
10. [Keamanan dan komponen pihak ketiga](#10-keamanan-dan-komponen-pihak-ketiga)
11. [Aplikasi LinkDeck di Debian HP (arm64)](#11-aplikasi-linkdeck-di-debian-hp-arm64)

---

## 1. Yang dibutuhkan

| Perangkat / fitur | Syarat |
|---|---|
| Laptop/PC | Windows 10/11, macOS 11 ke atas (Apple Silicon), atau Linux (Debian 12+/Ubuntu 22.04+) |
| Cermin | Android 5.0 ke atas |
| Layar baru dan Mode Game | Disarankan Android 10 ke atas |
| Audio ke PC | Android 11 ke atas (HP otomatis senyap mulai Android 13) |
| Kamera | Android 12 ke atas |
| Sambung lewat Wi-Fi tanpa kabel (kode QR / kode 6 angka) | Android 11 ke atas |
| Mode Game | Windows: WebView2 (bawaan Windows 11 dan Windows 10 yang diperbarui) · Linux: Chrome, Chromium, atau Edge · macOS: Safari 16.4 ke atas (perbarui macOS/Safari) |
| Alat Debian, clipboard gambar & berkas | Agen Debian 1.10.0 atau lebih baru. Clipboard gambar & berkas di laptop: Windows atau Linux (macOS: teks saja) |
| HP jadi mikrofon laptop | Android 11 ke atas. Windows: [VB-CABLE](https://vb-audio.com/Cable/) (gratis) · macOS: [BlackHole 2ch](https://existential.audio/blackhole/) (gratis) · Linux: PulseAudio/PipeWire (`pactl`, sudah ada di kebanyakan desktop) |
| Kamera HP jadi webcam Zoom/Meet | Android 12 ke atas. Windows/macOS: [OBS Studio](https://obsproject.com/) 30 ke atas (berisi *OBS Virtual Camera*) · Linux: modul `v4l2loopback` |
| Balas notifikasi & status pengisian baterai | Aplikasi **LinkDeck Pendamping** (opsional, Android 6.0 ke atas), dipasang dari LinkDeck dengan satu klik |
| Ikon tray | Windows dan Linux (GNOME butuh ekstensi *AppIndicator*). macOS belum didukung: menutup jendela berarti keluar |
| Kabel | Kabel USB yang bisa transfer data, bukan kabel khusus cas |

adb dan scrcpy sudah ada di dalam LinkDeck — tidak perlu dipasang sendiri.

---

## 2. Instalasi

Semua berkas ada di halaman **Releases** repo ini (kolom kanan halaman GitHub → *Releases* → versi terbaru).

| Berkas | Untuk | Arsitektur |
|---|---|---|
| `LinkDeck-<versi>-windows-setup.exe` / `-windows-portable.zip` | Laptop/PC Windows | x64 |
| `LinkDeck-<versi>-macos-arm64.dmg` | Mac Apple Silicon | arm64 |
| `linkdeck_<versi>_amd64.deb` / `LinkDeck-<versi>-x86_64.AppImage` | Laptop/PC **Linux** | Intel/AMD (amd64) saja |
| `linkdeck-debian_<versi>_all.deb` | Aplikasi LinkDeck di **Debian HP** (atau Debian/Ubuntu ARM lain) | semua |
| `linkdeck-agent_<versi>_all.deb` | Agen di **Debian HP**, supaya Debian tampil di laptop | semua |
| `linkdeck-companion.apk` | Aplikasi pendamping **Android** (opsional). Biasanya tidak perlu diunduh: LinkDeck memasangnya sendiri | semua |

> `linkdeck_<versi>_amd64.deb` **tidak bisa** dipasang di Debian HP (galat `libc6:amd64 ... [no choices]`), karena HP memakai prosesor ARM. Untuk HP, pakai `linkdeck-debian_<versi>_all.deb`. Cek arsitektur dengan `dpkg --print-architecture`.

### 2.1 Di laptop

**Windows**
1. Unduh `LinkDeck-<versi>-windows-setup.exe`, lalu klik dua kali.
2. Kalau muncul layar biru *"Windows protected your PC"*: klik **More info → Run anyway**.
3. Ikuti langkahnya, lalu buka **LinkDeck** dari menu Start.
4. Kalau Windows Firewall bertanya, centang **Private networks** → **Allow** (dipakai untuk menemukan HP secara otomatis).

> Tidak mau instal? Pakai `LinkDeck-<versi>-windows-portable.zip`: ekstrak, lalu jalankan `LinkDeck.exe`.

**macOS (Apple Silicon)**
1. Unduh `LinkDeck-<versi>-macos-arm64.dmg`, buka, lalu seret **LinkDeck** ke **Applications**.
2. Saat pertama dibuka: klik kanan LinkDeck → **Open** → **Open**.
3. Kalau muncul pesan aplikasi "rusak" (*damaged*), buka **Terminal** lalu jalankan:
   ```bash
   xattr -dr com.apple.quarantine /Applications/LinkDeck.app
   ```

**Linux**
```bash
sudo apt install ./linkdeck_<versi>_amd64.deb      # Debian/Ubuntu
linkdeck                                           # menjalankan aplikasi
```
Atau pakai AppImage:
```bash
chmod +x LinkDeck-<versi>-x86_64.AppImage
./LinkDeck-<versi>-x86_64.AppImage
```

**Pertama kali dibuka**, **Panduan awal** muncul: pilih bahasa (Bahasa Indonesia / English) dan tema, pilih yang mau disambungkan (HP Android, Debian di HP, atau keduanya), lalu ikuti daftar periksa yang diperbarui sendiri (adb siap, HP terdeteksi, izin debugging, aplikasi pendamping). Bisa dilewati, dan dibuka lagi kapan saja dari **Pengaturan → Aplikasi → Panduan awal**.

**Memperbarui LinkDeck:** unduh versi terbaru dari Releases lalu pasang seperti biasa — pengaturan, perangkat yang diingat, dan tombol game tetap tersimpan.

**Menghapus LinkDeck:** Windows: **Setelan → Aplikasi → LinkDeck → Copot pemasangan**. macOS: seret **LinkDeck** dari Applications ke Tempat Sampah. Linux: `sudo apt remove linkdeck`.

### 2.2 Di HP Android (sekali saja)

1. **Aktifkan Opsi pengembang** — ketuk 7 kali sampai muncul *"Anda sekarang developer"*:

   | Merek | Yang diketuk 7 kali |
   |---|---|
   | Umumnya (Pixel, Motorola, dll.) | **Setelan → Tentang ponsel → Nomor versi** |
   | Samsung | **Setelan → Tentang ponsel → Informasi perangkat lunak → Nomor versi** |
   | Xiaomi / Redmi / POCO | **Setelan → Tentang ponsel → Versi OS** (atau **Versi MIUI**) |
   | Oppo / Realme / OnePlus | **Setelan → Tentang perangkat → Versi → Nomor versi** |
   | vivo / iQOO | **Setelan → Tentang ponsel → Versi perangkat lunak** |

2. Buka **Opsi pengembang** (biasanya di **Setelan → Sistem**, atau **Setelan tambahan** di Xiaomi/Oppo; bisa juga dicari lewat kolom pencarian Setelan).
3. Nyalakan **Debugging USB**. Untuk sambungan tanpa kabel, nanti juga dipakai **Debugging nirkabel**.
4. **Khusus Xiaomi / Redmi / POCO:** nyalakan juga **Debugging USB (Setelan keamanan)**, lalu **restart HP**. Tanpa ini, gambar tampil tetapi klik, ketik, dan Mode Game tidak berfungsi. Di beberapa HP Oppo/Realme, opsi serupa bernama **Nonaktifkan pemantauan izin**.

Fitur utama tidak butuh aplikasi tambahan di Android. Aplikasi **LinkDeck Pendamping** bersifat opsional (untuk membalas notifikasi dan status pengisian baterai) dan dipasang dari LinkDeck dengan satu klik — lihat [Notifikasi HP & LinkDeck Pendamping](#notifikasi-hp--linkdeck-pendamping).

### 2.3 Di Debian 13 HP (opsional)

Lewati bagian ini kalau kamu hanya memakai fitur Android. Langkahnya (termasuk cara memasang Debian 13 XFCE di HP bila belum punya) ada di [bagian 4](#4-debian-13-xfce-di-hp-opsional).

---

## 3. Tutorial Android: Layar baru, Cermin, Kamera, dan Game

Bagian ini **hanya untuk Android** — tidak memerlukan Debian sama sekali.

Semua fitur Android memakai *Debugging USB/nirkabel* (adb). Pilih salah satu jalur di bawah, lalu lanjut ke [3.5](#35-memakai-layar-baru).

| Jalur | Kecepatan | Cocok untuk |
|---|---|---|
| **Kabel** | Paling cepat dan stabil | Semua fitur, terutama Mode Game |
| **Wi-Fi** | Cepat (tergantung sinyal; 5 GHz lebih baik) | Pemakaian sehari-hari tanpa kabel |
| **Bluetooth** | Lambat (±1–2 Mbps) | Cermin/layar ringan, notifikasi, copy-paste |

### 3.1 Sambung lewat kabel

1. Colok HP ke laptop dengan kabel data.
2. Di HP muncul *"Izinkan debugging USB?"* → centang **Selalu izinkan dari komputer ini** → **Izinkan**.
3. Buka LinkDeck. Nama HP muncul di kartu **Android** dengan label **Kabel**.

### 3.2 Sambung lewat Wi-Fi

HP dan laptop harus tersambung ke **Wi-Fi yang sama** (bukan data seluler).

**Cara A — pindai kode QR, tanpa kabel (Android 11+)**
1. Di LinkDeck klik **Sambungkan perangkat** (pojok kanan atas) → **Android** → **Wi-Fi** → **Tampilkan kode QR**.
2. Di HP: **Opsi pengembang → Debugging nirkabel** → nyalakan → **Sambungkan perangkat dengan kode QR**.
3. Arahkan kamera HP ke kode QR di laptop. Tunggu tulisan *"Tersambung lewat Wi-Fi!"*.

**Cara B — kode 6 angka, tanpa kabel (Android 11+)**
1. Di HP: **Debugging nirkabel → Sambungkan perangkat dengan kode penyambungan**.
2. Di LinkDeck: **Sambungkan perangkat → Android → Wi-Fi → Atau pakai kode 6 angka**. Alamat HP muncul otomatis — klik alamatnya.
3. Isi **Kode** sesuai yang tampil di HP → **Pasangkan & sambungkan**.

**Cara C — dari kabel ke Wi-Fi**
1. Sambungkan dulu lewat kabel ([3.1](#31-sambung-lewat-kabel)).
2. Klik **Lanjut tanpa kabel** di kartu Android → **Siapkan Android lewat Wi-Fi**.
3. Setelah muncul *"Selesai"*, cabut kabel. Ulangi hanya kalau HP di-restart.

### 3.3 Sambung lewat Bluetooth

Android hanya mengizinkan adb lewat jaringan setelah diaktifkan **sekali** lewat kabel atau Wi-Fi (aturan keamanan Android). Setelah itu, semua fitur Android berjalan lewat Bluetooth sampai HP di-restart.

1. **Aktifkan sekali:** sambungkan Android lewat kabel ([3.1](#31-sambung-lewat-kabel)) atau Wi-Fi ([3.2](#32-sambung-lewat-wi-fi)).
2. **Pasangkan Bluetooth** HP dan laptop seperti biasa (cukup sekali).
3. **Nyalakan Tethering Bluetooth di HP:**
   - Umumnya: **Setelan → Jaringan & internet → Hotspot & tethering → Tethering Bluetooth**
   - Samsung: **Setelan → Koneksi → Hotspot seluler dan Tethering → Tethering Bluetooth**
4. **Gabungkan laptop ke jaringan Bluetooth HP:**
   - **Windows:** tekan `Win + R`, ketik `control printers`, Enter → klik kanan ikon HP → **Connect using → Access point** → tunggu *"Connection successful"*.
   - **Linux:** buka **Blueman** → klik kanan HP → **Network Access Point**.
   - **macOS:** **System Settings → Network** → pilih **Bluetooth PAN** (kalau belum ada: **⋯ → Add Service → Bluetooth PAN**) → pilih HP → **Connect**.
5. Di LinkDeck klik **Sambungkan perangkat → Android → Bluetooth → Siapkan Android lewat Bluetooth**.
6. Setelah muncul *"Selesai"*, kabel/Wi-Fi boleh diputus. HP tampil di kartu Android dengan label **Bluetooth**.

Selama HP belum di-restart, LinkDeck **menyambung ulang sendiri** lewat Bluetooth setiap kali jaringan Bluetooth HP tersambung lagi — tidak perlu mengulang langkah 5.

> Cek di Windows: buka Command Prompt, ketik `ipconfig`. Di bagian **Bluetooth Network Connection** harus ada **IPv4 Address** dan **Default Gateway**. Kalau masih *Media disconnected*, ulangi langkah 3–4.

### 3.4 Kualitas otomatis

Bagian **Kualitas video** di kartu Android memilih pengaturan sesuai jalur yang terdeteksi:

| Jalur | Video | Catatan |
|---|---|---|
| Kabel | 16 Mbps, 60 fps | Kualitas penuh |
| Wi-Fi | 6 Mbps, 60 fps, maks. 1600 px | Penyangga kecil meredam patah-patah |
| Bluetooth | 0,8 Mbps, 15 fps, maks. 720 px | Tanpa suara; untuk tampilan ringan |

Kamu bisa menggantinya manual dengan tombol **Kabel / Wi-Fi / Bluetooth** di bagian itu.

### 3.5 Memakai Layar baru

Membuat layar Android **tambahan** di laptop. Layar HP tidak berubah dan tetap bisa dipakai bersamaan.

1. Di kartu Android pilih **Layar baru**.
2. Pilih ukuran: **Layar ini** (bawaan, seukuran layar laptop — layar penuh tanpa bilah hitam), **720p**, **1080p**, atau **4K**.
3. Klik **Mulai tampilkan**. Jendela Android terbuka di laptop.

Membuka satu aplikasi di jendelanya sendiri: ketik namanya di **Aplikasi HP di jendela sendiri** (mis. *WhatsApp*) → **Buka**.

Pilihan lain:
- **Audio ke PC** — suara HP pindah ke laptop (HP jadi senyap mulai Android 13). Di Android 11, buka kunci layar HP sebelum klik **Mulai tampilkan**.
- **HP tetap aktif** — layar HP tidak mati sendiri selama dipakai.
- **Ukuran bebas** — ukuran layar Android mengikuti ukuran jendela (tidak tersedia lewat Bluetooth).
- **Pengaturan lain** — **Rekam ke MP4**, **Suara juga di HP**, **Gamepad PC ke HP**, dan **Tampilkan di** (pilih monitor/TV).

### 3.6 Memakai Cermin

1. Pilih **Cermin** → **Mulai tampilkan**.
2. Laptop menampilkan persis isi layar HP. Klik dan ketik di jendela itu untuk mengendalikan HP.
3. **Matikan layar HP** mematikan layar fisik HP sementara tampilan di laptop tetap berjalan.

Bentuk jendela Cermin mengikuti bentuk layar HP, jadi bilah hitam di sisi kiri-kanan saat layar penuh itu normal. Untuk layar penuh tanpa bilah hitam, pakai **Layar baru** dengan ukuran **Layar ini**.

### 3.7 Memakai Kamera

1. Pilih **Kamera**, lalu **Belakang** atau **Depan** dan ukuran **720p/1080p**.
2. Klik **Mulai tampilkan**.
3. **Senter** (kamera belakang saja) dan **Zoom** (geser, atau tombol **−**, **1×**, **+**) bisa diubah saat kamera sedang tampil; kamera dibuka ulang ±1 detik untuk menerapkannya. Rentang zoom mengikuti lensa HP-mu.

**Kamera HP jadi webcam** untuk Zoom, Google Meet, Teams, Discord, atau OBS:
- **Windows / macOS:** pasang [OBS Studio](https://obsproject.com/) 30 ke atas, jalankan sekali lalu tutup. Di LinkDeck pilih **Kamera** → centang **Jadikan webcam untuk Zoom/Meet (lewat OBS Virtual Camera, tanpa jendela)** → **Mulai tampilkan**. Di aplikasi meeting pilih kamera **OBS Virtual Camera**. Tidak ada jendela yang terbuka; hentikan lewat daftar tampilan yang berjalan.
- **Linux:** centang **Jadikan webcam untuk aplikasi meeting** (butuh modul `v4l2loopback`, lihat [bagian 6](#di-laptop-linux)); di aplikasi meeting pilih kamera **Kamera HP**.

### 3.8 Memakai Mode Game

1. Pilih **Game**, ketik nama game (mis. *Mobile Legends*), lalu klik **Main**. Kosongkan nama untuk menampilkan layar HP apa adanya.
2. Game terbuka layar penuh seukuran laptop. Gerakkan mouse ke **bagian atas layar** untuk memunculkan menu.
3. **Atur tombol:** klik **Edit tombol** → pilih **Template** lalu **Pakai** (atau tambah tanda sendiri) → seret tiap tanda ke tombol di layar game → klik sebuah tanda lalu tekan tombol keyboard **atau tombol stik** penggantinya → **Simpan**. Pengaturan disimpan terpisah untuk setiap game.

| Jenis tanda | Cara kerja |
|---|---|
| **Joystick WASD** | W/A/S/D atau **stik kiri** gamepad menggeser jari di lingkaran joystick (bisa diganti **Pakai panah**). **Ukuran** lingkaran bisa diatur. Satu per game |
| **Tombol** | Tombol keyboard atau tombol stik = ketukan di titik itu. Bisa juga **Klik kiri** / **Klik kanan** (aktif saat bidik mouse menyala) |
| **Tombol geser** | Untuk skill berarah (MOBA). **Tahan** tombolnya → jari menempel di tombol skill; arahkan dengan **posisi mouse dari tengah layar** atau **stik kanan**; **lepas** untuk memakai skill. **Ukuran** = jangkauan geser (lingkaran titik-titik tampil saat mengedit/ditahan) |
| **Bidik mouse** | Tekan tombolnya (bawaan `` ` ``) untuk mengunci mouse: gerakan mouse menggeser kamera/bidikan. **Stik kanan** gamepad juga membidik tanpa mengunci mouse. Tekan lagi atau `Esc` untuk melepas. Satu per game |

**Kepekaan bidik** (klik tanda bidik saat mengedit):
- **Kepekaan** — kecepatan dasar.
- **Akselerasi** — 0 = linear; makin besar, gerakan mouse yang cepat menggeser makin jauh (memutar badan dengan cepat, membidik pelan tetap halus).
- **Saat membidik (tahan klik kanan)** — kepekaan terpisah selama klik kanan ditahan, misalnya saat memakai teropong (scope).

**Template** — **Dasar**, **MOBA** (mis. Mobile Legends), **Battle royale** (mis. PUBG Mobile, Free Fire), dan **Aksi / RPG** (mis. Genshin Impact). Posisi tanda di template adalah **perkiraan**, karena tata letak tiap game (dan pengaturan HUD di dalam game) berbeda — seret tanda agar pas, lalu **Simpan**.

**Berbagi tombol** — **Salin kode** menyalin semua tanda sebagai teks pendek yang diawali `LDK1.`; kirim ke teman. Teman membuka game yang sama → **Edit tombol** → **Tempel kode** → **Simpan**. Kode hanya berisi posisi dan tombol (tanpa data pribadi) dan diperiksa dulu sebelum dipakai.

**Gamepad (stik)** — colok atau pasangkan stik Xbox, PlayStation, atau stik lain yang dikenali Windows/macOS/Linux sebagai gamepad standar, lalu tekan salah satu tombolnya sekali. Stik kiri = joystick, stik kanan = bidik/arah tombol geser, tombol lain dipetakan lewat **Edit tombol** (klik tanda → tekan tombol stik). Tombol **Back/View** yang belum dipetakan = tombol **Kembali** Android.

**Info** (menu atas) — menampilkan FPS, waktu respons (ms), suhu baterai HP, persen baterai, dan 🎮 bila stik tersambung. Angka berwarna merah bila respons > 120 ms, suhu ≥ 42°C, atau baterai ≤ 15%.

- Klik mouse biasa = sentuhan satu jari. Roda mouse = gulir.
- Tombol yang tidak dipetakan dikirim sebagai ketikan (untuk chat).
- `Esc` = tombol **Kembali** Android. Untuk keluar dari layar penuh, **tahan** `Esc` (Windows, Chrome/Edge) atau klik **Layar penuh** di menu atas.
- **Tanda tombol** menyembunyikan/menampilkan tanda; **Info** menyembunyikan/menampilkan angka di atas; **Keluar** menutup Mode Game.

Suara game ikut keluar di laptop (Android 11 ke atas, kecuali lewat Bluetooth). Mode Game butuh WebView2 di Windows, Chrome/Chromium/Edge di Linux, atau Safari 16.4 ke atas di macOS.

---

## 4. Debian 13 XFCE di HP (opsional)

Untuk desktop XFCE, terminal, suara Debian, "Satu mouse", dan folder sinkron. Debian memakai **agen LinkDeck**, terpisah dari adb — jadi bisa tersambung walau Android tidak, dan sebaliknya.

### 4.0 Menyiapkan Debian 13 XFCE di HP (bila belum punya)

Lewati kalau Debian 13 XFCE sudah berjalan di HP-mu.

1. Pasang **Termux** dari [F-Droid](https://f-droid.org/packages/com.termux/) atau [GitHub Termux](https://github.com/termux/termux-app/releases) (disarankan; jangan campur dengan Termux dari sumber lain karena tanda tangannya berbeda). Opsional: **Termux:X11** dari [GitHub](https://github.com/termux/termux-x11/releases) untuk menampilkan XFCE di layar HP.
2. Di **Termux**:
   ```bash
   pkg update && pkg upgrade
   pkg install proot-distro
   termux-setup-storage                 # izinkan akses penyimpanan saat ditanya
   proot-distro install debian
   proot-distro login debian --shared-tmp
   ```
3. Di **Debian** (setelah login):
   ```bash
   apt update && apt install -y xfce4 xfce4-terminal dbus-x11
   cat /etc/debian_version              # harus 13.x
   ```
4. Untuk masuk lagi ke Debian kapan saja: buka Termux → `proot-distro login debian --shared-tmp` (sebagai root) atau `proot-distro login debian --user NAMAMU --shared-tmp` (sebagai pengguna biasa). Jalankan `linkdeck-start` sebagai pengguna yang biasa kamu pakai untuk XFCE.

> `--shared-tmp` membuat Debian dan Termux berbagi folder `/tmp`, sehingga XFCE di Termux:X11 dan clipboard-nya ikut terpantau LinkDeck.

### 4.1 Pasang agen (sekali)

1. Pindahkan `linkdeck-agent_<versi>_all.deb` (dari Releases) ke HP. Dua cara:
   - Kalau Android sudah tersambung ke LinkDeck: klik **Agen belum terpasang di HP? Kirim paketnya lewat adb** di panel Debian. Berkas masuk ke `/sdcard/Download/LinkDeck/linkdeck-agent.deb`.
   - Atau unduh dari halaman Releases lewat browser HP. Berkas biasanya masuk ke `/sdcard/Download/linkdeck-agent_<versi>_all.deb`.
2. Di terminal Debian, pasang sesuai lokasinya:
   ```bash
   sudo apt install /sdcard/Download/LinkDeck/linkdeck-agent.deb           # cara pertama
   sudo apt install /sdcard/Download/linkdeck-agent_<versi>_all.deb        # cara kedua
   ```
   Pemasangan paket butuh hak **root**:
   - Masuk sebagai **root** (`proot-distro login debian` tanpa `--user`, prompt diakhiri `#`): hapus kata `sudo`.
   - Masuk sebagai **pengguna biasa** (mis. `--user tiny`, prompt diakhiri `$`): tetap pakai `sudo`. Kalau `sudo` belum ada atau ditolak, keluar dulu (`exit`), masuk sebagai root dengan `proot-distro login debian`, jalankan perintah pasang tanpa `sudo`, lalu `exit` dan masuk lagi sebagai penggunamu.

   Kalau `/sdcard` tidak ada, jalankan `termux-setup-storage` di Termux, lalu login ulang ke Debian.
3. Jalankan:
   ```bash
   linkdeck-start
   ```
   Pertama kali kamu ditanya **resolusi** (Enter = `1920x1080`) dan diminta membuat **sandi VNC** (6–8 karakter). Lalu muncul PIN dan alamat HP per jaringan, contoh:
   ```
     Debian siap untuk LinkDeck (otomatis terlihat di PC pada jaringan yang sama)
     Mode        : baru (DISPLAY :1, 1920x1080)
     PIN agen    : 178778
     Sidik jari  : 3B:33:50:39:B9:55:75:30   (cocokkan dengan yang tampil di LinkDeck)
     Alamat HP per jaringan (pakai yang SATU jaringan dengan laptop):
     Wi-Fi (wlan0)             : 192.168.1.57
     Bluetooth (bt-pan)        : 192.168.44.1
     Data seluler (rmnet_data0): 10.169.158.53
     Log         : /home/kamu/.linkdeck/*.log
   ```
   Alamat **Data seluler** tidak bisa dipakai untuk menyambung dari laptop.

### 4.2 Menyambungkan Debian

| Jalur | Langkah |
|---|---|
| **Kabel** | Colok kabel dengan Debugging USB aktif → `linkdeck-start` → Debian muncul di panel Debian dengan label **Kabel** |
| **Wi-Fi** | HP dan laptop satu Wi-Fi → `linkdeck-start` → Debian muncul otomatis |
| **Bluetooth** | Tethering Bluetooth + laptop bergabung (lihat [3.3](#33-sambung-lewat-bluetooth) langkah 3–4) → `linkdeck-start` → Debian muncul dengan label **Bluetooth** |

Pilih Debian yang muncul → pastikan **Sidik jari** yang tampil di LinkDeck sama dengan di layar `linkdeck-start` → isi **PIN agen** dan **Sandi VNC** sekali → **Hubungkan**. Berikutnya tersambung otomatis.

Tidak muncul? Klik **Tidak muncul? Isi alamat manual** → pilih jalurnya → isi **IP HP** (untuk Bluetooth, LinkDeck mengisi IP-nya sendiri bila jaringan Bluetooth terdeteksi).

### 4.3 Memakai Debian

- **Desktop / Terminal** — desktop XFCE atau terminal Debian.
- **Suara** — suara Debian diputar di laptop.
- **Satu mouse** — gerakkan kursor melewati tepi layar laptop untuk mengendalikan Debian; kembali lewat tepi seberang atau `Ctrl + Alt + Home`.
- **Layar penuh** — penuh di layar ini atau di monitor/TV pilihan.
- **Lainnya** — **Resolusi desktop Debian** (pilih 1280×720 untuk Bluetooth), **Layar tujuan untuk layar penuh**, dan **Posisi Debian untuk "Satu mouse"**.
- **Alat** — membuka laci **Alat Debian** dengan tiga tab (butuh agen 1.10.0 atau lebih baru):

| Tab | Isi |
|---|---|
| **Berkas** | Jelajahi seluruh sistem berkas Debian. **~ Rumah** kembali ke folder rumah; centang **Tampilkan berkas tersembunyi** untuk berkas berawalan titik. Klik nama untuk pratinjau foto/video/musik/teks, **Unduh** ke `Downloads/LinkDeck` di laptop, **Unggah ke sini**, **+ Folder**, **Ganti nama**, dan **Hapus**. Demi keamanan, mengubah (unggah, buat, ganti nama, hapus) hanya bisa di dalam folder rumah (`~`); folder lain bertanda *Hanya baca*. Batas per berkas 48 MB |
| **Aplikasi** | Toko aplikasi Debian: daftar **aplikasi populer**, kolom **Cari** (nama paket), lalu **Pasang** atau **Copot**. Keluaran `apt` tampil langsung. **Perbarui daftar paket** = `apt update` (jalankan dulu bila pencarian kosong). Bila Debian dijalankan sebagai pengguna biasa, isi **Sandi sudo** (dipakai sekali, tidak disimpan, tidak tampil di log) |
| **Sistem** | Pemakaian CPU, RAM, swap, ruang kosong folder rumah dan sistem, lama menyala, dan daftar proses (CPU, RAM, pengguna). **Hentikan** (SIGTERM) atau **Paksa** (SIGKILL) proses milikmu. Diperbarui tiap 3 detik; daftar berhenti diperbarui selama kursor di atas tabel supaya tombol tidak bergeser |

> Di proot-distro, Android membatasi sebagian data sistem: angka CPU, waktu menyala, atau beban bisa berupa perkiraan, dan proses aplikasi Android lain tidak terlihat (hanya proses di dalam Debian).

**Baterai HP tanpa adb** (agen 1.11.0 atau lebih baru) — bila HP hanya tersambung lewat Debian (tanpa Debugging USB/nirkabel), kartu **Pantauan** tetap menampilkan persen baterai, ⚡ saat mengisi, dan suhu dengan label *Debian*. Agen membacanya dari aplikasi **LinkDeck Pendamping** bila terpasang (langsung, setiap berubah), lalu dari `termux-battery-status` (paket `termux-api` + aplikasi Termux:API), lalu dari `/sys/class/power_supply` (biasanya hanya terbaca di chroot/root). Bila tidak ada yang tersedia, kartu baterai kosong selama adb tidak tersambung.

---

## 5. Fitur bersama

- **Clipboard bersama** — salin di laptop, HP Android, atau Debian, lalu tempel di perangkat lain; berjalan selama HP tersambung, tanpa perlu membuka jendela.
  - **Android:** salin seperti biasa di aplikasi mana pun.
  - **Debian:** `Ctrl + C` di aplikasi XFCE, atau `Ctrl + Shift + C` di terminal. Berlaku di desktop LinkDeck **dan** di XFCE yang tampil di layar HP (Termux:X11); salinan juga disamakan antar keduanya.
  - **Gambar & berkas** (laptop ↔ Debian): salin gambar (mis. tangkapan layar, gambar dari browser) atau berkas (mis. di File Explorer / Thunar) lalu tempel (`Ctrl + V`) di perangkat lain. Berkas disalin ke `Downloads/LinkDeck/Clipboard` di laptop atau `~/Downloads/LinkDeck/Clipboard` di Debian, lalu clipboard di sana diisi berkas itu sehingga langsung bisa ditempel di pengelola berkas. Batas: 20 berkas per salinan, 48 MB per berkas (folder tidak ikut), gambar 20 MB. Butuh agen 1.10.0 atau lebih baru. Laptop yang didukung: Windows dan Linux (X11/Wayland); di macOS hanya teks. **HP Android hanya menerima teks** (batasan clipboard Android lewat adb).
  - Kartu ini menampilkan riwayat, asal tiap salinan (**PC**, **HP**, **Debian**), gambar mini untuk gambar, dan status tiap perangkat (titik hijau = terpantau). Untuk gambar/berkas di riwayat: **Salin lagi** mengisi ulang clipboard laptop dan Debian; **Buka folder** membuka lokasi berkas di laptop.
  - Sakelar **Android** menyalakan/mematikan pemantauan clipboard HP; sakelar **Gambar & berkas** menyalakan/mematikan salinan gambar dan berkas (matikan untuk menghemat kuota lewat Bluetooth); tombol **Uji** menulis teks uji lalu memeriksa apakah sampai di HP dan Debian.
- **Notifikasi HP** — notifikasi Android tampil di laptop; klik untuk membuka aplikasinya di jendela sendiri. Dengan **LinkDeck Pendamping**, notifikasi muncul seketika dan bisa dibalas — lihat di bawah.
- **Berkas** — seret berkas ke kotak **Tarik berkas ke sini**: **Ke Android** (masuk `Download/LinkDeck`) atau **Ke Debian** (masuk `~/Downloads/LinkDeck`). Dari Debian ke laptop: taruh berkas di `~/LinkDeck-Kirim`.
- **Buka tautan** — buka link di Android atau Debian.
- **Folder sinkron dua arah** — isi `LinkDeck-Sinkron` di laptop dan di Debian selalu disamakan.
- **Mode TV** — colok TV ke laptop (HDMI) → **Mode TV** → pilih **Android**, **Debian**, atau **Aplikasi HP** → resolusi → **Layar tujuan** → **Mulai Mode TV**.

### Notifikasi HP & LinkDeck Pendamping

Tanpa aplikasi tambahan, LinkDeck membaca notifikasi lewat adb setiap beberapa detik. Pasang **LinkDeck Pendamping** (aplikasi kecil, ±25 KB) untuk:

- **Membalas pesan** (WhatsApp, Telegram, SMS, dll.) langsung dari laptop: klik **Balas** di notifikasi → tulis → `Enter` atau **Kirim**. `Esc` membatalkan.
- **Tombol aksi** notifikasi (mis. **Tandai dibaca**, **Arsipkan**) dan **×** untuk menutup notifikasi di HP.
- Notifikasi **seketika** (bukan tiap beberapa detik), percakapan menampilkan beberapa pesan terakhir, dan notifikasi yang ditutup di HP ikut hilang dari laptop.
- **Status baterai langsung**: persen, ⚡ saat mengisi (USB, pengisi daya, nirkabel), dan suhu di kartu **Pantauan** dan info Mode Game.
- Lebih hemat: selama pendamping tersambung, LinkDeck berhenti menjalankan `dumpsys` berkala (terasa lewat Bluetooth).

**Memasang:** sambungkan Android (kabel, Wi-Fi, atau Bluetooth) → di kartu **Notifikasi HP** klik **Pasang** (atau **Pengaturan → Aplikasi pendamping Android → Pasang di HP**). LinkDeck memasang APK lewat adb dan menyalakan **akses notifikasi** otomatis — tidak perlu membuka Setelan. Label **● Seketika** menandakan pendamping aktif. LinkDeck juga memperbarui pendamping sendiri saat LinkDeck diperbarui.

**Kalau gagal:**
- Xiaomi/Redmi/POCO menolak pemasangan lewat USB: di **Opsi pengembang** nyalakan **Pasang lewat USB** (perlu masuk akun Mi), lalu klik **Pasang** lagi. Di beberapa HP, ketuk **Izinkan/Pasang** di layar HP.
- Tertulis *"akses notifikasinya mati"*: klik **Nyalakan**. Bila HP menolak, buka aplikasi **LinkDeck Pendamping** di HP → **Buka pengaturan akses notifikasi** → nyalakan **LinkDeck Pendamping**. (Android 13+: bila tombolnya terkunci karena *setelan terbatas*, buka **Setelan → Aplikasi → LinkDeck Pendamping → ⋮ → Izinkan setelan terbatas** dulu.)
- Pasang manual: unduh `linkdeck-companion.apk` dari Releases, pasang di HP, lalu nyalakan akses notifikasinya seperti di atas.

**Privasi:** pendamping tidak punya izin internet. Ia hanya membuka soket lokal di HP yang dijangkau LinkDeck lewat adb; isi notifikasi hanya diberikan ke adb (dan root). Aplikasi lain di HP — termasuk Debian di Termux — hanya bisa membaca status baterai, yang memang sudah dibagikan Android ke semua aplikasi. Matikan pemakaiannya di **Pengaturan → Aplikasi pendamping Android**; copot seperti aplikasi biasa.

### HP jadi mikrofon laptop

Pakai mikrofon HP untuk Zoom, Meet, Teams, Discord, atau rekaman (Android 11 ke atas, lewat kabel atau Wi-Fi).

1. **Sekali saja, siapkan kabel audio virtual** (tempat suara HP masuk sebagai "mikrofon"):
   - **Windows:** pasang [VB-CABLE](https://vb-audio.com/Cable/) (gratis), lalu restart komputer.
   - **macOS:** pasang [BlackHole 2ch](https://existential.audio/blackhole/) (gratis).
   - **Linux:** tidak perlu apa-apa — LinkDeck membuat mikrofon virtual **Mikrofon HP (LinkDeck)** sendiri lewat PulseAudio/PipeWire (butuh perintah `pactl`; di Debian/Ubuntu paket `pulseaudio-utils`).
2. Di kartu Android klik **Mikrofon HP**. Klik lagi untuk berhenti (atau lewat daftar tampilan yang berjalan).
3. Di aplikasi meeting pilih mikrofon: **CABLE Output** (Windows), **BlackHole 2ch** (macOS), atau **Mikrofon HP (LinkDeck)** (Linux).

Pilihan di **Pengaturan → Mikrofon HP**:
- **Tujuan suara** — **Mikrofon virtual** (untuk aplikasi meeting) atau **Speaker laptop** (mendengar langsung, mis. sebagai pengeras suara).
- **Peredam bising & gema** — memakai pengolahan suara HP untuk panggilan (disarankan untuk meeting).
- **Dengarkan juga di speaker laptop** — untuk mengecek suara; bisa menimbulkan gema saat meeting.

> Di Android 11, buka kunci layar HP sebelum menyalakan mikrofon. Suara dikirim mentah (±1,5 Mbps), jadi lewat Bluetooth bisa tersendat — pakai kabel atau Wi-Fi untuk meeting.

### Alat Android

Alat-alat ini bekerja lewat adb — tidak perlu memasang aplikasi apa pun di HP.

- **Berkas HP** (ikon folder di bilah kiri) — jelajahi penyimpanan HP (`/sdcard`): buka folder, **Naik**, buat **+ Folder**, **Unggah ke sini**, **Unduh** (ke `Downloads/LinkDeck` di laptop), **Ganti nama**, dan **Hapus**. Klik nama berkas untuk pratinjau foto, video, musik, atau teks.
- **Aplikasi HP** (ikon kotak-kotak di bilah kiri) — daftar aplikasi dengan pencarian (centang **Aplikasi sistem** untuk ikut menampilkannya). Tiap aplikasi bisa **Buka** (jendela sendiri), **★ Dock**, **Hentikan**, **Cadangkan** (APK disimpan di `Downloads/LinkDeck/APK`), **Hapus data**, dan **Copot** (khusus aplikasi yang kamu pasang). Tarik berkas `.apk` ke kotak **Pasang APK** untuk memasang; kalau HP bertanya, izinkan di layar HP.
- **Dock** — aplikasi yang disematkan lewat **★ Dock** muncul di kartu Android (mode **Layar baru**); klik untuk membukanya di jendela sendiri. Maksimal 12 aplikasi.
- **Kontrol media** — saat HP memutar musik/video, kartu Android menampilkan judulnya beserta tombol sebelumnya, putar/jeda, berikutnya, dan volume.
- **Keyboard & mouse saja** — pakai keyboard dan mouse laptop untuk HP **tanpa** menampilkan layarnya. Jendela kecil terbuka; klik di dalamnya lalu mengetik/menggerakkan mouse. Tekan `Alt` kiri untuk melepas mouse. Klik tombolnya lagi untuk berhenti.

### Kenyamanan

- **Mode privasi** — tombol **Privasi** di bilah atas menyamarkan isi clipboard, notifikasi, dan judul lagu, serta menahan munculan notifikasi. Bila **Otomatis saat presentasi** menyala (Pengaturan), mode ini aktif sendiri selama **Mode TV** atau layar penuh Debian.
- **Bahasa, tema & ukuran teks** — **Pengaturan → Tampilan**: bahasa **Indonesia** atau **English**; tema **Otomatis** (ikut sistem), **Gelap**, atau **Terang**; ukuran teks **Normal**, **Besar**, atau **Lebih besar**. Pemasangan baru mengikuti bahasa sistem; pengguna versi lama tetap berbahasa Indonesia.
- **Ikon tray** — menutup jendela tidak mematikan LinkDeck: ia tetap berjalan di tray (sambungan, clipboard, notifikasi, dan pintasan tetap aktif). Klik ikon LinkDeck di tray untuk membuka lagi. Di Windows, klik kanan ikon untuk menu **Buka LinkDeck**, **Tampilkan layar Android**, dan **Keluar dari LinkDeck** (menu yang sama muncul di Linux bila desktopnya memakai AppIndicator; selain itu cukup klik ikon). Membuka LinkDeck lagi dari menu Start/aplikasi menampilkan jendela yang sudah ada. Atur di **Pengaturan → Aplikasi → Tetap berjalan di tray saat jendela ditutup**; untuk benar-benar menutup pakai **Keluar**. macOS belum punya ikon tray: menutup jendela berarti keluar dari LinkDeck.
- **Jalankan saat komputer menyala** — **Pengaturan → Aplikasi**. LinkDeck mulai diam-diam di tray saat kamu masuk ke komputer, siap menyambung HP dan Debian (macOS: jendelanya terbuka dalam keadaan diperkecil di Dock).
- **Panduan awal** — **Pengaturan → Aplikasi → Panduan awal → Buka panduan** mengulang langkah-langkah pertama kali pakai.
- **Pembaruan otomatis** — saat dibuka, LinkDeck mengecek rilis terbaru di GitHub dan menampilkan bilah **Perbarui** bila ada versi baru. Windows: pemasang diunduh lalu dijalankan otomatis; LinkDeck ditutup selama pemasangan dan biasanya terbuka lagi sendiri (bila tidak, buka dari menu Start). macOS: berkas `.dmg` dibuka — seret LinkDeck ke Applications. Linux/Debian: LinkDeck menampilkan perintah `sudo apt install …` untuk ditempel di terminal; AppImage diganti otomatis. Bisa dimatikan atau dicek manual di **Pengaturan → Pembaruan**.
- **Pintasan global** — **Pengaturan → Pintasan global → Aktifkan**. `Ctrl + Alt + M` menampilkan/menutup layar Android (memakai pengaturan **Mulai tampilkan** terakhir), `Ctrl + Alt + K` menyalakan/mematikan **Keyboard & mouse saja**. Berfungsi walau jendela LinkDeck tidak aktif (Linux: butuh sesi X11).
- **Kirim ke HP dari Explorer** (Windows) — **Pengaturan → Windows Explorer** → nyalakan. Lalu klik kanan berkas → **Kirim ke** → **LinkDeck (HP Android)**; berkas masuk ke `Download/LinkDeck` di HP. Kalau HP belum tersambung, berkas dikirim begitu HP tersambung. Di Linux dan macOS pakai perintah `--send` (lihat [Daftar perintah](#6-daftar-perintah)).
- **Laporan masalah** — **Pengaturan → Bantuan → Buat laporan**. LinkDeck membuat `linkdeck-laporan-….zip` di `Downloads/LinkDeck` (berisi info versi, status, dan log; alamat IP dan nomor seri disamarkan), lalu membuka halaman GitHub Issues untuk melampirkannya.

### Lokasi berkas

| Isi | Laptop | Debian |
|---|---|---|
| Berkas masuk, rekaman, tangkapan layar | `Downloads/LinkDeck` | `~/Downloads/LinkDeck` |
| Folder sinkron | `LinkDeck-Sinkron` (di folder pengguna) | `~/LinkDeck-Sinkron` |
| Kirim ke laptop | — | `~/LinkDeck-Kirim` |
| Pengaturan, tombol game, log | Windows `%LOCALAPPDATA%\LinkDeck` · macOS `~/Library/Application Support/LinkDeck` · Linux `~/.local/share/LinkDeck` | `~/.linkdeck` |

---

## 6. Daftar perintah

### Di terminal Debian (HP)

| Perintah | Fungsi |
|---|---|
| `proot-distro login debian --shared-tmp` | (di Termux) Masuk ke Debian sebagai root |
| `proot-distro login debian --user NAMAMU --shared-tmp` | (di Termux) Masuk ke Debian sebagai pengguna biasa |
| `linkdeck-start` | Menyalakan LinkDeck di Debian: desktop XFCE **baru** seukuran monitor (layar HP tidak berubah) |
| `linkdeck-start baru 1280x720` | Sama, dengan resolusi tertentu (mis. untuk Bluetooth) |
| `linkdeck-start baru 3840x2160` | Resolusi 4K untuk TV |
| `linkdeck-start bagikan` | Membagikan sesi XFCE yang **sedang terbuka** di HP (mis. Termux:X11, display `:0`) |
| `LINKDECK_SHARE_DISPLAY=:2 linkdeck-start bagikan` | Membagikan sesi di display lain |
| `linkdeck-stop` | Mematikan semua bagian LinkDeck di Debian |
| `linkdeck-setup` | Mengganti resolusi bawaan dan sandi VNC (PIN tetap) |
| `linkdeck-cert` | Menampilkan sidik jari sertifikat |
| `linkdeck-cert --baru` | Membuat sertifikat baru (lalu di LinkDeck: **Pengaturan → Lupakan** perangkat, sambungkan ulang) |
| `cat ~/.linkdeck/config` | Melihat PIN yang tersimpan |
| `tail -f ~/.linkdeck/agent.log` | Melihat log agen (`Ctrl + C` untuk keluar) |
| `tail -n 30 ~/.linkdeck/vnc.log` | Melihat log desktop/VNC |
| `pgrep -af "agent.py\|Xtigervnc"` | Mengecek apakah LinkDeck sedang berjalan |
| `sudo apt install ./linkdeck-agent_<versi>_all.deb` | Memasang atau memperbarui agen |
| `sudo apt remove linkdeck-agent` | Menghapus agen |
| `rm -rf ~/.linkdeck` | Menghapus semua pengaturan agen (PIN, sandi, sertifikat) |
| `apt install xclip` | Memasang ulang pemantau clipboard Debian bila kartu Clipboard menulis *"xclip belum terpasang"* |
| `apt install sudo` lalu `echo "NAMAMU ALL=(ALL) ALL" > /etc/sudoers.d/NAMAMU` | (sebagai root) Mengizinkan pengguna biasa memasang aplikasi lewat **Alat → Aplikasi** |
| `linkdeck` | Menjalankan aplikasi LinkDeck di Debian HP (paket `linkdeck-debian`) |
| `linkdeck-scrcpy-build` | Membangun scrcpy versi yang sesuai di Debian HP (untuk Layar baru, Cermin, Kamera) |
| `dpkg --print-architecture` | Melihat arsitektur Debian (`arm64` di HP) |

**Suara Debian lewat PulseAudio Termux.** Kalau tombol **Suara** memberi pesan galat, jalankan di **Termux** (bukan di Debian):
```bash
pulseaudio --start --load="module-native-protocol-tcp auth-ip-acl=127.0.0.1 auth-anonymous=1" --exit-idle-time=-1
```
Lalu di Debian, sebelum `linkdeck-start`:
```bash
sudo apt install pulseaudio-utils
export PULSE_SERVER=127.0.0.1
```

### Di laptop (semua sistem)

| Perintah | Fungsi |
|---|---|
| `linkdeck --tray` | Menjalankan LinkDeck diam-diam di tray tanpa membuka jendela (dipakai **Jalankan saat komputer menyala**). Windows: `LinkDeck.exe --tray` |
| `linkdeck --send FOTO.jpg DOKUMEN.pdf` | (Linux) Kirim berkas ke `Download/LinkDeck` di HP lewat LinkDeck yang sedang berjalan |
| `/Applications/LinkDeck.app/Contents/MacOS/LinkDeck --send BERKAS` | (macOS) Sama seperti di atas |
| `"C:\Program Files\LinkDeck\LinkDeck.exe" --send BERKAS` | (Windows) Sama seperti di atas; menu **Kirim ke** memakai perintah ini. Bila dipasang untuk pengguna saja, lokasinya `%LOCALAPPDATA%\Programs\LinkDeck` |

### Di laptop Windows

| Perintah | Fungsi |
|---|---|
| `ipconfig` (Command Prompt) | Melihat IP laptop; untuk Bluetooth lihat **Default Gateway** di *Bluetooth Network Connection* |
| `control printers` (lewat `Win + R`) | Membuka *Devices and Printers* untuk bergabung ke jaringan Bluetooth HP |
| `ping 192.168.44.1` | Mengecek HP bisa dijangkau (ganti dengan IP HP-mu) |
| `"%LOCALAPPDATA%\LinkDeck\linkdeck.log"` | Membuka log LinkDeck |

### Di laptop Linux

| Perintah | Fungsi |
|---|---|
| `linkdeck` | Menjalankan LinkDeck |
| `sudo apt install xclip` | Diperlukan untuk copy-paste (atau `wl-clipboard` di Wayland) |
| `sudo apt install v4l2loopback-dkms` | Supaya kamera HP bisa jadi webcam |
| `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Kamera HP"` | Menyalakan webcam virtual (ulangi setelah restart) |
| `sudo apt install pulseaudio-utils` | Diperlukan untuk **Mikrofon HP** (perintah `pactl`/`pacat`) |
| `pactl list short sources \| grep linkdeck` | Mengecek mikrofon virtual **Mikrofon HP (LinkDeck)** sedang aktif |
| `ls ~/.config/autostart/linkdeck.desktop` | Mengecek **Jalankan saat komputer menyala** sudah terpasang |
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

## 7. Pintasan keyboard

Di jendela **Android** (Layar baru, Cermin, Kamera). `Alt` = Alt kiri; tombol Windows/⌘ juga bisa.

| Pintasan | Fungsi |
|---|---|
| `Ctrl + C` / `Ctrl + V` | Copy-paste antara laptop dan HP |
| `Alt + F` atau `F11` | Layar penuh |
| `Alt + W` atau klik ganda | Ubah ukuran jendela agar pas tanpa bilah hitam |
| `Alt + H` atau klik tengah | Tombol Home |
| `Alt + B`, `Alt + Backspace`, atau klik kanan | Tombol Kembali |
| `Alt + S` | Daftar aplikasi terbuka |
| `Alt + N` | Buka panel notifikasi |
| `Alt + ↑` / `Alt + ↓` | Volume naik / turun (mode Kamera: zoom) |
| `Alt + T` / `Alt + Shift + T` | Senter nyala / mati (mode Kamera) |
| `Alt + P` | Tombol power |
| `Alt + O` / `Alt + Shift + O` | Matikan / nyalakan layar HP, tampilan tetap jalan |
| `Alt + R` | Putar layar HP |
| `Alt + Q` | Tutup jendela |
| Seret berkas ke jendela | APK langsung terpasang; berkas lain masuk `/sdcard/Download` |

Di **Mode Game**:

| Pintasan | Fungsi |
|---|---|
| `Esc` | Tombol Kembali Android (atau melepas bidik mouse) |
| Tahan `Esc` | Keluar dari layar penuh (Windows, Chrome/Edge) |
| `` ` `` (bisa diganti) | Mengunci/melepas mouse untuk bidik |

Lainnya:

| Pintasan | Fungsi |
|---|---|
| `Ctrl + Alt + Home` | Mengambil kembali mouse dari Debian ("Satu mouse") |
| `Ctrl + Alt + M` | Tampilkan/tutup layar Android (bila **Pintasan global** aktif) |
| `Ctrl + Alt + K` | Nyalakan/matikan **Keyboard & mouse saja** (bila **Pintasan global** aktif) |
| `Esc` | Keluar dari layar penuh Debian / menutup panel |

---

## 8. Mengatasi masalah

| Masalah | Solusi |
|---|---|
| HP tidak muncul saat dicolok | Ketuk **Izinkan** di HP. Coba kabel lain (banyak kabel hanya untuk mengecas). Matikan-nyalakan **Debugging USB** |
| Kartu Android menulis *"Izinkan debugging di layar HP"* | Cabut-colok kabel, lalu ketuk **Izinkan** (centang **Selalu izinkan**) |
| Bluetooth sudah tersambung tapi Android tidak muncul | Android perlu diaktifkan sekali lewat kabel atau Wi-Fi, lalu **Siapkan Android lewat Bluetooth** ([3.3](#33-sambung-lewat-bluetooth)). Setelah HP di-restart, ulangi sekali |
| Kode QR tidak terdeteksi | HP dan laptop harus satu Wi-Fi; sebagian router memblokir pencarian perangkat (*AP isolation*). Pakai kode 6 angka atau kabel |
| `ipconfig` menulis *Media disconnected* di Bluetooth | Tethering Bluetooth belum menyala, atau langkah **Connect using → Access point** belum dilakukan |
| Ada bilah hitam di kiri-kanan | Pakai **Layar baru** dengan ukuran **Layar ini**. Mode **Cermin** selalu mengikuti bentuk layar HP |
| Gambar patah-patah | Pakai kabel atau Wi-Fi 5 GHz; dekatkan HP ke router; pilih kualitas **Bluetooth** untuk sementara |
| Suara keluar di HP dan laptop sekaligus | Matikan **Suara juga di HP** (Pengaturan lain). Android 13+ dijamin senyap; Android 11–12 tergantung pabrikan |
| Senter tidak menyala | Senter hanya ada di kamera **belakang** |
| Gambar Android tampil, tetapi klik/ketik/Mode Game tidak berfungsi | Nyalakan **Debugging USB (Setelan keamanan)** (Xiaomi/Redmi/POCO) atau **Nonaktifkan pemantauan izin** (sebagian Oppo/Realme) di Opsi pengembang, lalu restart HP |
| Audio ke PC tidak keluar (Android 11) | Buka kunci layar HP, lalu mulai ulang tampilan |
| Mode Game layar hitam | Buka LinkDeck dari aplikasinya (Windows memakai WebView2) atau Chrome/Edge. Klik **Keluar**, lalu **Main** lagi |
| Jendela LinkDeck kosong/putih di Windows 10 | Pasang **Microsoft Edge WebView2 Runtime** (*Evergreen*) dari [situs Microsoft](https://developer.microsoft.com/microsoft-edge/webview2/), lalu buka ulang LinkDeck |
| Salinan tidak muncul di Clipboard bersama | Klik **Uji** di kartu Clipboard: hasilnya menunjukkan bagian yang bermasalah dan pesan galatnya tampil di kartu. Pastikan sakelar **Android** menyala dan Debian tersambung (titik hijau). Yang disalin harus teks |
| Salinan dari XFCE di layar HP (Termux:X11) tidak muncul | Masuk ke Debian dengan `proot-distro login debian --shared-tmp`, lalu jalankan ulang `linkdeck-start`. Perbarui agen ke 1.7.0 atau lebih baru |
| Gambar/berkas yang disalin tidak ikut | Pastikan sakelar **Gambar & berkas** menyala dan agen Debian 1.10.0 atau lebih baru (arahkan kursor ke sakelar untuk melihat alasannya). Berkas lebih dari 48 MB dan folder tidak ikut. Ke/dari HP Android hanya teks |
| **Alat** menulis *"Agen Debian … belum mendukung fitur ini"* | Perbarui agen di Debian ke 1.10.0 atau lebih baru ([bagian 4.1](#41-pasang-agen-sekali)), lalu jalankan ulang `linkdeck-start` |
| Pasang aplikasi gagal: *"Bila sandi salah…"* | Periksa **Sandi sudo**. Bila pengguna Debian belum boleh memakai sudo, masuk sebagai root lalu jalankan perintah `sudo` di [Daftar perintah](#6-daftar-perintah), atau pasang lewat terminal sebagai root |
| Pencarian di **Alat → Aplikasi** kosong | Klik **Perbarui daftar paket** dulu (Debian baru biasanya belum punya daftar paket) |
| Stik (gamepad) tidak terdeteksi di Mode Game | Tekan salah satu tombol stik sekali setelah Mode Game terbuka (browser baru mengenali stik setelah ada tombol ditekan). Stik harus terdeteksi sebagai gamepad oleh sistem operasi |
| Copy-paste tidak jalan (laptop Linux) | `sudo apt install xclip` |
| Debian tidak muncul | Pastikan `linkdeck-start` sudah jalan dan HP satu jaringan dengan laptop; atau isi alamat manual |
| Alamat HP diawali `10.` atau `100.` | Itu alamat data seluler. Pakai alamat Wi-Fi atau Bluetooth dari daftar `linkdeck-start` |
| Pintasan global tidak bereaksi | Di Linux butuh sesi X11 (Wayland belum didukung); di macOS izinkan LinkDeck di **Accessibility** dan **Input Monitoring**. Matikan lalu nyalakan lagi di Pengaturan |
| Menu **Kirim ke → LinkDeck** tidak ada | Nyalakan di **Pengaturan → Windows Explorer**. Bila LinkDeck dipindah/diinstal ulang, matikan lalu nyalakan lagi |
| Pembaruan otomatis gagal | Klik **Perbarui** sekali lagi, atau unduh manual dari halaman Releases |
| **Copot** tidak ada untuk suatu aplikasi | Aplikasi bawaan (sistem) tidak bisa dicopot dari LinkDeck — hanya aplikasi yang kamu pasang sendiri |
| `libc6:amd64 ... [no choices]` saat memasang di HP | Berkasnya salah: `linkdeck_<versi>_amd64.deb` hanya untuk laptop Intel/AMD. Di HP pakai `linkdeck-debian_<versi>_all.deb` (aplikasi) atau `linkdeck-agent_<versi>_all.deb` (agen) |
| `dpkg: error: requested operation requires superuser privilege` saat memasang agen | Kamu masuk sebagai pengguna biasa. Pakai `sudo apt install ./linkdeck-agent_<versi>_all.deb`, atau masuk sebagai root (`proot-distro login debian`) lalu pasang tanpa `sudo`. Peringatan `debconf ... Dialog` aman diabaikan |
| *"Agen Debian tidak menjawab"* | `linkdeck-stop`, lalu `linkdeck-start`. Lihat log: `tail -n 30 ~/.linkdeck/agent.log` |
| *"PIN agen salah"* | Lihat PIN dengan `cat ~/.linkdeck/config` |
| *"Sandi VNC salah"* | Buat sandi baru dengan `linkdeck-setup`, lalu sambungkan ulang |
| *"Sidik jari sertifikat berubah"* | Kalau baru menjalankan `linkdeck-cert --baru`: **Pengaturan → Lupakan** perangkat lalu sambungkan ulang. Kalau tidak, jangan lanjutkan — bisa ada yang menyamar di jaringan |
| Layar hitam di desktop Debian | `linkdeck-stop`, lalu `linkdeck-start`. Cek `tail -n 30 ~/.linkdeck/xfce.log` |
| Suara Debian tidak keluar | Lihat *Suara Debian lewat PulseAudio Termux* di [bagian 6](#di-terminal-debian-hp) |
| "Satu mouse" tidak jalan di macOS | **System Settings → Privacy & Security** → izinkan LinkDeck di **Accessibility** dan **Input Monitoring** |
| "Satu mouse" tidak jalan di Linux | Butuh sesi **X11**; Wayland belum didukung |
| Windows SmartScreen menghalangi | **More info → Run anyway** (aplikasi belum ditandatangani sertifikat berbayar) |
| **Mikrofon HP**: *"Kabel audio virtual tidak ditemukan"* | Pasang VB-CABLE (Windows, lalu restart) atau BlackHole 2ch (macOS), lalu coba lagi. Atau pilih **Speaker laptop** di **Pengaturan → Mikrofon HP** |
| Mikrofon HP tidak terdengar di Zoom/Meet | Di aplikasi meeting pilih mikrofon **CABLE Output** (Windows), **BlackHole 2ch** (macOS), atau **Mikrofon HP (LinkDeck)** (Linux) — bukan *CABLE Input*. Android 11: buka kunci layar HP dulu |
| *"Mikrofon virtual tidak bisa dibuat"* (Linux) | `sudo apt install pulseaudio-utils`, pastikan PulseAudio/PipeWire berjalan (`pactl info`) |
| Webcam: *"Kamera virtual tidak bisa dibuka"* (Windows/macOS) | Pasang OBS Studio 30 ke atas, buka sekali lalu tutup, coba lagi. Jangan nyalakan *Start Virtual Camera* di OBS bersamaan |
| Notifikasi tidak bisa dibalas / tidak ada tombol **Balas** | Pasang **LinkDeck Pendamping** (kartu **Notifikasi HP** → **Pasang**). Tombol **Balas** hanya muncul bila aplikasi pengirim menyediakan balasan langsung di notifikasinya |
| Pemasangan pendamping gagal (*INSTALL_FAILED_USER_RESTRICTED*) | Xiaomi/POCO: **Opsi pengembang → Pasang lewat USB** (masuk akun Mi); HP lain: ketuk **Izinkan** di layar HP. Lihat [Notifikasi HP & LinkDeck Pendamping](#notifikasi-hp--linkdeck-pendamping) |
| Ikon tray tidak muncul (Linux) | GNOME tidak punya area tray bawaan: pasang ekstensi *AppIndicator and KStatusNotifierItem Support* (`sudo apt install gnome-shell-extension-appindicator`), lalu log out dan masuk lagi. Tanpa area tray, menutup jendela akan keluar dari LinkDeck (Pengaturan memberi tahu bila ini terjadi) |
| LinkDeck tidak menyala sendiri saat login | Matikan lalu nyalakan lagi **Pengaturan → Aplikasi → Jalankan saat komputer menyala** (perlu bila LinkDeck dipindah/diinstal ulang). Windows: cek **Task Manager → Startup apps** |
| Baterai di Pantauan kosong saat hanya Debian yang tersambung | Pasang LinkDeck Pendamping di HP, atau `termux-api` di Termux + aplikasi Termux:API. Agen harus 1.11.0 atau lebih baru |

Masih bermasalah? Buka **Issues** di repo ini dan lampirkan log LinkDeck (lihat *Lokasi berkas*) — serta `~/.linkdeck/agent.log` bila masalahnya di Debian.

---

## 9. Untuk pengembang

### Struktur proyek
```
app.py                 aplikasi desktop: server di latar + jendela (WebView2 / WKWebView / Chrome)
server.py              backend: adb, scrcpy, Mode Game, penemuan otomatis, terowongan TLS, sinkron, notifikasi
pcclip.py              clipboard laptop: teks, gambar, dan berkas (Win32 / NSPasteboard / xclip / wl-clipboard)
features.py            berkas & aplikasi HP, media, pembaruan otomatis, pintasan global, laporan masalah
richclip.py            clipboard gambar & berkas laptop ↔ Debian
debiantools.py         Alat Debian: berkas, toko aplikasi (apt), pemantau sistem
kvm.py                 "Satu mouse" lintas laptop dan Debian
notif.py               pembaca notifikasi Android dan daftar aplikasi
tray.py                ikon tray dan jalan otomatis saat login (Windows/macOS/Linux)
mediadev.py            HP jadi mikrofon (kabel audio virtual / PulseAudio) dan webcam Windows/macOS (OBS Virtual Camera)
companionlink.py       sambungan ke aplikasi pendamping Android: notifikasi seketika, balas, baterai
companion/             kode aplikasi pendamping Android (Java, tanpa Gradle)
static/index.html      antarmuka
static/i18n/en.js      kamus bahasa Inggris untuk antarmuka
phone/agent.py         agen di Debian HP
phone/bin/             linkdeck-start, linkdeck-stop, linkdeck-setup, linkdeck-cert
build/                 unduh dependensi, spec PyInstaller, pengemasan, ikon, installer Windows, APK pendamping
.github/workflows/     build otomatis semua OS
```

### Menjalankan dari kode
```bash
pip install -r requirements.txt
python build/fetch_deps.py windows    # atau linux | macos-arm64 | macos-x86_64 (adb, scrcpy, noVNC, xterm.js)
python app.py                         # aplikasi desktop
python server.py                      # server saja, buka http://127.0.0.1:8740
```

### Membuat installer lewat GitHub Actions
Workflow `.github/workflows/build.yml` membangun APK pendamping Android, installer Windows, macOS (Apple Silicon), Linux, dan paket agen Debian. APK ditandatangani kunci sementara kecuali secret `COMPANION_KEYSTORE_B64` (keystore dalam base64) dan `COMPANION_KEYSTORE_PASS` diisi di **Settings → Secrets and variables → Actions**; dengan kunci tetap, pembaruan pendamping terpasang di atas versi lama tanpa dicopot dulu.
```bash
git tag v<versi>
git push origin v<versi>
```
Tunggu 10–15 menit di tab **Actions**; hasilnya muncul di **Releases**. Tanpa tag: **Actions → Build LinkDeck → Run workflow** (hasil di *Artifacts*).

> Mengunggah lewat browser tidak menyertakan folder tersembunyi `.github`. Buat `.github/workflows/build.yml` lewat **Add file → Create new file**, atau pakai `terbitkan.bat` / `terbitkan.sh`.

### Menerbitkan dengan satu perintah
- **Windows:** klik dua kali `terbitkan.bat`
- **Linux/macOS:** `bash terbitkan.sh`

Skrip membuka browser untuk login GitHub, membuat (atau memperbarui) repo, mengunggah kode, dan memicu build. Butuh Git dan GitHub CLI (`winget install GitHub.cli`, `sudo apt install git gh`, atau `brew install gh`).

### Membuat installer di komputer sendiri
```bash
pip install -r requirements.txt -r build/requirements-build.txt
python build/fetch_deps.py linux
python build/build_agent_deb.py
python build/build_companion.py       # opsional: APK pendamping (butuh: sudo apt install aapt apksigner zipalign dalvik-exchange android-sdk-platform-23 default-jdk-headless)
pyinstaller build/linkdeck.spec --noconfirm
python build/package.py linux         # hasil di folder out/
```

### Menambah atau mengubah teks antarmuka
Teks asli antarmuka berbahasa Indonesia. Terjemahan Inggris ada di `static/i18n/en.js` (teks utuh, kalimat berformat, dan pola untuk pesan yang memuat nilai). Setelah menambah teks, jalankan `python build/check_i18n.py` (butuh `pip install playwright` dan `python -m playwright install chromium`) untuk melihat teks yang belum diterjemahkan.

### Port yang dipakai
| Port | Di mana | Fungsi |
|---|---|---|
| `8740` TCP | Laptop (hanya lokal) | Antarmuka LinkDeck |
| `47823` UDP | Laptop | Menerima sinyal penemuan otomatis dari Debian di HP |
| `5555` TCP | HP | adb lewat jaringan (setelah **Siapkan Android lewat Wi-Fi/Bluetooth**) |
| `8765` TCP (TLS) | HP | Agen Debian: desktop, terminal, suara, clipboard, berkas |
| `5901` TCP | HP (hanya lokal) | Server VNC desktop Debian |

---

## 10. Keamanan dan komponen pihak ketiga

- Antarmuka LinkDeck hanya bisa diakses dari laptop itu sendiri dan dilindungi token sesi.
- Semua lalu lintas ke Debian **terenkripsi TLS**; sertifikat HP dikunci saat pertama tersambung, dan LinkDeck menolak menyambung bila sertifikatnya berubah. Agen dilindungi **PIN**, desktop dilindungi **sandi VNC**, dan server VNC hanya bisa diakses dari HP itu sendiri.
- adb lewat jaringan (port 5555) tidak terenkripsi dan tetap aktif sampai HP di-restart. Pakai hanya di jaringan yang kamu percayai.
- Aplikasi **LinkDeck Pendamping** tidak punya izin internet dan hanya membuka soket lokal (`linkdeck_companion`) di HP. Isi notifikasi dan perintah balas hanya dilayani untuk adb (pengguna *shell*) dan root; penyambung lain hanya menerima status baterai.

LinkDeck memakai komponen pihak ketiga berikut, masing-masing dengan lisensinya sendiri:
[scrcpy](https://github.com/Genymobile/scrcpy) (Apache-2.0),
[Android SDK Platform-Tools / adb](https://developer.android.com/tools/releases/platform-tools),
[noVNC](https://github.com/novnc/noVNC) (MPL-2.0),
[xterm.js](https://github.com/xtermjs/xterm.js) (MIT),
[TigerVNC](https://tigervnc.org/) (GPL-2.0, di HP),
[aiohttp](https://github.com/aio-libs/aiohttp), [pywebview](https://github.com/r0x0r/pywebview), [pynput](https://github.com/moses-palmer/pynput), [pyperclip](https://github.com/asweigart/pyperclip), [python-qrcode](https://github.com/lincolnloop/python-qrcode), [pystray](https://github.com/moses-palmer/pystray) dan [Pillow](https://python-pillow.org/) (ikon tray), serta di Windows/macOS [python-sounddevice](https://github.com/spatialaudio/python-sounddevice), [PyAV](https://github.com/PyAV-Org/PyAV), [pyvirtualcam](https://github.com/letmaik/pyvirtualcam), dan [NumPy](https://numpy.org/) (mikrofon & webcam). VB-CABLE, BlackHole, dan OBS Studio dipasang sendiri oleh pengguna bila dibutuhkan dan tidak ikut dalam LinkDeck.

---

## 11. Aplikasi LinkDeck di Debian HP (arm64)

Selain dipakai di laptop, aplikasi LinkDeck juga bisa dipasang **di Debian 13 XFCE pada HP itu sendiri**. Gunanya:

- **Layar baru**: aplikasi Android terbuka sebagai **jendela di desktop XFCE**, seperti mode desktop. Paling terasa saat XFCE ditampilkan di monitor/TV.
- **Clipboard bersama** antara Android dan Debian di HP yang sama.
- **Kamera** dan **Mode Game** di dalam Debian.
- **Cermin** layar Android (berguna saat XFCE tampil di monitor; di layar HP sendiri gambarnya akan berulang seperti cermin berhadapan).

Paket ini **tidak sama** dengan agen. Agen (`linkdeck-agent`) membuat Debian tampil di laptop; aplikasi (`linkdeck-debian`) menjalankan LinkDeck di Debian. Keduanya boleh dipasang bersamaan.

### 11.1 Pasang

1. Unduh `linkdeck-debian_<versi>_all.deb` dari halaman Releases ke HP.
2. Di terminal Debian:
   ```bash
   sudo apt update
   sudo apt install /sdcard/Download/linkdeck-debian_<versi>_all.deb
   ```
   Paket ini sekaligus memasang adb, scrcpy, Chromium, dan pustaka Python dari repositori Debian (unduhannya bisa beberapa ratus MB). Kalau masuk sebagai root, hapus `sudo` (lihat [bagian 4.1](#41-pasang-agen-sekali)).
3. Cek versi scrcpy:
   ```bash
   scrcpy --version
   ```
   **Layar baru**, **Cermin**, dan **Kamera** butuh scrcpy **4.0 atau lebih baru**. Kalau versinya lebih lama, bangun versi yang sesuai langsung di HP (sekali saja, butuh internet, sekitar 5–15 menit):
   ```bash
   linkdeck-scrcpy-build
   ```
   **Mode Game** dan **Clipboard bersama** sudah jalan tanpa langkah ini, karena memakai server scrcpy bawaan LinkDeck.
4. Jalankan dari menu aplikasi XFCE (cari **LinkDeck**) atau ketik `linkdeck` di terminal.

### 11.2 Sambungkan Android di HP yang sama

LinkDeck di Debian mengendalikan Android lewat adb, sama seperti di laptop. Bedanya, adb di HP harus membuka "pintu jaringan" (port 5555) agar bisa dijangkau dari Debian. Pilih salah satu:

**Cara A — dengan laptop (paling mudah):**
1. Sambungkan HP ke LinkDeck di laptop (kabel atau Wi-Fi), lalu klik **Lanjut tanpa kabel** → **Siapkan Android lewat Wi-Fi** (atau **Bluetooth**). Langkah ini membuka port 5555 di HP.
2. Buka LinkDeck di Debian HP. Android tersambung sendiri dengan label **HP ini** (alamat `127.0.0.1:5555`). Pertama kali, HP bertanya *"Izinkan debugging USB?"* untuk Debian — centang **Selalu izinkan** → **Izinkan**.

**Cara B — tanpa laptop (Android 11+, HP harus tersambung ke Wi-Fi):**
1. Di HP: **Opsi pengembang → Debugging nirkabel** → nyalakan.
2. Buka LinkDeck di Debian → **Sambungkan perangkat → Android → Wi-Fi → Atau pakai kode 6 angka**.
3. Pakai **layar terpisah** (split screen): satu sisi **Setelan → Debugging nirkabel → Sambungkan perangkat dengan kode penyambungan**, sisi lain LinkDeck. Isi **Alamat pairing** dan **Kode** yang tampil di Setelan → **Pasangkan & sambungkan**.
4. Kalau belum tersambung sendiri, isi alamat yang tertera di layar utama **Debugging nirkabel** (port-nya berbeda dari alamat pairing) ke **Alamat debugging (manual)** → **Sambungkan**.

Port 5555 tertutup lagi setiap HP di-restart; ulangi Cara A atau B setelah restart.

### 11.3 Tips

- Lewat jalur **HP ini**, kualitas video otomatis diturunkan (4 Mbps, 30 fps, maks. 1280 px) karena merekam dan menampilkan dikerjakan prosesor yang sama.
- Panel **Debian** di aplikasi ini tidak diperlukan — kamu sudah berada di Debian.
- **LinkDeck Pendamping** juga bisa dipasang dari sini (kartu **Notifikasi HP** → **Pasang**) untuk membalas notifikasi Android dari desktop XFCE.
- Kalau jendela LinkDeck tidak terbuka: pastikan Chromium terpasang (`sudo apt install chromium`). LinkDeck menjalankannya dengan opsi `--no-sandbox` karena sandbox Chromium tidak tersedia di proot.

Riwayat perubahan ada di [CHANGELOG.md](CHANGELOG.md).
