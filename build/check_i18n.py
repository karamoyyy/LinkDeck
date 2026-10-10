"""
Cek terjemahan Inggris UI LinkDeck (alat pengembang).

Menjalankan server LinkDeck sementara (data di folder sementara, bahasa = en), membuka UI di Chromium
lewat Playwright, lalu mencantumkan teks dan atribut yang masih terlihat berbahasa Indonesia.
Tambahkan terjemahannya di static/i18n/en.js.

    pip install playwright && python -m playwright install chromium
    python build/check_i18n.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN = r"""
() => {
  const ID = /\b(yang|dan|di|ke|tidak|untuk|dengan|belum|sudah|dari|lewat|dulu|ini|itu|tersambung|Pasang|Buka|Tutup|Kirim|Sambungkan|terpasang|lalu|atau|bisa|Coba|Klik|ketuk|Ketuk|Tidak|Belum|Sudah|layar|Layar|berkas|Berkas|Hapus|Simpan|Mulai|Aktif|Nyalakan|Matikan|Pilih|Tampilkan|Salin|Tempel|Cari|Batal|Kembali|Lanjut|Keluar|Ukuran|Tombol|tombol|Suara|suara|Kamera|Pengaturan|Bantuan|Panduan|panduan)\b/;
  const out = new Set();
  const skip = el => el.closest('[translate="no"],#term,.xterm,script,style,svg');
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while((n = w.nextNode())){ if(skip(n.parentElement)) continue; const t = n.data.replace(/\s+/g,' ').trim(); if(t && ID.test(t)) out.add('teks   | ' + t); }
  for(const el of document.querySelectorAll('[title],[placeholder],[aria-label],[alt]')){
    if(skip(el)) continue;
    for(const a of ['title','placeholder','aria-label','alt']){ const v = el.getAttribute(a); if(v && ID.test(v)) out.add('atribut| ' + v); }
  }
  return [...out];
}
"""

# nama yang memang tidak diterjemahkan (nama perangkat/berkas sungguhan)
ALLOWED = ("Mikrofon HP (LinkDeck)", "LinkDeck (HP Android)")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Butuh Playwright: pip install playwright && python -m playwright install chromium")
        return 2
    port = free_port()
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "LinkDeck"
        data.mkdir()
        (data / "settings.json").write_text(json.dumps({"lang": "en", "onboarded": False}))
        env = {**os.environ, "LINKDECK_PORT": str(port), "XDG_DATA_HOME": tmp, "LOCALAPPDATA": tmp,
               "LINKDECK_SAVE_DIR": str(Path(tmp) / "dl"), "LINKDECK_SYNC_DIR": str(Path(tmp) / "sync")}
        if sys.platform == "darwin":
            env["HOME"] = tmp
            (Path(tmp) / "Library" / "Application Support" / "LinkDeck").mkdir(parents=True)
            (Path(tmp) / "Library" / "Application Support" / "LinkDeck" / "settings.json").write_text(
                json.dumps({"lang": "en", "onboarded": False}))
        srv = subprocess.Popen([sys.executable, str(ROOT / "server.py")], env=env, cwd=ROOT,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    socket.create_connection(("127.0.0.1", port), 0.5).close()
                    break
                except OSError:
                    time.sleep(0.25)
            left: set[str] = set()
            with sync_playwright() as p:
                b = p.chromium.launch()
                pg = b.new_page(viewport={"width": 1366, "height": 768})
                pg.goto(f"http://127.0.0.1:{port}/")
                pg.wait_for_timeout(3500)
                left |= set(pg.evaluate(SCAN))
                for _ in range(5):                       # semua langkah panduan awal
                    if pg.locator("#wizard").is_hidden():
                        break
                    pg.click("#wizNext")
                    pg.wait_for_timeout(400)
                    left |= set(pg.evaluate(SCAN))
                b.close()
        finally:
            srv.terminate()
            srv.wait(10)
    left = {x for x in left if not any(a in x for a in ALLOWED)}
    for x in sorted(left):
        print(x)
    print(f"\n{len(left)} teks belum diterjemahkan." if left else "Semua teks yang terlihat sudah berbahasa Inggris.")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
