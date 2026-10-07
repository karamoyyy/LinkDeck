# Riwayat perubahan

## 1.9.0 — pembaruan besar tahap 1
**Alat Android (tanpa aplikasi tambahan di HP)**
- **Berkas HP**: jelajahi `/sdcard`, unggah ke folder mana pun, unduh, ganti nama, hapus, buat folder, dan pratinjau foto/video/musik/teks.
- **Aplikasi HP**: daftar dengan pencarian (termasuk aplikasi sistem), buka di jendela sendiri, hentikan, cadangkan APK (termasuk aplikasi split), hapus data, copot, dan pasang APK dengan seret-lepas.
- **Dock aplikasi favorit** di kartu Android (maks. 12).
- **Kontrol media**: judul yang sedang diputar, sebelumnya/putar-jeda/berikutnya, volume.
- **Keyboard & mouse saja**: kendalikan HP dengan keyboard dan mouse laptop tanpa menampilkan layar (UHID).

**Kenyamanan**
- **Mode privasi** (manual atau otomatis saat Mode TV/layar penuh): isi clipboard, notifikasi, dan judul lagu disamarkan.
- **Tema** Otomatis/Gelap/Terang dan **ukuran teks** Normal/Besar/Lebih besar.
- **Pembaruan otomatis** dari GitHub Releases, dengan jalur cadangan bila API GitHub menolak permintaan. Windows: pemasang dijalankan otomatis; AppImage diganti otomatis; macOS/Debian: dipandu.
- **Pintasan global**: `Ctrl+Alt+M` layar Android (memakai pengaturan terakhir, atau Cermin bila Layar baru tidak didukung), `Ctrl+Alt+K` keyboard & mouse saja.
- **Kirim ke HP** dari menu klik kanan **Kirim ke** di Windows Explorer, atau perintah `--send` di Linux/macOS; berkas antre bila HP belum tersambung.
- **Laporan masalah** sekali klik: zip berisi info versi, status, dan log dengan alamat IP dan nomor seri disamarkan.

## 1.8.0
**Aplikasi LinkDeck untuk Debian di HP (baru)**
- Paket baru `linkdeck-debian_<versi>_all.deb`: aplikasi LinkDeck tanpa biner per arsitektur, sehingga bisa dipasang di Debian 13 pada HP (arm64) maupun Debian/Ubuntu lain. adb, scrcpy, Chromium, dan pustaka Python diambil dari repositori Debian.
- Server scrcpy 4.1 dibundel: **Mode Game** dan **Clipboard bersama** langsung jalan apa pun versi scrcpy sistem.
- Perintah `linkdeck-scrcpy-build` membangun scrcpy versi yang sesuai langsung di HP, untuk **Layar baru**, **Cermin**, dan **Kamera** bila scrcpy bawaan Debian terlalu lama. Peringatan di aplikasi langsung menyebut perintah ini.
- Jalur baru **HP ini**: LinkDeck di Debian HP menyambung otomatis ke Android di HP yang sama (`127.0.0.1:5555`) dengan kualitas yang disesuaikan.
- Chromium dijalankan dengan opsi yang dibutuhkan proot (`--no-sandbox`).
- Workflow GitHub Actions ikut membangun dan merilis paket ini.

**Dokumentasi**
- README: tabel berkas mana untuk perangkat mana (termasuk penjelasan galat `libc6:amd64` di HP) dan bagian baru *Aplikasi LinkDeck di Debian HP (arm64)*.

## 1.7.0
**Perbaikan: salinan dari Debian tidak muncul di Clipboard bersama**
- Penyebab: agen hanya memantau clipboard di desktop LinkDeck (`:1`), padahal XFCE yang tampil di layar HP (mis. Termux:X11, `:0`) memakai clipboard X terpisah. Kini agen memantau dan mengisi clipboard di **semua** layar X Debian sekaligus, dan menyamakan salinan antar layar.
- Tombol **Uji** kini membaca balik clipboard Debian di setiap layar, jadi hasil "Debian ✓" benar-benar terbukti.
- Kartu Clipboard memberi tahu bila `xclip` belum terpasang di Debian, dan menampilkan layar X yang terpantau.

