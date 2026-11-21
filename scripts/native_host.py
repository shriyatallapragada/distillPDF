"""Chrome native messaging host for DistillPDF.

Reads one framed JSON request from stdin, runs the existing Python pipeline
locally, writes study-notes.pdf / study-notes.html to the user's Downloads
folder, and returns a small framed JSON reply with their paths. Keeping the
large HTML out of the reply stays under Chrome's 1 MB native-message limit.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import struct
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.clean import clean  # noqa: E402
from pipeline.common import load_config, write_json  # noqa: E402
from pipeline.enhance import enhance  # noqa: E402
from pipeline.render import render  # noqa: E402
from pipeline.validate import validate  # noqa: E402

HOST_NAME = "com.distillpdf.host"


def read_message() -> dict[str, Any] | None:
    header = sys.stdin.buffer.read(4)
    if not header:
        return None
    length = struct.unpack("<I", header)[0]
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = sys.stdin.buffer.read(remaining)
        if not chunk:
            raise EOFError("native host message ended early")
        chunks.append(chunk)
        remaining -= len(chunk)
    return json.loads(b"".join(chunks).decode("utf-8"))


_WRITE_LOCK = threading.Lock()
# main() pins the real stdout before the pipeline redirects print() to stderr.
# Tests leave it unset so they can supply their own stream.
MESSAGE_STREAM: Any = None


def write_message(payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    stream = MESSAGE_STREAM or sys.stdout.buffer
    with _WRITE_LOCK:
        stream.write(struct.pack("<I", len(data)) + data)
        stream.flush()


class _Heartbeat:
    """Send tiny progress frames so Chrome's MV3 worker stays awake.

    A large PDF can take longer than the service worker's idle timeout. Any
    message on the native port counts as activity, so a 10-second heartbeat
    keeps the port (and therefore the waiting promise) alive.
    """

    def __init__(self, interval: float = 10.0) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(interval,), daemon=True)

    def _run(self, interval: float) -> None:
        while not self._stop.wait(interval):
            try:
                write_message({"type": "progress", "message": "Still building…"})
            except Exception:
                return

    def __enter__(self) -> "_Heartbeat":
        self._thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=1)


def download_dir() -> Path:
    """Pick a writable output folder, preferring the browser's Downloads.

    A helper launched by Chrome can be denied access to ~/Downloads by macOS
    privacy settings. In that case the project's ``out/`` folder is used and
    the returned path tells the user where the files actually landed.
    """
    override = os.environ.get("NLMDF_DOWNLOAD_DIR")
    candidates = [Path(override).expanduser()] if override else []
    candidates.append(Path.home() / "Downloads")
    candidates.append(ROOT / "out")
    for target in candidates:
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".distillpdf-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return target
        except OSError:
            continue
    raise RuntimeError("No writable output folder; set NLMDF_DOWNLOAD_DIR.")


def unique_path(folder: Path, name: str) -> Path:
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    for number in range(1, 1000):
        candidate = folder / f"{stem} ({number}){suffix}"
        if not candidate.exists():
            return candidate
    return folder / f"{stem}-new{suffix}"


def build(chat: dict[str, Any]) -> dict[str, Any]:
    """Run the four stages and copy the two finished files to Downloads."""
    if not isinstance(chat, dict) or not chat.get("turns"):
        return {"ok": False, "error": "No answers were selected."}

    config = load_config()
    config["title"] = str(chat.get("title") or "Study notes")
    destination = download_dir()

    with tempfile.TemporaryDirectory(prefix="distillpdf-") as work:
        root = Path(work)
        chat_file = root / "chat.json"
        write_json(chat_file, chat)

        # Pipeline helpers print progress; native messaging stdout must stay
        # clean, so route all chatter to stderr.
        with contextlib.redirect_stdout(sys.stderr):
            manifest = clean(chat_file, root / "clean.md", config=config)
            enhance(
                root / "clean.md",
                root / "enhanced.md",
                root / "clean.meta.json",
                config,
            )
            render(root / "enhanced.md", root / "study-notes.pdf", config=config)
            try:
                report = validate(
                    root / "study-notes.pdf",
                    root / "study-notes.html",
                    root / "enhanced.md",
                    root / "clean.meta.json",
                    config=config,
                )
            except Exception as exc:  # never block the files because of a check
                report = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}

        html_source = root / "study-notes.html"
        pdf_source = root / "study-notes.pdf"
        if not html_source.exists() or not pdf_source.exists():
            return {"ok": False, "error": "The renderer did not produce both files."}

        html_out = unique_path(destination, "study-notes.html")
        pdf_out = unique_path(destination, "study-notes.pdf")
        html_out.write_bytes(html_source.read_bytes())
        pdf_out.write_bytes(pdf_source.read_bytes())

        return {
            "ok": True,
            "html": str(html_out),
            "pdf": str(pdf_out),
            "answers": len(manifest["answers"]),
            "passed": bool(report.get("passed", False)),
            "checks": [
                {"name": check["name"], "status": check["status"]}
                for check in report.get("checks", [])
            ],
            "model": config.get("model"),
        }


def main() -> int:
    global MESSAGE_STREAM
    MESSAGE_STREAM = sys.stdout.buffer
    try:
        message = read_message()
        if message is None:
            return 0
        # Heartbeats keep Chrome's MV3 service worker from timing out while a
        # large document is rendered. The background script ignores the
        # progress frames but stays alive because the port sees activity.
        with _Heartbeat():
            response = build(message.get("chat") or {}) if message.get("type") == "build" else {
                "ok": False,
                "error": "Unknown request type.",
            }
    except Exception as exc:
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    write_message(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
