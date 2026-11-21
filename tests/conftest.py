from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CHAT = ROOT / "sample" / "chat.json"


@pytest.fixture()
def config() -> dict:
    from pipeline.common import load_config

    return load_config()


@pytest.fixture()
def small_chat(tmp_path: Path) -> Path:
    payload = {
        "title": "Unit fixture",
        "user_instructions": "",
        "turns": [
            {"role": "user", "markdown": "Please explain this", "index": 0},
            {
                "role": "assistant",
                "markdown": "First answer with $\\alpha \\le 1$ and `code_0`.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |",
                "latex": ["\\alpha \\le 1"],
                "index": 1,
            },
            {
                "role": "assistant",
                "markdown": "Second answer with `code_1` and [1] a citation.",
                "index": 2,
            },
        ],
    }
    path = tmp_path / "chat.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def cleaned(small_chat: Path, tmp_path: Path, config: dict):
    from pipeline.clean import clean

    return clean(
        small_chat,
        tmp_path / "clean.md",
        tmp_path / "clean.meta.json",
        config,
    )
