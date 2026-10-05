"""Penulis paket .deb murni Python (tanpa dpkg-deb), supaya bisa dibangun di Windows/macOS/Linux."""
from __future__ import annotations

import io
import tarfile
import time
from pathlib import Path


def _tar(entries: list[tuple[str, bytes | None, int, str | None]]) -> bytes:
    """entries: (path, data|None untuk direktori, mode, target symlink|None)"""
    buf = io.BytesIO()
    now = int(time.time())
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tf:
        seen = set()
        for path, data, mode, link in entries:
            parts = Path(path).parts
            for i in range(1, len(parts)):            # direktori induk lebih dulu
                d = "./" + "/".join(parts[:i])
                if d not in seen:
                    seen.add(d)
                    ti = tarfile.TarInfo(d)
                    ti.type, ti.mode, ti.mtime = tarfile.DIRTYPE, 0o755, now
                    ti.uname = ti.gname = "root"
                    tf.addfile(ti)
            ti = tarfile.TarInfo("./" + path)
            ti.mtime, ti.uname, ti.gname = now, "root", "root"
            if link is not None:
                ti.type, ti.linkname, ti.mode = tarfile.SYMTYPE, link, 0o777
                tf.addfile(ti)
            else:
                ti.size, ti.mode = len(data or b""), mode
                tf.addfile(ti, io.BytesIO(data or b""))
    return buf.getvalue()


def _ar_member(name: str, data: bytes) -> bytes:
    head = (f"{name:<16}{int(time.time()):<12}{0:<6}{0:<6}{0o100644:<8o}{len(data):<10}`\n").encode()
    assert len(head) == 60
    return head + data + (b"\n" if len(data) % 2 else b"")


def build_deb(out: Path, control: dict[str, str], files: list[tuple[str, bytes | None, int, str | None]],
              conffiles: list[str] | None = None, postinst: str | None = None) -> Path:
    ctrl = "".join(f"{k}: {v}\n" for k, v in control.items() if v)
    size_kb = sum(len(d or b"") for _, d, _, _ in files) // 1024 + 1
    ctrl = ctrl.replace("Installed-Size: auto", f"Installed-Size: {size_kb}")
    centries = [("control", ctrl.encode(), 0o644, None)]
    if conffiles:
        centries.append(("conffiles", "".join(c + "\n" for c in conffiles).encode(), 0o644, None))
    if postinst:
        centries.append(("postinst", postinst.encode(), 0o755, None))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"!<arch>\n" + _ar_member("debian-binary", b"2.0\n")
                    + _ar_member("control.tar.gz", _tar(centries))
                    + _ar_member("data.tar.gz", _tar(files)))
    return out
