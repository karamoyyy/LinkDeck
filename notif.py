"""
Notifikasi Android -> PC, tanpa aplikasi pendamping.

Membaca `adb shell dumpsys notification --noredact` dan mengambil judul & teks notifikasi aktif.
Format dumpsys sedikit berbeda antar versi Android, jadi parser ini sengaja longgar.
"""
from __future__ import annotations

import hashlib
import re

REC = re.compile(r"^(\s*)NotificationRecord\(0x[0-9a-fA-F]+: pkg=(\S+).*?key=([^\s:]+)")
FLAGS = re.compile(r"\bflags=0x([0-9a-fA-F]+)")
EXTRA = re.compile(r"^\s*android\.(title|text|bigText|subText)=(.*)$")
WRAP = re.compile(r"^(?:String|SpannableString|SpannedString|SpannableStringBuilder)\s*\((.*)\)\s*$", re.S)
SKIP_PKGS = {"android", "com.android.systemui", "com.android.shell", "com.android.providers.downloads"}
FLAG_ONGOING, FLAG_FOREGROUND, FLAG_GROUP_SUMMARY = 0x2, 0x40, 0x200


def _clean(v: str) -> str:
    v = v.strip()
    m = WRAP.match(v)
    if m:
        v = m.group(1)
    return "" if v in ("null", "") else v


def parse(dump: str) -> list[dict]:
    lines = dump.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == "Notification List:"), None)
    if start is None:
        return []
    base = len(lines[start]) - len(lines[start].lstrip())
    out: list[dict] = []
    cur = None
    for line in lines[start + 1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= base:
            break   # bagian lain dumpsys dimulai
        m = REC.match(line)
        if m:
            cur = {"pkg": m.group(2), "key": m.group(3), "title": "", "text": "", "flags": 0}
            f = FLAGS.search(line[line.find("Notification("):] if "Notification(" in line else "")
            if f:
                cur["flags"] = int(f.group(1), 16)
            out.append(cur)
            continue
        if cur is None:
            continue
        e = EXTRA.match(line)
        if e:
            k, v = e.group(1), _clean(e.group(2))
            if k == "title" and v:
                cur["title"] = v
            elif k in ("text", "bigText") and v and (k == "bigText" or not cur["text"]):
                cur["text"] = v
    result = []
    for n in out:
        if n["pkg"] in SKIP_PKGS or n["flags"] & (FLAG_ONGOING | FLAG_FOREGROUND | FLAG_GROUP_SUMMARY):
            continue
        if not (n["title"] or n["text"]):
            continue
        n["id"] = hashlib.sha1(f"{n['key']}|{n['title']}|{n['text']}".encode()).hexdigest()[:12]
        result.append(n)
    return result


def parse_apps(listing: str) -> list[dict]:
    """Parse keluaran `scrcpy --list-apps` (baris berisi label lalu nama paket di akhir)."""
    apps = []
    for line in listing.splitlines():
        s = line.strip()
        if not s or not s[0] in "*-":
            continue
        parts = s[1:].strip().rsplit(None, 1)
        if len(parts) == 2 and re.match(r"^[a-zA-Z][\w]*(\.[\w]+)+$", parts[1]):
            apps.append({"label": parts[0].strip(), "pkg": parts[1], "system": s[0] == "*"})
    return sorted(apps, key=lambda a: (a["system"], a["label"].lower()))
