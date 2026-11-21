from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from pipeline.common import plain_text_from_markdown, word_count
from pipeline.validate import _contact_sheet, _markdown_token_counts, _pdf_text

ROOT = Path(__file__).resolve().parents[1]


def test_markdown_token_counts():
    text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```mermaid\nflowchart TD\n A --> B\n```\n"
    assert _markdown_token_counts(text) == (1, 1)


def test_pdf_text_helpers(tmp_path: Path):
    pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with pdf.open("wb") as handle:
        writer.write(handle)
    assert _pdf_text(pdf) == ""
    sheet = _contact_sheet(pdf, tmp_path / "sheet.png")
    assert Path(sheet).exists()
    assert Path(sheet).stat().st_size > 0


def test_plain_text_from_markdown():
    md = "## Heading\n\n**Bold** and `code` with [link](https://example.com) and $\\alpha$.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |"
    plain = plain_text_from_markdown(md)
    assert "Heading" in plain
    assert "https://" not in plain
    assert "$" not in plain
    assert word_count(plain) > 0


@pytest.mark.integration()
def test_full_pipeline_offline(tmp_path: Path):
    from pipeline.cli import main

    code = main(["all", str(ROOT / "sample" / "chat.json"), "--outdir", str(tmp_path), "--offline"])
    assert code == 0
    report = (tmp_path / "report.json").read_text(encoding="utf-8")
    import json

    data = json.loads(report)
    assert data["passed"] is True
    assert [item["name"] for item in data["checks"]] == [
        "math",
        "flowcharts",
        "tables",
        "diagram_fit",
        "diagram_connection",
        "missing_text",
        "missing_symbols",
        "visual",
    ]
    assert all(item["pass"] for item in data["checks"])
    assert (tmp_path / "study-notes.html").exists()
    assert (tmp_path / "study-notes.pdf").stat().st_size > 10_000
    # The offline fallback must not silently drop the sample's formula.
    assert "\\theta_{t+1}" in (tmp_path / "enhanced.md").read_text()