**Notifikasi panduan**
- Saat aplikasi dibuka, muncul notifikasi kaca kecil di tengah layar (latar hitam transparan 50%) berisi tautan panduan di GitHub. Muncul sekali setiap aplikasi dibuka, bisa ditutup, dan hilang sendiri setelah 15 detik. Tautan panduan juga ada di laci **Pengaturan**.

**Dokumentasi**
- README dilengkapi: cara membuka Opsi pengembang per merek HP, **Debugging USB (Setelan keamanan)** untuk Xiaomi/Redmi/POCO, cara memasang Debian 13 XFCE di HP lewat Termux + proot-distro, dua lokasi paket agen, cara menyalin di Debian, catatan audio Android 11, memperbarui/menghapus aplikasi, WebView2 di Windows 10, serta tautan unduhan ke halaman Releases.

## 1.6.0
**Perbaikan**
- Peringatan keliru *"scrcpy belum mendukung layar virtual"* di Windows. Versi scrcpy bawaan kini dibaca dari berkas versinya, tanpa menjalankan program (pemeriksaan lama bisa melewati batas waktu saat pertama kali dipindai antivirus). Ini juga memulihkan Layar baru, Mode Game, dan jembatan clipboard HP yang ikut bergantung pada versi itu.
- Bila versi scrcpy belum terbaca saat aplikasi dibuka, LinkDeck terus mencoba di latar (tanpa menahan jendela) dan menampilkan "Memeriksa versi scrcpy…", bukan peringatan keliru.
- Mode Game: `Esc` kini benar-benar dikirim sebagai tombol Kembali saat layar penuh (Keyboard Lock di WebView2/Chrome/Edge); tahan `Esc` untuk keluar dari layar penuh.
- Debian kini terdeteksi otomatis lewat Bluetooth dan hotspot: agen menyiarkan sinyalnya ke setiap jaringan HP, bukan hanya jalur utama (yang sering kali data seluler).

**Android lewat Bluetooth**
- Begitu adb di HP aktif (setelah **Siapkan Android lewat Bluetooth**), LinkDeck menemukan dan menyambung Android lewat Bluetooth secara otomatis setiap kali jaringan Bluetooth HP tersambung — Layar baru, Cermin, Kamera, dan Mode Game langsung bisa dipakai.
- LinkDeck membaca jaringan laptop (`ipconfig` berbahasa Inggris maupun Indonesia) untuk mengenali jaringan Bluetooth HP beserta IP-nya.
- Kartu Android menampilkan panduan saat belum tersambung, termasuk saat Bluetooth ke HP sudah tersambung tetapi adb belum aktif.
- Kamera lewat Bluetooth memakai 720p agar tetap lancar; angka kualitas Bluetooth di kartu kini sesuai pengaturan sebenarnya (0,8 Mbps).

**Debian**
- `linkdeck-start` menampilkan alamat HP per jaringan (Wi-Fi, Bluetooth, data seluler) agar tidak salah memakai alamat data seluler.
- IP Bluetooth di panel Debian terisi otomatis dari jaringan Bluetooth yang terdeteksi; pesan galat menyebut IP yang benar.

**Dokumentasi**
- README ditulis ulang: tutorial khusus Android (kabel, Wi-Fi, Bluetooth) untuk Layar baru, Cermin, Kamera, dan Mode Game; bagian Debian dipisah sebagai opsional; daftar pintasan dicocokkan dengan scrcpy 4.1.

## 1.5.0
**Mode Game (baru)**
- Main game Android di laptop dengan keyboard & mouse. Video game ditampilkan langsung di LinkDeck (WebCodecs H.264) dan layarnya dibuat **seukuran layar laptop**, jadi penuh tanpa bilah hitam.
- Pemetaan tombol: **joystick WASD** (atau panah), **tombol** keyboard → ketukan di titik mana pun, **klik kiri/kanan** sebagai tombol, dan **bidik mouse** (pointer lock) untuk game tembak-tembakan. Tombol yang tidak dipetakan dikirim sebagai ketikan Android; Esc = tombol Kembali.
- **Edit tombol**: seret tanda ke posisinya, klik lalu tekan tombol keyboard untuk mengganti, atur ukuran joystick dan kepekaan bidik, "Template dasar" sekali klik. Disimpan per game.
- Suara game tetap keluar di laptop.

