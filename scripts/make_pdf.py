"""One-click bridge from a downloaded chat.json to an opened study-notes.pdf.

Used by make-pdf.command (macOS), make-pdf.bat (Windows) and make-pdf.sh
(Linux). You can also drag chat.json onto any of those launchers.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> Path:
    names = (
        ("Scripts", "python.exe")
        if os.name == "nt"
        else ("bin", "python")
    )
    return ROOT / ".venv" / names[0] / names[1]


def ensure_environment() -> Path:
    python = venv_python()
    if python.exists():
        return python
    print("First run: setting up the local environment…")
    installer = "install.bat" if os.name == "nt" else "install.sh"
    subprocess.run([str(ROOT / installer)], cwd=ROOT, check=True)
    if not python.exists():
        raise RuntimeError(f"Setup finished but {python} is missing")
    return python


def find_chat(explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser()
        return candidate if candidate.is_file() else None

    downloads = Path.home() / "Downloads"
    folders = [ROOT, downloads]
    for folder in folders:
        direct = folder / "chat.json"
        if direct.is_file():
            return direct
    if downloads.is_dir():
        recent = sorted(
            downloads.glob("chat*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if recent:
            return recent[0]
    return None


def open_pdf(pdf: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(pdf)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(pdf)], check=False)
        else:
            subprocess.run(["xdg-open", str(pdf)], check=False)
    except Exception:
        webbrowser.open(pdf.resolve().as_uri())


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    chat = find_chat(args[0] if args else None)
    if chat is None:
        print("Could not find chat.json.")
        print("Download it from the DistillPDF extension, or drag it onto this launcher.")
        return 1

    chat = chat.resolve()
    outdir = chat.parent / "out"
    print(f"Using: {chat}")
    python = ensure_environment()
    result = subprocess.run(
        [
            str(python),
            "-m",
            "pipeline.cli",
            "all",
            str(chat),
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("\nThe pipeline reported a problem. Check report.json in:")
        print(f"  {outdir}")
        return result.returncode

    pdf = outdir / "study-notes.pdf"
    if not pdf.exists():
        print(f"Expected {pdf} but it was not created.")
        return 1
    print(f"\nYour PDF is ready:\n  {pdf}")
    open_pdf(pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
