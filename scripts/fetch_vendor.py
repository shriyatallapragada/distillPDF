"""Download the pinned, local copies of KaTeX, Mermaid and fonts.

The renderer must work with no network access, so the browser assets are
committed to ``templates/vendor``. Re-run this script only when bumping a
version, then re-run the tests and the render verification.

Usage::

    python scripts/fetch_vendor.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "templates" / "vendor"

KATEX_VERSION = "0.16.11"
MERMAID_VERSION = "10.9.1"
INTER_VERSION = "5.2.5"

JSDELIVR = "https://cdn.jsdelivr.net/npm"

KATEX_FILES = [
    "dist/katex.min.js",
    "dist/katex.min.css",
    *[
        f"dist/fonts/{name}"
        for name in (
            "KaTeX_AMS-Regular.woff2",
            "KaTeX_Caligraphic-Bold.woff2",
            "KaTeX_Caligraphic-Regular.woff2",
            "KaTeX_Fraktur-Bold.woff2",
            "KaTeX_Fraktur-Regular.woff2",
            "KaTeX_Main-Bold.woff2",
            "KaTeX_Main-BoldItalic.woff2",
            "KaTeX_Main-Italic.woff2",
            "KaTeX_Main-Regular.woff2",
            "KaTeX_Math-BoldItalic.woff2",
            "KaTeX_Math-Italic.woff2",
            "KaTeX_SansSerif-Bold.woff2",
            "KaTeX_SansSerif-Italic.woff2",
            "KaTeX_SansSerif-Regular.woff2",
            "KaTeX_Script-Regular.woff2",
            "KaTeX_Size1-Regular.woff2",
            "KaTeX_Size2-Regular.woff2",
            "KaTeX_Size3-Regular.woff2",
            "KaTeX_Size4-Regular.woff2",
            "KaTeX_Typewriter-Regular.woff2",
        )
    ],
]

INTER_FILES = [
    "files/inter-latin-400-normal.woff2",
    "files/inter-latin-600-normal.woff2",
    "files/inter-latin-700-normal.woff2",
    "files/inter-latin-400-italic.woff2",
]


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "notebooklm-pdf-vendor/1"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https URL
        data = response.read()
    target.write_bytes(data)
    print(f"  {target.relative_to(ROOT)} ({len(data):,} bytes)")


def main() -> int:
    jobs: list[tuple[str, Path]] = []
    for rel in KATEX_FILES:
        jobs.append(
            (
                f"{JSDELIVR}/katex@{KATEX_VERSION}/{rel}",
                VENDOR / "katex" / rel.removeprefix("dist/"),
            )
        )
    jobs.append(
        (
            f"{JSDELIVR}/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js",
            VENDOR / "mermaid" / "mermaid.min.js",
        )
    )
    for rel in INTER_FILES:
        jobs.append(
            (
                f"{JSDELIVR}/@fontsource/inter@{INTER_VERSION}/{rel}",
                VENDOR / "fonts" / Path(rel).name,
            )
        )

    print(f"Fetching {len(jobs)} vendor files...")
    for url, target in jobs:
        try:
            download(url, target)
        except Exception as exc:  # pragma: no cover - network failure path
            print(f"FAILED: {url}: {exc}", file=sys.stderr)
            return 1
    print("Vendor assets are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
