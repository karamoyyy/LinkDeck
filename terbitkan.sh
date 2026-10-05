#!/usr/bin/env bash
# Terbitkan LinkDeck ke GitHub dengan satu perintah (Linux/macOS):  bash terbitkan.sh
# Membuat repo di akunmu, mengunggah kode, lalu memicu pembuatan semua installer.
set -e
cd "$(dirname "$0")"
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

command -v git >/dev/null || { echo "Git belum terpasang. Debian/Ubuntu: sudo apt install git   macOS: xcode-select --install"; exit 1; }
if ! command -v gh >/dev/null; then
  echo "GitHub CLI (gh) belum terpasang. Pasang dulu, lalu jalankan lagi:"
  case "$(uname)" in
    Darwin) echo "  brew install gh" ;;
    *)      echo "  sudo apt install gh      (atau petunjuk lain di https://cli.github.com)" ;;
  esac
  exit 1
fi

say "1/4  Masuk ke akun GitHub"
if ! gh auth status >/dev/null 2>&1; then
  echo "Browser akan terbuka. Salin kode yang muncul di sini, tempel di browser, lalu setujui."
  gh auth login --hostname github.com --git-protocol https --web --scopes workflow
elif ! gh auth status 2>&1 | grep -q "workflow"; then
  echo "Perlu izin tambahan 'workflow' agar file build otomatis bisa diunggah."
  gh auth refresh --hostname github.com --scopes workflow
fi
gh auth setup-git

say "2/4  Membuat repo dan mengunggah kode"
if git remote get-url origin >/dev/null 2>&1; then
  echo "Repo sudah terhubung ke $(git remote get-url origin), lanjut unggah."
  git push -u origin main
else
  read -rp "Nama repo [linkdeck]: " NAMA; NAMA=${NAMA:-linkdeck}
  if gh repo view "$NAMA" >/dev/null 2>&1; then
    echo "Repo $NAMA sudah ada di akunmu (versi sebelumnya). Memperbarui..."
    git remote add origin "$(gh repo view "$NAMA" --json url -q .url).git"
    git push -u origin main
  else
    read -rp "Jadikan publik? Publik = build gratis tanpa batas (Y/n): " PUB
    case "$PUB" in n|N) VIS=--private ;; *) VIS=--public ;; esac
    gh repo create "$NAMA" "$VIS" --source=. --remote=origin --push \
      --description "Sambungkan layar HP (Android + Debian XFCE) ke PC, monitor, atau TV"
  fi
fi

say "3/4  Memicu pembuatan installer"
git push origin "v$(cat VERSION)"

URL=$(gh repo view --json url -q .url)
say "4/4  Selesai"
echo "Repo         : $URL"
echo "Proses build : $URL/actions   (sekitar 10-15 menit)"
echo "Installer    : $URL/releases"
(command -v xdg-open >/dev/null && xdg-open "$URL/actions" >/dev/null 2>&1) || \
(command -v open >/dev/null && open "$URL/actions" >/dev/null 2>&1) || true
