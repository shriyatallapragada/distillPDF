"""Mermaid validation used by both enhance.py and validate.py.

The real check is ``mermaid.parse`` inside the same locally-bundled Mermaid
build the renderer uses. If a browser is not available, a conservative
structural check is used and a warning is emitted.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

MERMAID_JS = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "vendor"
    / "mermaid"
    / "mermaid.min.js"
)

FENCED_MERMAID_RE = re.compile(
    r"(?ms)^(`{3,}|~{3,})\s*mermaid\s*\n(.*?)^\1[ \t]*$"
)


def extract_mermaid_sources(text: str) -> list[str]:
    """Return the code *inside* mermaid fences, without the backticks."""
    return [match.group(2).strip() for match in FENCED_MERMAID_RE.finditer(text)]

_DIAGRAM_RE = re.compile(
    r"^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|"
    r"erDiagram|journey|gantt|pie|mindmap|timeline)\b"
)


def _structural_parse(source: str) -> bool:
    """Offline fallback: header + balanced delimiters."""
    first = next((line.strip() for line in source.splitlines() if line.strip()), "")
    if not _DIAGRAM_RE.match(first):
        return False
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    quote: str | None = None
    for char in source:
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != pairs[char]:
                return False
    return not stack


def _browser_parse(blocks: list[str], chrome_channel: str | None) -> list[bool]:
    from playwright.sync_api import sync_playwright

    script = MERMAID_JS.read_text(encoding="utf-8")
    page_html = (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        f"<body><script>{script}</script></body></html>"
    )
    results: list[bool] = []
    with sync_playwright() as playwright:
        launch: dict[str, object] = {"headless": True}
        if chrome_channel:
            launch["channel"] = chrome_channel
        browser = playwright.chromium.launch(**launch)  # type: ignore[arg-type]
        try:
            page = browser.new_page()
            page.set_content(page_html, wait_until="load")
            page.evaluate(
                "() => mermaid.initialize({startOnLoad:false, securityLevel:'loose'})"
            )
            for source in blocks:
                results.append(
                    bool(
                        page.evaluate(
                            """async (src) => {
                                try { await mermaid.parse(src); return true; }
                                catch (error) { return false; }
                            }""",
                            source,
                        )
                    )
                )
        finally:
            browser.close()
    return results


def validate_mermaid_blocks(
    blocks: list[str],
    chrome_channel: str | None = "chrome",
    use_browser: bool = True,
) -> list[bool]:
    """Return one boolean per block, in the same order."""
    if not blocks:
        return []
    if use_browser:
        try:
            return _browser_parse(blocks, chrome_channel)
        except Exception as exc:  # browser missing, offline machine, etc.
            warnings.warn(
                f"Mermaid browser validation unavailable ({exc}); "
                "using structural fallback.",
                RuntimeWarning,
                stacklevel=2,
            )
    return [_structural_parse(block) for block in blocks]
