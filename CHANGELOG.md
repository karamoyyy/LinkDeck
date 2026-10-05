# Riwayat perubahan

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
