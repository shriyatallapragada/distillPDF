"""Build ready-to-unzip packages for the extension and the mobile capture page."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "extension"
OUTPUT = ROOT / "dist" / "DistillPDF-extension.zip"
MOBILE_PAGE = ROOT / "mobile" / "capture.html"
MOBILE_OUTPUT = ROOT / "dist" / "DistillPDF-mobile-capture.zip"
TOP = "DistillPDF-extension"
SKIP_DIRS = {"test", "scripts", "__pycache__", ".pytest_cache"}
SKIP_NAMES = {".DS_Store"}

INSTALL = """DistillPDF — NotebookLM PDF + HTML exporter

Before loading the extension, run install.sh (or install.bat on Windows) in the
DistillPDF project once. That installs the local helper which builds the PDF.

1. In the project, run: ./install.sh   (Windows: install.bat)
2. In Chrome, open chrome://extensions.
3. Turn on Developer mode (top right).
4. Click Load unpacked and select this DistillPDF-extension folder.
5. Open a NotebookLM chat, tick the answers you want, then click Build PDF + HTML.
6. study-notes.pdf and study-notes.html appear in your Downloads folder.

Desktop Chrome only. On a phone, use DistillPDF-mobile-capture.zip instead.
No sign-in, no network calls. Everything is rendered on your own computer.
"""

MOBILE_INSTALL = """DistillPDF — mobile capture page

Chrome on Android and iOS cannot install extensions, so use this page instead.

1. Unzip this file on your phone.
2. Open capture.html in any mobile browser (it works offline).
3. Paste each NotebookLM answer, then tap Download chat.json.
4. Move chat.json to a computer running DistillPDF and run:
   nlm-pdf all chat.json --outdir out

Your notes stay in the browser's local storage until you clear them.
"""


def build_extension() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        archive.writestr(f"{TOP}/INSTALL.txt", INSTALL)
        for path in sorted(SOURCE.rglob("*")):
            relative = path.relative_to(SOURCE)
            if path.is_dir() or path.name in SKIP_NAMES:
                continue
            if any(part in SKIP_DIRS for part in relative.parts[:-1]):
                continue
            archive.write(path, f"{TOP}/{relative.as_posix()}")
    with ZipFile(OUTPUT) as archive:
        count = sum(not name.endswith("/") for name in archive.namelist())
    print(f"packaged {count} files -> {OUTPUT.relative_to(ROOT)}")
    return count


def build_mobile() -> int:
    MOBILE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(MOBILE_OUTPUT, "w", ZIP_DEFLATED) as archive:
        archive.writestr("INSTALL.txt", MOBILE_INSTALL)
        archive.write(MOBILE_PAGE, "capture.html")
    print(f"packaged mobile capture -> {MOBILE_OUTPUT.relative_to(ROOT)}")
    return 2


def main() -> None:
    build_extension()
    build_mobile()


if __name__ == "__main__":
    main()
