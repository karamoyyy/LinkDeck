#!/usr/bin/env bash
# Linux / macOS: siapkan venv sekali, lalu jalankan LinkDeck
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
exec python app.py "$@"
