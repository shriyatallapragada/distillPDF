"""Regression coverage using the real markdown export in test_txt/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REAL_MARKDOWN = ROOT / "test_txt" / "sample_chat.md"


@pytest.mark.integration()
@pytest.mark.skipif(not REAL_MARKDOWN.exists(), reason="real chat fixture not present")
def test_real_markdown_export_round_trip(tmp_path: Path):
    from pipeline.cli import main
    from scripts.markdown_to_chat import convert

    chat = tmp_path / "chat.json"
    chat.write_text(
        json.dumps(convert(REAL_MARKDOWN, title="QC notes"), ensure_ascii=False),
        encoding="utf-8",
    )
    outdir = tmp_path / "out"
    assert main(["all", str(chat), "--outdir", str(outdir), "--offline"]) == 0

    report = json.loads((outdir / "report.json").read_text(encoding="utf-8"))
    assert report["passed"] is True
    checks = {item["name"]: item for item in report["checks"]}
    assert checks["math"]["expected"] > 200  # escaped \\(...\\) + multiline $$...$$
    assert checks["math"]["errors"] == 0
    assert checks["math"]["actual"] == checks["math"]["expected"]
    assert checks["missing_text"]["pass"] is True
    # The ASCII quantum circuit is a wide preformatted block; it must become
    # one viewBox-fitted SVG with every source line intact (no wrapping).
    assert checks["diagram_fit"]["pass"] is True
    metrics = report["browser_metrics"]
    assert metrics["fitted_blocks"] >= 1
    assert metrics["min_diagram_scale"] < 1
    assert metrics["overflow_blocks"] == 0
    assert metrics["diagram_lines"] == [3]
    assert checks["diagram_connection"]["pass"] is True
    assert metrics["diagram_aligned"] is True
    page = (outdir / "study-notes.html").read_text(encoding="utf-8")
    assert "Register 2 (L qubits): |1⟩" in page
    assert (outdir / "study-notes.html").stat().st_size > 1_000_000