**Layar penuh tanpa bilah hitam**
- Pilihan resolusi baru **Layar ini** (bawaan) untuk "Layar baru", jendela aplikasi, dan notifikasi: layar virtual Android dibuat seukuran layar laptop, sehingga layar penuh benar-benar penuh.

**Menyambungkan**
- Laci "Sambungkan perangkat" kini dipisah **Android** (adb) dan **Debian 13 XFCE** (agen LinkDeck), masing-masing dengan panduan Kabel / Wi-Fi / Bluetooth.
- Android **tanpa kabel**: pindai **kode QR** dari Debugging nirkabel (Android 11+), LinkDeck memasangkan dan menyambung otomatis. Cara kode 6 angka kini mendeteksi alamatnya sendiri dan langsung menyambung setelah dipasangkan.
- Android lewat **Bluetooth** tidak lagi wajib kabel: cukup tersambung sekali lewat Wi-Fi (kode QR).

## 1.4.0
**Clipboard bersama**
- Pemantau clipboard PC ditulis ulang. Windows memakai API Win32 langsung dan hanya membuka clipboard saat isinya berubah (GetClipboardSequenceNumber), jadi lebih andal dan tidak mengganggu aplikasi lain. macOS memakai NSPasteboard. Linux tetap memakai xclip/wl-clipboard.
- Pemantau tidak pernah berhenti lagi karena satu kesalahan; masalah ditampilkan langsung di kartu Clipboard.
- Tombol **Uji** di kartu Clipboard: menulis teks uji ke clipboard PC, membacanya kembali, lalu mengirimnya ke HP dan Debian, dan melaporkan hasilnya per perangkat.
- Pesan galat jembatan clipboard HP kini menyertakan keluaran dari HP, supaya penyebabnya terlihat.
- Baris baru dinormalkan antara Windows (CRLF), Android, dan Debian, sehingga teks yang sama tidak dianggap berbeda.

**Kamera**
- Senter, zoom, dan arah kamera kini langsung diterapkan saat kamera sedang tampil (kamera dibuka ulang ±1 detik). Sebelumnya hanya berlaku saat kamera pertama dibuka.
- Zoom tepat sampai 0,1× dengan rentang asli lensa HP (mis. 0,6×–10× untuk kamera belakang dengan ultra-wide), plus tombol −, 1×, +.
- Senter otomatis dinonaktifkan untuk kamera depan (tidak punya senter).

**Audio ke PC**
- Android 13+: suara HP **dipindah** ke PC dan HP jadi senyap, sehingga tidak bertabrakan. Opsi **Suara juga di HP** tersedia di Pengaturan lain bila ingin keduanya.
- Hanya satu jendela per HP yang mengambil suara; jendela berikutnya otomatis tanpa suara agar tidak dobel.
- Android di bawah 11 diberi tahu bahwa suara tidak bisa dikirim ke PC.

## 1.3.0
- **Clipboard Android selalu tersinkron**, tanpa perlu membuka jendela Android. LinkDeck menjalankan jembatan clipboard ringan di HP (scrcpy-server hanya kanal kontrol: tanpa video, audio, atau jendela). Salin di HP → langsung ada di PC dan Debian; salin di PC atau Debian → langsung ada di HP.
- Kartu Clipboard menampilkan status tiap perangkat (PC, setiap HP Android, Debian), lencana sumber **HP** beserta nama HP, dan sakelar **Android** untuk menyalakan/mematikan pemantauan clipboard HP.
- Perbaikan: gema clipboard — isi lama yang memantul balik dari Debian tidak lagi menimpa salinan terbaru.
- Sakelar bergaya terang kini terlihat jelas saat aktif.

