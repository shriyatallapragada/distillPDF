"""Load the unpacked extension and verify capture, selection and download.

Run with: .venv/bin/python extension/test/run_test.py

Chrome launched by Playwright is managed in some environments and ignores
--load-extension, so this test starts Chrome with a debug port and loads the
extension through the standard Extensions.loadUnpacked CDP command.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

EXTENSION = Path(__file__).resolve().parents[1]
FIXTURE = (Path(__file__).parent / "fixture.html").read_text(encoding="utf-8")
PALETTE = {
    "#5B5F8D",
    "#9BB29E",
    "#DA6B51",
    "#F1DCBA",
    "#484149",
}
def chrome_executable() -> Path:
    """Find desktop Chrome on macOS, Windows or Linux."""
    candidates: list[Path] = []
    for name in ("google-chrome", "google-chrome-stable", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    if sys.platform == "darwin":
        candidates.append(
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        )
    elif os.name == "nt":
        for base in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ):
            if base:
                candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("Desktop Chrome not found; install Chrome to run this test")


def check_palette() -> None:
    used = set()
    for path in EXTENSION.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".css", ".js", ".html", ".json"}:
            used.update(c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", path.read_text()))
        elif path.suffix == ".png":
            image = Image.open(path).convert("RGB")
            pixels = (
                image.get_flattened_data()
                if hasattr(image, "get_flattened_data")
                else image.getdata()
            )
            used.update(f"#{r:02X}{g:02X}{b:02X}" for r, g, b in pixels)
    extra = used - PALETTE
    assert not extra, f"colors outside the palette: {sorted(extra)}"
    print(f"palette: {len(used)}/5 approved colors used, no extras")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    check_palette()
    port = free_port()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads = root / "downloads"
        downloads.mkdir()
        process = subprocess.Popen(
            [
                str(chrome_executable()),
                f"--remote-debugging-port={port}",
                f"--user-data-dir={root / 'profile'}",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-sandbox",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
                    break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Chrome did not start with a debug port")

            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                cdp = browser.new_browser_cdp_session()
                loaded = cdp.send("Extensions.loadUnpacked", {"path": str(EXTENSION)})
                assert loaded.get("id"), f"extension failed to load: {loaded}"
                cdp.send(
                    "Browser.setDownloadBehavior",
                    {"behavior": "allow", "downloadPath": str(downloads)},
                )

                context = browser.contexts[0]
                page = context.pages[0] if context.pages else context.new_page()
                page.route(
                    "https://notebook.google.com/**",
                    lambda route: route.fulfill(
                        status=200, content_type="text/html", body=FIXTURE
                    ),
                )
                page.goto("https://notebook.google.com/notebook/test")
                page.wait_for_selector(".nl-kebab-panel", timeout=20_000)
                page.wait_for_function(
                    "() => /answers ready/.test(document.querySelector('[data-nlk-status]').textContent)",
                    timeout=20_000,
                )

                rows = page.locator(".nl-kebab-item")
                assert rows.count() == 4, f"expected 4 answers, got {rows.count()}"
                print(f"picker: {rows.count()} assistant answers found")

                # Nothing is selected automatically; the user opts in.
                assert page.locator(".nl-kebab-item input:checked").count() == 0
                for message_id in ("a0", "a1", "a2", "a9"):
                    assert (
                        page.locator(f'[data-message-id="{message_id}"]').get_attribute(
                            "data-nlk-selected"
                        )
                        == "false"
                    )
                print("default: all answers start unchecked")

                # Pick one real answer. The popup can ask the content script
                # for the exact payload that will be sent to the local helper.
                rows.nth(1).locator("input").check()
                assert (
                    page.locator('[data-message-id="a1"]').get_attribute("data-nlk-selected")
                    == "true"
                )
                assert (
                    page.locator('[data-message-id="a2"]').get_attribute("data-nlk-selected")
                    == "false"
                )

                # Open from a GitHub tab whose title mentions NotebookLM.
                # The title must not take precedence over the real chat origin.
                other = context.new_page()
                other.route(
                    "https://github.com/**",
                    lambda route: route.fulfill(
                        status=200, content_type="text/html",
                        body="<title>DistillPDF — NotebookLM PDF exporter</title>",
                    ),
                )
                other.goto("https://github.com/shriyatallapragada/distillPDF")
                other.bring_to_front()
                popup = context.new_page()
                popup.goto(f"chrome-extension://{loaded['id']}/popup.html")
                other.bring_to_front()
                popup.evaluate("() => refresh()")
                popup.wait_for_selector(".pop-item", timeout=10_000)
                assert popup.locator(".pop-item").count() == 4
                assert popup.evaluate("() => lastTab.url").startswith("https://notebook.google.com/")
                print("popup: selected NotebookLM from an unrelated GitHub tab")

                def selected_payload():
                    result = popup.evaluate("() => send('NLK_EXPORT', undefined, lastTab)")
                    return result["data"]

                data = selected_payload()
                assert len(data["turns"]) == 1
                turn = data["turns"][0]
                assert "Gradient descent" in turn["markdown"]
                assert "$\\theta_{t+1} = \\theta_t - \\eta \\nabla_\\theta L$" in turn["markdown"]
                assert "$$\\eta \\le 1/L$$" in turn["markdown"]
                assert "\\theta_{t+1} = \\theta_t - \\eta \\nabla_\\theta L" in turn["latex"]
                assert "| Symbol | Meaning |" in turn["markdown"]
                assert "```python" in turn["markdown"]
                assert "[1]" not in turn["markdown"]
                assert "Internal thinking placeholder" not in turn["markdown"]
                # Whitespace rules: tabs -> 4 columns, NBSP kept inside the
                # diagram, trailing spaces kept, prose NBSP folded to a space.
                assert "\n    │\u00a0\u00a0  \n" in turn["markdown"]
                assert "\t" not in turn["markdown"]
                assert "Spacing in prose wraps." in turn["markdown"]
                assert "Explain gradient descent" not in json.dumps(data)
                print("export: one selected answer, exact LaTeX, table, code and whitespace")

                # The payload keeps every selected reply. The Python cleaner
                # drops only whole replies that match known boilerplate.
                popup.evaluate("() => send('NLK_TOGGLE', true, lastTab)")
                all_data = selected_payload()
                texts = [item["markdown"] for item in all_data["turns"]]
                assert len(texts) == 4, texts
                assert any("Gradient descent" in text for text in texts)
                assert any("From chat to PDF" in text for text in texts)
                assert any("How can I help" in text for text in texts)
                assert any("Let me know" in text for text in texts)
                print("export: all selected replies kept in the payload")

                # Clicking Build PDF + HTML must reach the native-helper bridge.
                # No host is registered in this test profile, so the expected
                # result is a clear "helper not installed" status in the page.
                page.get_by_role("button", name="Build PDF + HTML").click()
                page.wait_for_function(
                    "() => /Build failed|Helper unavailable/.test("
                    "document.querySelector('[data-nlk-status]').textContent)",
                    timeout=15_000,
                )
                status = page.locator("[data-nlk-status]").inner_text()
                assert "Local helper" in status or "Helper unavailable" in status, status
                print("build: button reaches the local native-helper bridge")

                page.close()
                other.bring_to_front()
                popup.reload()
                popup.get_by_role("button", name="Open NotebookLM").wait_for(timeout=10_000)
                assert popup.locator("#status").inner_text() == "Open a NotebookLM chat first."
                assert popup.locator("#picker [data-tab-id]").count() == 0
                print("popup: no NotebookLM tab yields an open button and no GitHub target")

                browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
