"""Register the DistillPDF native messaging host for Chrome/Chromium/Edge.

This is called by install.sh / install.ps1, but can also be run on its own:

    python3 scripts/install_native_host.py

Chrome only talks to local helpers that are explicitly registered. The
registration is a small JSON file containing the absolute path of our wrapper
and the fixed extension ID from extension/manifest.json. No network, no admin
rights, no changes outside the browser's own config folder (plus one registry
key on Windows).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOST = "com.distillpdf.host"
EXTENSION_ID = "iijffgjddbjkelolocfppjhindfkabfd"


def runtime_dir() -> Path:
    """A location Chrome's helper is always allowed to read.

    On macOS, apps are denied access to ~/Documents by default. Keeping the
    helper source there makes Chrome report "Operation not permitted" even
    though the same files work from a terminal. The installer therefore copies
    the helper runtime next to the browser's own application support folder.
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "DistillPDF"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DistillPDF"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "distillpdf"


def venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def prepare_runtime() -> Path:
    """Copy the pipeline into the helper's own folder and write its wrapper."""
    target = runtime_dir()
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "native_host.py", target / "native_host.py")

    for folder in ("pipeline", "templates"):
        destination = target / folder
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            ROOT / folder,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    config = ROOT / "config.yaml"
    if config.exists():
        shutil.copy2(config, target / "config.yaml")
    else:
        (target / "config.yaml").unlink(missing_ok=True)

    # Do NOT resolve(): .venv/bin/python is a symlink to the system interpreter,
    # and following it loses the venv's pyvenv.cfg (hence all site-packages).
    python = venv_python()
    if os.name == "nt":
        (target / "distillpdf-host.cmd").write_text(
            "@echo off\r\n"
            f'"{python}" "%~dp0native_host.py"\r\n',
            encoding="utf-8",
        )
        return target / "distillpdf-host.cmd"

    wrapper = target / "distillpdf-host"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "# Installed by scripts/install_native_host.py. Runs the local pipeline.\n"
        f'exec "{python}" "$(dirname "$0")/native_host.py"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper


def host_executable() -> Path:
    return prepare_runtime()


def manifest(executable: Path) -> dict[str, Any]:
    return {
        "name": HOST,
        "description": "DistillPDF local PDF + HTML builder",
        "path": str(executable),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{EXTENSION_ID}/"],
    }


def _darwin_folders() -> list[Path]:
    base = Path.home() / "Library" / "Application Support"
    names = (
        "Google/Chrome",
        "Google/Chrome Dev",
        "Chromium",
        "Microsoft Edge",
        "BraveSoftware/Brave-Browser",
    )
    return [base / name / "NativeMessagingHosts" for name in names]


def _linux_folders() -> list[Path]:
    base = Path.home() / ".config"
    names = (
        "google-chrome",
        "google-chrome-beta",
        "chromium",
        "microsoft-edge",
        "BraveSoftware/Brave-Browser",
    )
    return [base / name / "NativeMessagingHosts" for name in names]


def _windows_manifest(executable: Path) -> Path:
    # Windows native hosts are registered through the registry, so the JSON
    # lives with the helper instead of inside a browser profile.
    target = runtime_dir() / f"{HOST}.json"
    target.write_text(json.dumps(manifest(executable), indent=2) + "\n", encoding="utf-8")
    return target


def _write_registry(manifest_path: Path) -> list[str]:
    import winreg  # type: ignore[import-not-found]

    roots = (
        (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\NativeMessagingHosts"),
        (winreg.HKEY_CURRENT_USER, r"Software\Google\ChromeDev\NativeMessagingHosts"),
        (winreg.HKEY_CURRENT_USER, r"Software\Chromium\NativeMessagingHosts"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Edge\NativeMessagingHosts"),
        (winreg.HKEY_CURRENT_USER, r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts"),
    )
    written: list[str] = []
    for root, prefix in roots:
        try:
            key = winreg.CreateKey(root, f"{prefix}\\{HOST}")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest_path))
            winreg.CloseKey(key)
            written.append(prefix.split("\\")[1])
        except OSError:
            continue
    return written


def install() -> list[Path]:
    executable = host_executable()
    if not executable.exists():
        raise FileNotFoundError(f"Native helper wrapper not found: {executable}")
    if os.name != "nt" and not os.access(executable, os.X_OK):
        executable.chmod(0o755)

    if os.name == "nt":
        target = _windows_manifest(executable)
        browsers = _write_registry(target)
        print(f"registered {HOST} for: {', '.join(browsers) or 'no supported browser'}")
        print(f"manifest: {target}")
        return [target]

    data = json.dumps(manifest(executable), indent=2) + "\n"
    written: list[Path] = []
    candidates = _darwin_folders() if platform.system() == "Darwin" else _linux_folders()
    for index, folder in enumerate(candidates):
        # Only create the registration where a browser profile exists, except
        # for the first (Chrome) entry which we always set up.
        if index and not folder.parent.exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{HOST}.json"
        target.write_text(data, encoding="utf-8")
        written.append(target)
    for target in written:
        print(f"registered: {target}")
    return written


def main() -> int:
    try:
        install()
    except Exception as exc:
        print(f"Could not register the native helper: {exc}", file=sys.stderr)
        return 1
    print("Reload the extension in chrome://extensions once after installation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
