@echo off
rem Terbitkan LinkDeck ke GitHub dengan satu klik (Windows): klik dua kali file ini.
setlocal
cd /d "%~dp0"
echo.
echo === Terbitkan LinkDeck ke GitHub ===

where git >nul 2>nul
if errorlevel 1 (
  echo Git belum terpasang. Mencoba memasang lewat winget...
  winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
  echo Tutup jendela ini, lalu klik dua kali terbitkan.bat sekali lagi.
  pause
  exit /b 0
)
where gh >nul 2>nul
if errorlevel 1 (
  echo GitHub CLI belum terpasang. Mencoba memasang lewat winget...
  winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements
  echo Tutup jendela ini, lalu klik dua kali terbitkan.bat sekali lagi.
  pause
  exit /b 0
)

echo.
echo [1/4] Masuk ke akun GitHub
gh auth status >nul 2>nul
if errorlevel 1 (
  echo Browser akan terbuka. Salin kode yang muncul di sini, tempel di browser, lalu setujui.
  gh auth login --hostname github.com --git-protocol https --web --scopes workflow
  if errorlevel 1 goto gagal
) else (
  gh auth status 2>&1 | findstr /i "workflow" >nul
  if errorlevel 1 (
    echo Perlu izin tambahan 'workflow' agar file build otomatis bisa diunggah.
    gh auth refresh --hostname github.com --scopes workflow
    if errorlevel 1 goto gagal
  )
)
gh auth setup-git

echo.
echo [2/4] Membuat repo dan mengunggah kode
git remote get-url origin >nul 2>nul
if not errorlevel 1 (
  git push -u origin main
  if errorlevel 1 goto gagal
  goto tags
)
set "NAMA=linkdeck"
set /p "NAMA=Nama repo [linkdeck]: "
gh repo view "%NAMA%" >nul 2>nul
if not errorlevel 1 (
  echo Repo %NAMA% sudah ada di akunmu ^(versi sebelumnya^). Memperbarui...
  for /f "delims=" %%u in ('gh repo view "%NAMA%" --json url -q .url') do git remote add origin "%%u.git"
  git push -u origin main
  if errorlevel 1 goto gagal
  goto tags
)
set "PUB=Y"
set /p "PUB=Jadikan publik? Publik = build gratis tanpa batas (Y/n): "
set "VIS=--public"
if /i "%PUB%"=="n" set "VIS=--private"
gh repo create "%NAMA%" %VIS% --source=. --remote=origin --push --description "Sambungkan layar HP (Android + Debian XFCE) ke PC, monitor, atau TV"
if errorlevel 1 goto gagal

:tags
echo.
echo [3/4] Memicu pembuatan installer
set /p VER=<VERSION
git push origin v%VER%
if errorlevel 1 goto gagal

for /f "delims=" %%u in ('gh repo view --json url -q .url') do set "URL=%%u"
echo.
echo [4/4] Selesai
echo Repo         : %URL%
echo Proses build : %URL%/actions   (sekitar 10-15 menit)
echo Installer    : %URL%/releases
start "" "%URL%/actions"
pause
exit /b 0

:gagal
echo.
echo Gagal. Baca pesan di atas, perbaiki, lalu jalankan terbitkan.bat lagi.
pause
exit /b 1