## 1.2.1
- Perbaikan: kartu "Hubungkan desktop Debian" terpotong (tombol Hubungkan tidak terlihat) di layar laptop 1366×768 dan 1280×720. Panel kini memanjang sesuai isinya sebelum tersambung, lalu terkunci 16:9 setelah desktop tampil.
- Perbaikan: kolom isian di kartu sambung meluber keluar kartu.
- Perbaikan: label "Desktop/Terminal" terpotong; toolbar Debian kini muat dari lebar 1280 px ke atas.
- Bar atas selalu satu baris; tombol "Mulai tampilkan" lebar penuh; kolom sandi melebar saat PIN tidak diperlukan.
- Kontras kartu sambung dan kolom isian ditingkatkan; teks contoh (placeholder) dipersingkat agar tidak terpotong.

## 1.2.0
**Perbaikan bug**
- Layar desktop Debian tidak lagi membesar/mengecil sendiri: tinggi panel dikunci ke lebarnya (16:9), tidak ikut berubah saat isi kartu Android berubah.
- Perangkat yang putus sesaat (umum di Bluetooth) tetap ditampilkan 10 detik, jadi tampilan tidak berkedip dan melompat.
- "Ukuran jendela bebas" kini mati secara bawaan dan selalu mati di Bluetooth (bisa memicu jendela Android mengubah ukuran sendiri).
- "Ikuti ukuran panel" tidak lagi aktif otomatis; resolusi desktop diatur dari menu Lainnya.

**Lebih lancar**
- Bluetooth: video Android 800 kbps/720p/15 fps dengan penyangga 150 ms; desktop Debian JPEG kualitas rendah + kompresi maksimum; suara mu-law 16 kHz (~128 kbps, sebelumnya ~384 kbps).
- Wi-Fi: penyangga video 40 ms meredam patah-patah; kualitas desktop disetel per jalur.
- Notifikasi disaring di HP sebelum dikirim (dari ratusan KB jadi beberapa KB) dan dicek lebih jarang di Bluetooth.
- Pengecekan baterai/jeda adb jauh lebih jarang di Bluetooth.
- Gerakan "Satu mouse" digabung (maks 60 paket/detik, 30 di Bluetooth).
- Pilihan resolusi desktop Debian (1920×1080 sampai 1024×600) langsung dari LinkDeck.

**Tampilan**
- Toolbar Debian rapi satu baris; pengaturan jarang dipakai pindah ke menu Lainnya.
- Pengaturan Android yang jarang dipakai dilipat di "Pengaturan lain".
- Tombol utama lebih tegas, teks lebih kontras, latar sedikit lebih gelap.
- Pantauan pindah ke bawah panel Debian sehingga kedua kolom seimbang.

## 1.1.1
- Tombol satu klik **Siapkan Android lewat Bluetooth / Wi-Fi**: lewat kabel sekali, adb dipindah ke jaringan dan langsung tersambung, tanpa Command Prompt.
- Tombol **Lanjut tanpa kabel** di kartu Android saat HP tersambung kabel.
- HP yang sudah disiapkan disambung ulang otomatis selama belum di-restart.
- LinkDeck memberi tahu kalau laptop belum tergabung ke jaringan Bluetooth HP atau belum satu Wi-Fi.
- `linkdeck-start` tidak lagi menampilkan IP Bluetooth tebakan.

## 1.1.0
- Sambung otomatis: agen Debian terdeteksi lewat Wi-Fi, kabel, dan tethering Bluetooth; PIN dan sandi cukup sekali.
- Enkripsi TLS untuk semua jalur ke Debian dengan sertifikat yang dikunci; VNC di HP kini hanya lokal.
- Terminal Debian dan suara desktop Debian di LinkDeck.
- Satu mouse & keyboard lintas PC dan Debian (eksperimental).
- Folder sinkron dua arah `~/LinkDeck-Sinkron`.
- Android: ukuran jendela bebas, aplikasi HP di jendela sendiri, mode kamera/webcam, gamepad, `--keep-active`.
- Notifikasi HP tampil di PC dan bisa membuka aplikasinya.
- Mode TV satu klik, halaman pengaturan, daftar perangkat yang diingat.
- Perbaikan: pengecekan proses di `linkdeck-start`/`linkdeck-stop` tidak lagi salah mengenali proses lain.

## 1.0.0
- Rilis pertama: layar virtual Android, desktop Debian lewat VNC, clipboard, berkas, tautan, installer semua OS.
