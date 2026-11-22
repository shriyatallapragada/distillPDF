from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from pipeline.clean import clean
from pipeline.common import plain_text_from_markdown, read_json, word_count, write_json
from pipeline.enhance import enhance
from pipeline.validate import _contact_sheet, _markdown_token_counts, _pdf_text

ROOT = Path(__file__).resolve().parents[1]


def test_markdown_token_counts():
    text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```mermaid\nflowchart TD\n A --> B\n```\n"
    assert _markdown_token_counts(text) == (1, 1, 0)


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


@pytest.mark.parametrize(
    ("captured_bullets", "rendered_items", "expected_pass"),
    [(False, 0, False), (True, 0, False), (True, 2, True)],
)
def test_teleportation_list_items_are_validated(
    tmp_path: Path, monkeypatch, captured_bullets: bool, rendered_items: int, expected_pass: bool
):
    import pipeline.validate as stage

    intro = "To teleport a single unknown qubit, Alice and Bob must share:"
    bell_pair = r"|\beta_{00}\rangle = (|00\rangle+|11\rangle)/\sqrt{2}"
    classical = "Communicated over a standard classical channel from Alice to Bob"
    bullets = f"- **1 Shared Entangled Bell Pair:** ${bell_pair}$ [7]\n\n- **2 Classical Bits:** {classical} [8]\n"
    source = tmp_path / "chat.json"
    write_json(source, {"turns": [{
        "index": 11, "role": "assistant", "list_items": 2,
        "markdown": intro + ("\n\n" + bullets if captured_bullets else ""),
    }]})
    clean(source, tmp_path / "clean.md")
    enhanced = tmp_path / "enhanced.md"
    enhance(tmp_path / "clean.md", enhanced, offline=True)
    text = enhanced.read_text()
    assert "[7]" not in text and "[8]" not in text
    if captured_bullets:
        assert bell_pair in text and classical in text

    def pdf_text(_):
        if not captured_bullets:
            return f"Section 1 {intro}"
        return f"Section 1 {intro} 1 Shared Entangled Bell Pair: |β00⟩ = (|00⟩+|11⟩)/√2 2 Classical Bits: {classical}"

    monkeypatch.setattr(stage, "_browser_metrics", lambda *_: {
        "dom_list_items": rendered_items, "dom_katex": int(captured_bullets),
    })
    monkeypatch.setattr(stage, "_pdf_text", pdf_text)
    monkeypatch.setattr(stage, "_contact_sheet", lambda *_: str(tmp_path / "sheet.png"))
    pdf = tmp_path / "study-notes.pdf"
    pdf.touch()
    report = stage.validate(pdf)
    check = next(item for item in report["checks"] if item["name"] == "list_items")
    assert check["pass"] is expected_pass
    assert report["passed"] is expected_pass
    if not captured_bullets:
        assert "Answer 11: 0/2 captured list items" in check["detail"]
        assert next(item for item in report["checks"] if item["name"] == "missing_text")["pass"]
    elif not rendered_items:
        assert "0/2 Markdown list items rendered" in check["detail"]


def test_validate_initial_markdown_and_pdf_without_browser(tmp_path, monkeypatch):
    from pipeline import validate as stage
    from pipeline.cli import main

    source = tmp_path / "initial.md"
    source.write_text("**Resources:**\n\n- One Bell pair $\\sqrt{2}$ [7]\n- Keep both ΩΩ and $[0,1]$.\n")
    pdf = tmp_path / "export.pdf"
    pdf.touch()
    pdf.with_suffix(".html").write_text(
        "<main><p>Resources:</p><ul><li>One Bell pair √2</li><li>Keep both ΩΩ and [0,1].</li></ul></main>"
    )
    monkeypatch.setattr(
        stage, "_pdf_text", lambda _: "Extra heading\nResources:\nOne Bell pair √2\nKeep both Ω and [0,1]."
    )
    report = tmp_path / "report.json"
    assert main(["validate", str(pdf), "--source-md", str(source), "--report", str(report)]) == 1
    output = read_json(report)["checks"][0]["outputs"]
    assert output["html"]["unmatched_blocks"] == 0
    assert output["pdf"]["examples"] == ["Keep both ΩΩ and [0,1]."]


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
        "list_items",
        "diagram_fit",
        "diagram_connection",
        "missing_text",
        "source_fidelity",
        "missing_symbols",
        "visual",
    ]
    assert all(item["pass"] for item in data["checks"])
    assert (tmp_path / "study-notes.html").exists()
    assert (tmp_path / "study-notes.pdf").stat().st_size > 10_000
    # The offline fallback must not silently drop the sample's formula.
    assert "\\theta_{t+1}" in (tmp_path / "enhanced.md").read_text()
