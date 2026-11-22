"""Tests for the Chrome native messaging bridge (scripts/native_host.py)."""

from __future__ import annotations

import importlib.util
import io
import json
import struct
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_FILE = ROOT / "scripts" / "native_host.py"


def load_host():
    spec = importlib.util.spec_from_file_location("native_host_under_test", HOST_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_framed_messages_round_trip(monkeypatch):
    host = load_host()
    payload = {"type": "build", "chat": {"turns": [{"markdown": "héllo"}]}}
    data = json.dumps(payload).encode("utf-8")
    framed = struct.pack("<I", len(data)) + data
    stdin = types.SimpleNamespace(buffer=io.BytesIO(framed))
    stdout = types.SimpleNamespace(buffer=io.BytesIO())
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)

    assert host.read_message() == payload
    host.write_message({"ok": True, "pdf": "a.pdf"})
    raw = stdout.buffer.getvalue()
    size = struct.unpack("<I", raw[:4])[0]
    assert json.loads(raw[4 : 4 + size].decode("utf-8")) == {"ok": True, "pdf": "a.pdf"}


def test_unique_path_avoids_overwriting(monkeypatch, tmp_path):
    host = load_host()
    first = host.unique_path(tmp_path, "study-notes.pdf")
    first.write_text("first")
    second = host.unique_path(tmp_path, "study-notes.pdf")
    assert second.name == "study-notes (1).pdf"
    second.write_text("second")
    assert host.unique_path(tmp_path, "study-notes.pdf").name == "study-notes (2).pdf"


def test_math_capture_warning_is_surfaced():
    host = load_host()
    assert host._math_capture_check({"turns": [{"markdown": "plain prose"}]}) is None
    check = host._math_capture_check({
        "turns": [{"markdown": "plain prose", "math_warnings": ["garbled math"]}]
    })
    assert check is not None
    assert check["name"] == "math_capture"
    assert check["status"] == "fail"
    assert check["expected"] == 0
    assert check["actual"] == 1
    assert "garbled math" in check["detail"]


def test_installer_prepares_runtime_with_venv_python(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "installer_under_test", ROOT / "scripts" / "install_native_host.py"
    )
    assert spec and spec.loader
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    monkeypatch.setattr(installer, "runtime_dir", lambda: tmp_path)

    executable = installer.prepare_runtime()
    assert executable.is_file()
    assert (tmp_path / "native_host.py").exists()
    assert (tmp_path / "pipeline" / "common.py").exists()
    assert (tmp_path / "templates").is_dir()
    wrapper = executable.read_text(encoding="utf-8")
    # The venv python must stay a symlink path: resolving it would bypass
    # pyvenv.cfg and lose all installed packages.
    assert ".venv/bin/python" in wrapper or ".venv\\Scripts\\python.exe" in wrapper
    assert "/opt/homebrew" not in wrapper

    manifest = installer.manifest(executable)
    assert manifest["path"] == str(executable)
    assert manifest["allowed_origins"] == [
        "chrome-extension://iijffgjddbjkelolocfppjhindfkabfd/"
    ]


def test_build_writes_pdf_and_html_directly(monkeypatch, tmp_path):
    """The helper produces both files without ever handing chat.json back."""
    host = load_host()
    monkeypatch.setenv("NLMDF_DOWNLOAD_DIR", str(tmp_path))
    chat = {
        "title": "Helper check",
        "source": "test",
        "turns": [
            {
                "role": "assistant",
                "markdown": "## Local build\n\nThis note was rendered by the native helper.",
            }
        ],
    }
    response = host.build(chat)
    assert response["ok"] is True, response
    assert response["answers"] == 1
    pdf = Path(response["pdf"])
    html = Path(response["html"])
    assert pdf.exists() and pdf.stat().st_size > 1000
    assert html.exists() and html.stat().st_size > 1000
    assert "study-notes.pdf" == pdf.name or pdf.name.startswith("study-notes (")
    assert "study-notes.html" == html.name or html.name.startswith("study-notes (")
    assert "Local build" in html.read_text(encoding="utf-8")
    assert all(check["name"] != "math_capture" for check in response["checks"])
