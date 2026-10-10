"""
Bangun APK "LinkDeck Pendamping" (companion/) tanpa Android Studio / Gradle.

Alat yang dipakai (Debian/Ubuntu):
    sudo apt install aapt apksigner zipalign dalvik-exchange android-sdk-platform-23 default-jdk-headless

Hasil: companion/linkdeck-companion.apk (diabaikan git; ikut dibundel ke aplikasi oleh linkdeck.spec).

Tanda tangan APK:
  * LINKDECK_COMPANION_KEYSTORE (+ LINKDECK_COMPANION_KS_PASS, LINKDECK_COMPANION_KS_ALIAS) bila diisi;
  * selain itu kunci lokal ~/.cache/linkdeck/companion.jks dibuat otomatis sekali.
  Kunci tidak pernah disimpan di repo. Bila tanda tangan berubah antar versi, LinkDeck otomatis
  mencopot versi lama lalu memasang yang baru (akses notifikasi dinyalakan lagi otomatis).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "companion"
OUT = SRC / "linkdeck-companion.apk"
ANDROID_JAR_CANDIDATES = [
    os.environ.get("ANDROID_JAR", ""),
    "/usr/lib/android-sdk/platforms/android-23/android.jar",
    "/usr/share/java/com.android.android-23.jar",
]
MIN_SDK, TARGET_SDK = 23, 34
ICON_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def tool(name: str, *alts: str) -> str:
    for n in (name, *alts):
        p = shutil.which(n)
        if p:
            return p
    sys.exit(f"Alat '{name}' tidak ditemukan. Pasang: sudo apt install aapt apksigner zipalign "
             f"dalvik-exchange android-sdk-platform-23 default-jdk-headless")


def run(*cmd, **kw) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def version() -> tuple[str, int]:
    v = (os.environ.get("LINKDECK_VERSION") or (ROOT / "VERSION").read_text()).strip()
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if not m:
        sys.exit(f"Versi tidak dikenali: {v}")
    a, b, c = (int(x) for x in m.groups())
    return v, a * 10000 + b * 100 + c


def make_icons(res: Path) -> None:
    """Ikon peluncur: logo LinkDeck di atas kotak membulat gelap (digambar, tanpa berkas gambar di repo)."""
    from PIL import Image, ImageDraw
    for dpi, size in ICON_SIZES.items():
        s = size / 48
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([2 * s, 2 * s, 46 * s, 46 * s], radius=11 * s, fill=(29, 32, 48, 255))
        d.rounded_rectangle([8 * s, 13 * s, 32 * s, 31 * s], radius=5 * s, fill=(236, 198, 245, 255))
        d.rounded_rectangle([26 * s, 19 * s, 40 * s, 40 * s], radius=4.5 * s, fill=(191, 230, 248, 255),
                            outline=(29, 32, 48, 255), width=max(1, round(2.4 * s)))
        out = res / f"drawable-{dpi}"
        out.mkdir(parents=True, exist_ok=True)
        im.save(out / "ic_launcher.png", optimize=True)


def keystore(work: Path, keytool: str) -> tuple[Path, str, str]:
    ks = os.environ.get("LINKDECK_COMPANION_KEYSTORE")
    if ks:
        return (Path(ks), os.environ.get("LINKDECK_COMPANION_KS_PASS", ""),
                os.environ.get("LINKDECK_COMPANION_KS_ALIAS", "linkdeck"))
    path = Path.home() / ".cache" / "linkdeck" / "companion.jks"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        run(keytool, "-genkeypair", "-keystore", path, "-storepass", "linkdeck", "-keypass", "linkdeck",
            "-alias", "linkdeck", "-keyalg", "RSA", "-keysize", "3072", "-validity", "10000",
            "-dname", "CN=LinkDeck Companion, O=LinkDeck", "-noprompt", stdout=subprocess.DEVNULL)
    return path, "linkdeck", "linkdeck"


def main() -> None:
    android_jar = next((Path(p) for p in ANDROID_JAR_CANDIDATES if p and Path(p).exists()), None)
    if not android_jar:
        sys.exit("android.jar API 23 tidak ditemukan (sudo apt install android-sdk-platform-23 atau isi ANDROID_JAR).")
    aapt2, javac, dx = tool("aapt2"), tool("javac"), tool("dalvik-exchange", "dx")
    zipalign, apksigner, keytool = tool("zipalign"), tool("apksigner"), tool("keytool")
    ver, code = version()

    with tempfile.TemporaryDirectory(prefix="linkdeck-companion-") as tmp:
        work = Path(tmp)
        res = work / "res"
        shutil.copytree(SRC / "res", res)
        make_icons(res)
        gen, classes = work / "gen", work / "classes"
        pkgdir = gen / "id" / "linkdeck" / "companion"
        pkgdir.mkdir(parents=True)
        classes.mkdir()
        (pkgdir / "BuildInfo.java").write_text(
            "package id.linkdeck.companion;\n\n/** Dibuat otomatis oleh build_companion.py. */\n"
            f"final class BuildInfo {{\n    static final String VERSION = \"{ver}\";\n"
            "    private BuildInfo() { }\n}\n", encoding="utf-8")

        compiled = work / "res.zip"
        run(aapt2, "compile", "--dir", res, "-o", compiled)
        base = work / "base.apk"
        run(aapt2, "link", "-I", android_jar, "--manifest", SRC / "AndroidManifest.xml",
            "--min-sdk-version", MIN_SDK, "--target-sdk-version", TARGET_SDK,
            "--version-code", code, "--version-name", ver, "--java", gen, "--auto-add-overlay",
            "-o", base, compiled)

        sources = sorted(str(p) for p in (SRC / "src").rglob("*.java")) + sorted(str(p) for p in gen.rglob("*.java"))
        run(javac, "--release", "8", "-encoding", "UTF-8", "-Xlint:-options", "-classpath", android_jar,
            "-d", classes, *sources)
        dex = work / "classes.dex"
        run(dx, "--dex", f"--min-sdk-version={MIN_SDK}", f"--output={dex}", classes)

        unaligned = work / "unaligned.apk"
        shutil.copy(base, unaligned)
        with zipfile.ZipFile(unaligned, "a", zipfile.ZIP_DEFLATED) as z:
            z.write(dex, "classes.dex")
        aligned = work / "aligned.apk"
        run(zipalign, "-p", "-f", "4", unaligned, aligned)

        ks, pw, alias = keystore(work, keytool)
        signed = work / "signed.apk"
        run(apksigner, "sign", "--ks", ks, "--ks-pass", f"pass:{pw}", "--ks-key-alias", alias,
            "--key-pass", f"pass:{pw}", "--min-sdk-version", MIN_SDK, "--out", signed, aligned)
        run(apksigner, "verify", "--min-sdk-version", MIN_SDK, signed)
        shutil.copy(signed, OUT)
    print(f"APK pendamping {ver} ({code}): {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
