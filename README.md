# LinkDeck

**Tampilkan dan kendalikan HP Android di laptop, monitor, atau TV — lewat kabel, Wi-Fi, atau Bluetooth — tanpa mengganggu layar yang sedang terbuka di HP.**

LinkDeck adalah aplikasi desktop (Windows, macOS, Linux) untuk:

- **Layar baru** — membuat layar Android tambahan di laptop; layar HP tetap bisa dipakai seperti biasa.
- **Cermin** — menampilkan persis apa yang ada di layar HP.
- **Kamera** — kamera HP tampil di laptop (senter, zoom, belakang/depan).
- **Mode Game** — main game Android dengan keyboard & mouse (WASD, tombol, bidik mouse) dalam layar penuh seukuran laptop.

**Unduh:** [halaman Releases](https://github.com/karamoyyy/LinkDeck/releases/latest) · **Panduan:** halaman ini.

Ditambah fitur bersama: copy-paste dua arah, kirim berkas, notifikasi HP di laptop, dan Mode TV. Bila HP-mu juga menjalankan **Debian 13 XFCE** (mis. lewat Termux), LinkDeck bisa menampilkan desktop, terminal, dan suara Debian — ini opsional dan disambungkan terpisah dari Android.

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

Tidak perlu memasang aplikasi apa pun di Android.

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

Di Linux, kamera HP bisa dijadikan webcam untuk Zoom/Meet lewat **Jadikan webcam untuk aplikasi meeting** (butuh modul `v4l2loopback`, lihat [bagian 6](#di-laptop-linux)).

### 3.8 Memakai Mode Game

1. Pilih **Game**, ketik nama game (mis. *Mobile Legends*), lalu klik **Main**. Kosongkan nama untuk menampilkan layar HP apa adanya.
2. Game terbuka layar penuh seukuran laptop. Gerakkan mouse ke **bagian atas layar** untuk memunculkan menu.
3. **Atur tombol:** klik **Edit tombol** → **Template dasar** (atau tambah sendiri) → seret tiap tanda ke tombol di layar game → klik sebuah tanda lalu tekan tombol keyboard penggantinya → **Simpan**. Pengaturan disimpan terpisah untuk setiap game.

| Jenis tanda | Cara kerja |
|---|---|
| **Joystick WASD** | W/A/S/D menggeser jari di lingkaran joystick (bisa diganti **Pakai panah**). **Ukuran** lingkaran bisa diatur |
| **Tombol** | Tombol keyboard = ketukan di titik itu. Bisa juga **Klik kiri** / **Klik kanan** (aktif saat bidik mouse menyala) |
| **Bidik mouse** | Tekan tombolnya (bawaan `` ` ``) untuk mengunci mouse: gerakan mouse menggeser kamera/bidikan. **Kepekaan** bisa diatur. Tekan lagi atau `Esc` untuk melepas |

- Klik mouse biasa = sentuhan satu jari. Roda mouse = gulir.
- Tombol yang tidak dipetakan dikirim sebagai ketikan (untuk chat).
- `Esc` = tombol **Kembali** Android. Untuk keluar dari layar penuh, **tahan** `Esc` (Windows, Chrome/Edge) atau klik **Layar penuh** di menu atas.
- **Tanda tombol** menyembunyikan/menampilkan tanda; **Keluar** menutup Mode Game.

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

---

## 5. Fitur bersama

- **Clipboard bersama** — salin di laptop, HP Android, atau Debian, lalu tempel di perangkat lain; berjalan selama HP tersambung, tanpa perlu membuka jendela.
  - **Android:** salin seperti biasa di aplikasi mana pun.
  - **Debian:** `Ctrl + C` di aplikasi XFCE, atau `Ctrl + Shift + C` di terminal. Berlaku di desktop LinkDeck **dan** di XFCE yang tampil di layar HP (Termux:X11); salinan juga disamakan antar keduanya.
  - Kartu ini menampilkan riwayat, asal tiap salinan (**PC**, **HP**, **Debian**), dan status tiap perangkat (titik hijau = terpantau). Sakelar **Android** menyalakan/mematikan pemantauan clipboard HP; tombol **Uji** menulis teks uji lalu memeriksa apakah sampai di HP dan Debian.
- **Notifikasi HP** — notifikasi Android tampil di laptop; klik untuk membuka aplikasinya di jendela sendiri.
- **Berkas** — seret berkas ke kotak **Tarik berkas ke sini**: **Ke Android** (masuk `Download/LinkDeck`) atau **Ke Debian** (masuk `~/Downloads/LinkDeck`). Dari Debian ke laptop: taruh berkas di `~/LinkDeck-Kirim`.
- **Buka tautan** — buka link di Android atau Debian.
- **Folder sinkron dua arah** — isi `LinkDeck-Sinkron` di laptop dan di Debian selalu disamakan.
- **Mode TV** — colok TV ke laptop (HDMI) → **Mode TV** → pilih **Android**, **Debian**, atau **Aplikasi HP** → resolusi → **Layar tujuan** → **Mulai Mode TV**.

### Alat Android

Semua alat ini bekerja lewat adb — tidak perlu memasang aplikasi apa pun di HP.

- **Berkas HP** (ikon folder di bilah kiri) — jelajahi penyimpanan HP (`/sdcard`): buka folder, **Naik**, buat **+ Folder**, **Unggah ke sini**, **Unduh** (ke `Downloads/LinkDeck` di laptop), **Ganti nama**, dan **Hapus**. Klik nama berkas untuk pratinjau foto, video, musik, atau teks.
- **Aplikasi HP** (ikon kotak-kotak di bilah kiri) — daftar aplikasi dengan pencarian (centang **Aplikasi sistem** untuk ikut menampilkannya). Tiap aplikasi bisa **Buka** (jendela sendiri), **★ Dock**, **Hentikan**, **Cadangkan** (APK disimpan di `Downloads/LinkDeck/APK`), **Hapus data**, dan **Copot** (khusus aplikasi yang kamu pasang). Tarik berkas `.apk` ke kotak **Pasang APK** untuk memasang; kalau HP bertanya, izinkan di layar HP.
- **Dock** — aplikasi yang disematkan lewat **★ Dock** muncul di kartu Android (mode **Layar baru**); klik untuk membukanya di jendela sendiri. Maksimal 12 aplikasi.
- **Kontrol media** — saat HP memutar musik/video, kartu Android menampilkan judulnya beserta tombol sebelumnya, putar/jeda, berikutnya, dan volume.
- **Keyboard & mouse saja** — pakai keyboard dan mouse laptop untuk HP **tanpa** menampilkan layarnya. Jendela kecil terbuka; klik di dalamnya lalu mengetik/menggerakkan mouse. Tekan `Alt` kiri untuk melepas mouse. Klik tombolnya lagi untuk berhenti.

### Kenyamanan

- **Mode privasi** — tombol **Privasi** di bilah atas menyamarkan isi clipboard, notifikasi, dan judul lagu, serta menahan munculan notifikasi. Bila **Otomatis saat presentasi** menyala (Pengaturan), mode ini aktif sendiri selama **Mode TV** atau layar penuh Debian.
- **Tema & ukuran teks** — **Pengaturan → Tampilan**: tema **Otomatis** (ikut sistem), **Gelap**, atau **Terang**; ukuran teks **Normal**, **Besar**, atau **Lebih besar**.
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

Masih bermasalah? Buka **Issues** di repo ini dan lampirkan log LinkDeck (lihat *Lokasi berkas*) — serta `~/.linkdeck/agent.log` bila masalahnya di Debian.

---

## 9. Untuk pengembang

### Struktur proyek
```
app.py                 aplikasi desktop: server di latar + jendela (WebView2 / WKWebView / Chrome)
server.py              backend: adb, scrcpy, Mode Game, penemuan otomatis, terowongan TLS, sinkron, notifikasi
pcclip.py              clipboard laptop (Win32 / NSPasteboard / xclip)
kvm.py                 "Satu mouse" lintas laptop dan Debian
notif.py               pembaca notifikasi Android dan daftar aplikasi
static/index.html      antarmuka
phone/agent.py         agen di Debian HP
phone/bin/             linkdeck-start, linkdeck-stop, linkdeck-setup, linkdeck-cert
build/                 unduh dependensi, spec PyInstaller, pengemasan, ikon, installer Windows
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
Workflow `.github/workflows/build.yml` membangun installer Windows, macOS (Apple Silicon), Linux, dan paket agen Debian.
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
pyinstaller build/linkdeck.spec --noconfirm
python build/package.py linux         # hasil di folder out/
```

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

LinkDeck memakai komponen pihak ketiga berikut, masing-masing dengan lisensinya sendiri:
[scrcpy](https://github.com/Genymobile/scrcpy) (Apache-2.0),
[Android SDK Platform-Tools / adb](https://developer.android.com/tools/releases/platform-tools),
[noVNC](https://github.com/novnc/noVNC) (MPL-2.0),
[xterm.js](https://github.com/xtermjs/xterm.js) (MIT),
[TigerVNC](https://tigervnc.org/) (GPL-2.0, di HP),
[aiohttp](https://github.com/aio-libs/aiohttp), [pywebview](https://github.com/r0x0r/pywebview), [pynput](https://github.com/moses-palmer/pynput), [pyperclip](https://github.com/asweigart/pyperclip), dan [python-qrcode](https://github.com/lincolnloop/python-qrcode).

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
- Kalau jendela LinkDeck tidak terbuka: pastikan Chromium terpasang (`sudo apt install chromium`). LinkDeck menjalankannya dengan opsi `--no-sandbox` karena sandbox Chromium tidak tersedia di proot.

Riwayat perubahan ada di [CHANGELOG.md](CHANGELOG.md).
