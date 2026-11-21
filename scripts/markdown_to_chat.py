"""Wrap a plain Markdown transcript as chat.json for the Python pipeline.

Useful when no browser is available (servers, phones, CI). The Markdown is
stored verbatim: Stage 2 still does the whitespace/citation/math normalization
it would do for an answer captured by the extension.

Usage::

    .venv/bin/python scripts/markdown_to_chat.py notes.md notes.json --title "QC notes"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def convert(source: str | Path, title: str = "", instructions: str = "") -> dict:
    text = Path(source).read_text(encoding="utf-8")
    return {
        "title": title or Path(source).stem,
        "source": f"markdown:{Path(source).resolve()}",
        "user_instructions": instructions,
        "turns": [
            {
                "role": "assistant",
                "markdown": text,
                "latex": [],
                "index": 0,
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Markdown -> chat.json wrapper")
    parser.add_argument("markdown", help="input .md transcript")
    parser.add_argument("output", nargs="?", help="output chat.json (default: alongside input)")
    parser.add_argument("--title", default="", help="notebook title")
    parser.add_argument("--instructions", default="", help="user_instructions for enhance")
    args = parser.parse_args(argv)

    out = Path(args.output) if args.output else Path(args.markdown).with_suffix(".json")
    payload = convert(args.markdown, args.title, args.instructions)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"markdown_to_chat: {args.markdown} -> {out} (1 assistant turn)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
