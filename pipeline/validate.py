"""Render verification -- runs after every PDF and writes report.json.

Automatic checks are supplemented by a contact sheet for a quick human skim.
A failed check marks the export as failed and the report points at
study-notes.html, which is always written as an offline fallback.
"""

from __future__ import annotations

import argparse
import math as math_module
import re
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from .common import (
    _without_fences,
    count_math,
    load_config,
    plain_text_from_markdown,
    read_json,
    word_count,
    write_json,
)
from .mermaid_validate import extract_mermaid_sources, validate_mermaid_blocks
from .fidelity import compare_source
from .structure import normalize_structure

_TOLERANCE = 0.02
_CONTENT_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{3,}")


def _source_content_terms(markdown_text: str) -> set[str]:
    """Prose words only: math command names never appear as PDF text."""
    text = _without_fences(markdown_text)
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    text = re.sub(r"(?<!\\)\$([^\n$]+?)(?<!\\)\$", " ", text)
    plain = plain_text_from_markdown(text)
    return {word.lower() for word in _CONTENT_WORD_RE.findall(plain)}


def _browser_metrics(html_path: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    channel = (config.get("render", {}) or {}).get("chrome_channel", "chrome")
    launch: dict[str, Any] = {"headless": True}
    if channel:
        launch["channel"] = str(channel)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch)
        try:
            page = browser.new_page()
            page.goto(Path(html_path).resolve().as_uri(), wait_until="load")
            page.wait_for_function(
                "window.__NLMDF && window.__NLMDF.ready === true", timeout=120_000
            )
            state = dict(page.evaluate("() => window.__NLMDF"))
            state["dom_katex"] = page.locator(".nlmdf-symbol").count()
            state["dom_symbol_svg"] = page.locator(".nlmdf-symbol-svg").count()
            state["dom_katex_errors"] = page.locator(".katex-error").count()
            state["dom_tables"] = page.locator("table").count()
            state["dom_list_items"] = page.locator("main li:not(.footnote-item)").count()
            state["dom_mermaid_figures"] = page.locator(".mermaid-figure").count()
            state["dom_error_svgs"] = page.evaluate(
                """() => Array.from(document.querySelectorAll('.mermaid-figure svg'))
                    .filter(function (svg) {
                      return /syntax error|error in text/i.test(svg.textContent || '');
                    }).length"""
            )
            state["dom_text_words"] = len((page.locator("main").inner_text() or "").split())
            state["dom_toc_words"] = 0
            state["fitted_blocks"] = int(state.get("fittedBlocks", 0))
            state["min_diagram_scale"] = float(state.get("minDiagramScale", 1))
            state["diagram_lines"] = list(state.get("diagramLines", []))
            state["diagram_aligned"] = bool(state.get("diagramAligned", True))
            state["overflow_blocks"] = page.evaluate(
                """() => {
                    var bad = 0;
                    // Scaled SVG circuits: the whole drawing must sit inside
                    // its figure, and every source line stays a <text> node.
                    document.querySelectorAll('figure.nlmdf-diagram').forEach(function (fig) {
                      var svg = fig.querySelector('svg');
                      if (!svg || !svg.querySelector('text')) { bad += 1; return; }
                      var outer = fig.getBoundingClientRect();
                      var inner = svg.getBoundingClientRect();
                      if (inner.right > outer.right + 1 || inner.left < outer.left - 1) bad += 1;
                      if (Number(fig.getAttribute('data-nlmdf-lines')) !== svg.querySelectorAll('text').length) bad += 1;
                    });
                    // Ordinary pre blocks must not overflow either.
                    document.querySelectorAll('pre').forEach(function (pre) {
                      var code = pre.querySelector('code');
                      if (!code) return;
                      var outer = pre.getBoundingClientRect();
                      var inner = code.getBoundingClientRect();
                      if (inner.right > outer.right + 1 || inner.left < outer.left - 1) bad += 1;
                    });
                    return bad;
                }"""
            )
            return state
        finally:
            browser.close()


def _markdown_token_counts(text: str) -> tuple[int, int, int]:
    # Count the structure the renderer actually sees, so a table that
    # NotebookLM emitted inside a numbered line is expected as a table.
    tokens = MarkdownIt("commonmark").enable("table").parse(normalize_structure(text))
    tables = sum(1 for token in tokens if token.type == "table_open")
    mermaid = sum(
        1
        for token in tokens
        if token.type == "fence" and token.info.strip().lower() == "mermaid"
    )
    list_items = sum(1 for token in tokens if token.type == "list_item_open")
    return tables, mermaid, list_items


def _pdf_text(pdf_path: str | Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _contact_sheet(pdf_path: str | Path, output: str | Path, columns: int = 3) -> str:
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    document = pdfium.PdfDocument(str(pdf_path))
    thumbs: list[tuple[int, Image.Image]] = []
    width = 280
    for number in range(len(document)):
        bitmap = document[number].render(scale=1.2)
        image = bitmap.to_pil().convert("RGB")
        height = max(1, round(image.height * width / image.width))
        thumbs.append((number + 1, image.resize((width, height))))

    cell_height = max((image.height for _, image in thumbs), default=200) + 34
    rows = math_module.ceil(len(thumbs) / columns)
    canvas = Image.new(
        "RGB", (columns * (width + 24), max(1, rows) * cell_height), "#e9edf2"
    )
    draw = ImageDraw.Draw(canvas)
    for position, (number, image) in enumerate(thumbs):
        column, row = position % columns, position // columns
        x = column * (width + 24) + 12
        y = row * cell_height + 12
        draw.rectangle(
            [x - 1, y - 1, x + width, y + image.height], fill="white", outline="#b9c2cc"
        )
        canvas.paste(image, (x, y))
        draw.text((x + 2, y + image.height + 6), f"Page {number}", fill="#20272f")

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)
    return str(target.resolve())


def _check(name: str, passed: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "pass": bool(passed),
        "detail": detail,
        **extra,
    }


def _source_check(
    markdown: str, pdf_text: str, html: Path, strip_citations: bool, config: dict[str, Any]
) -> dict[str, Any]:
    comparison = compare_source(
        markdown, pdf_text, html.read_text(encoding="utf-8") if html.is_file() else None,
        remove_citations=strip_citations, config=config,
    )
    detail = ", ".join(
        f"{item['unmatched_blocks']}/{item['expected_blocks']} source blocks unmatched in {name.upper()}"
        for name, item in comparison.items()
    )
    return _check(
        "source_fidelity",
        not any(item["unmatched_blocks"] for item in comparison.values()),
        detail,
        outputs=comparison,
    )


def validate(
    pdf_path: str | Path,
    html_path: str | Path | None = None,
    enhanced_path: str | Path | None = None,
    meta_path: str | Path | None = None,
    report_path: str | Path | None = None,
    config: dict[str, Any] | None = None,
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run all verification checks and write report.json."""
    config = config or load_config()
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_file}")
    if html_path is None:
        html_file = (
            pdf_file.with_suffix(".html") if source_path is not None and enhanced_path is None
            else pdf_file.with_name("study-notes.html")
        )
    else:
        html_file = Path(html_path)
    if enhanced_path is None:
        enhanced_file = pdf_file.with_name("enhanced.md")
    else:
        enhanced_file = Path(enhanced_path)
    if meta_path is None:
        meta_file = pdf_file.with_name("clean.meta.json")
    else:
        meta_file = Path(meta_path)
    if report_path is None:
        report_file = pdf_file.with_name("report.json")
    else:
        report_file = Path(report_path)

    if source_path is not None and enhanced_path is None:
        source = Path(source_path).read_text(encoding="utf-8")
        check = _source_check(
            source, _pdf_text(pdf_file), html_file, bool(config.get("strip_citations", True)), config,
        )
        report = {"pdf": str(pdf_file.resolve()), "passed": check["pass"], "checks": [check]}
        write_json(report_file, report)
        print(f"validate: {'PASS' if report['passed'] else 'FAIL'} -> {report_file}")
        print(f"  {check['detail']}")
        return report

    markdown_text = enhanced_file.read_text(encoding="utf-8")
    manifest = read_json(meta_file) if meta_file.exists() else {}
    expected = manifest.get("expected", {})
    metrics = _browser_metrics(html_file, config)
    extracted = _pdf_text(pdf_file)
    markdown_tables, _, markdown_list_items = _markdown_token_counts(markdown_text)

    checks: list[dict[str, Any]] = []

    # 1. Math ------------------------------------------------------------------
    expected_math = int(expected.get("formulas", count_math(markdown_text)))
    rendered_math = int(metrics.get("dom_katex", 0))
    katex_errors = int(
        metrics.get("dom_katex_errors", metrics.get("katexErrors", 0))
    )
    checks.append(
        _check(
            "math",
            katex_errors == 0 and rendered_math == expected_math,
            (
                "No formulas found in the input. Formula preservation could not be checked."
                if expected_math == rendered_math == katex_errors == 0
                else f"{rendered_math}/{expected_math} formulas rendered, "
                     f"{katex_errors} KaTeX error elements"
            ),
            expected=expected_math,
            actual=rendered_math,
            errors=katex_errors,
        )
    )

    # 2. Flowcharts ------------------------------------------------------------
    blocks = extract_mermaid_sources(markdown_text)
    channel = (config.get("render", {}) or {}).get("chrome_channel", "chrome")
    parsed = validate_mermaid_blocks(blocks, channel)
    figures = int(metrics.get("dom_mermaid_figures", 0))
    error_svgs = int(metrics.get("dom_error_svgs", 0))
    checks.append(
        _check(
            "flowcharts",
            all(parsed) and error_svgs == 0 and figures == len(blocks),
            f"{len(blocks)} blocks, {sum(parsed)} parse, {figures} rendered, "
            f"{error_svgs} error SVGs",
            expected=len(blocks),
            actual=figures,
        )
    )

    # 3. Tables ----------------------------------------------------------------
    expected_tables = int(expected.get("tables", markdown_tables))
    actual_tables = int(metrics.get("dom_tables", 0))
    checks.append(
        _check(
            "tables",
            actual_tables == expected_tables,
            f"{actual_tables} tables in HTML vs {expected_tables} in source",
            expected=expected_tables,
            actual=actual_tables,
        )
    )

    rendered_list_items = int(metrics.get("dom_list_items", 0))
    shortfalls = manifest.get("list_item_shortfalls", [])
    details = [f"{rendered_list_items}/{markdown_list_items} Markdown list items rendered in HTML"]
    details.extend(
        f"Answer {item['index']}: {item['actual']}/{item['expected']} captured list items reached clean Markdown"
        for item in shortfalls
    )
    checks.append(
        _check(
            "list_items",
            not shortfalls and rendered_list_items == markdown_list_items,
            ". ".join(details),
            expected=markdown_list_items,
            actual=rendered_list_items,
            capture_shortfalls=shortfalls,
        )
    )

    # 3b. Wide ASCII circuits / diagrams must fit without wrapping -----------
    fitted = int(metrics.get("fitted_blocks", 0))
    overflow = int(metrics.get("overflow_blocks", 0))
    min_scale = float(metrics.get("min_diagram_scale", 1))
    checks.append(
        _check(
            "diagram_fit",
            overflow == 0,
            f"{fitted} wide block(s) converted to fit-to-width SVG "
            f"(smallest scale {min_scale:.2f}); {overflow} overflowing",
            expected=0,
            actual=overflow,
        )
    )

    # 3c. A control square must be joined to its connector and target gate -----
    aligned = bool(metrics.get("diagram_aligned", True))
    checks.append(
        _check(
            "diagram_connection",
            aligned,
            "control square, vertical connector and target gate aligned"
            if aligned
            else "circuit control/connector/gate are misaligned",
            expected=True,
            actual=aligned,
        )
    )

    # 4. Missing text ----------------------------------------------------------
    source_words = word_count(plain_text_from_markdown(markdown_text))
    toc_words = int(metrics.get("dom_toc_words", 0))
    pdf_words = word_count(extracted)
    allowed = max(2, math_module.ceil((source_words + toc_words) * _TOLERANCE))
    if expected_math == 0:
        # Plain prose: the architecture's original word-count comparison.
        passed = abs(pdf_words - (source_words + toc_words)) <= allowed
        detail = (
            f"PDF {pdf_words} words; enhanced.md ~{source_words} + TOC {toc_words} "
            f"(tolerance {_TOLERANCE:.0%}, allowed {allowed})"
        )
    else:
        # KaTeX emits MathML as well as glyphs, so extracted PDF text contains
        # many extra tokens per formula. A 2% *total* word count is therefore
        # meaningless for math-heavy notes; verify that prose survived instead.
        source_terms = _source_content_terms(markdown_text)
        pdf_terms = {word.lower() for word in _CONTENT_WORD_RE.findall(extracted)}
        missing_terms = sorted(source_terms - pdf_terms)
        coverage = 1 - len(missing_terms) / max(1, len(source_terms))
        passed = coverage >= 1 - _TOLERANCE
        detail = (
            f"{coverage:.1%} of {len(source_terms)} prose terms found in PDF; "
            f"{len(missing_terms)} missing; PDF has {pdf_words} words "
            f"(KaTeX MathML inflates the count)"
        )
    checks.append(
        _check(
            "missing_text",
            passed,
            detail,
            expected=source_words + toc_words,
            actual=pdf_words,
        )
    )

    source = Path(source_path).read_text(encoding="utf-8") if source_path is not None else manifest.get("source_markdown")
    if source is not None:
        checks.append(_source_check(
            source, extracted, html_file,
            bool(manifest.get("strip_citations", config.get("strip_citations", True))),
            config,
        ))

    # 5. Missing symbols -------------------------------------------------------
    plain = plain_text_from_markdown(markdown_text)
    non_ascii = sorted({char for char in plain if ord(char) > 127})
    missing = [char for char in non_ascii if char not in extracted]
    replacement_char = "\ufffd" in extracted
    checks.append(
        _check(
            "missing_symbols",
            not missing and not replacement_char,
            f"{len(non_ascii)} non-ASCII characters checked; "
            f"missing={missing!r}; U+FFFD={replacement_char}",
            missing=missing,
            replacement_char=replacement_char,
        )
    )

    # 6. Visual contact sheet (manual) ----------------------------------------
    sheet = _contact_sheet(pdf_file, pdf_file.with_name("contact-sheet.png"))
    checks.append(
        {
            "name": "visual",
            "status": "manual",
            "pass": True,
            "detail": f"Skim {Path(sheet).name} for broken diagrams or awkward breaks.",
            "contact_sheet": sheet,
        }
    )

    passed = all(item["pass"] for item in checks)
    report = {
        "pdf": str(pdf_file.resolve()),
        "html_fallback": str(html_file.resolve()),
        "passed": passed,
        "checks": checks,
        "browser_metrics": metrics,
    }
    write_json(report_file, report)

    print(f"validate: {'PASS' if passed else 'FAIL'} -> {report_file}")
    for item in checks:
        if item["status"] != "pass":
            print(f"  [{item['status']}] {item['name']}: {item['detail']}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the rendered PDF")
    parser.add_argument("pdf", help="study-notes.pdf")
    parser.add_argument("--html", help="study-notes.html")
    parser.add_argument("--md", help="enhanced.md")
    parser.add_argument("--source-md", help="initial chat Markdown to compare with the exported PDF and HTML")
    parser.add_argument("--meta", help="clean.meta.json")
    parser.add_argument("--report", help="report.json output")
    parser.add_argument("--config", help="config.yaml")
    args = parser.parse_args(argv)

    report = validate(
        args.pdf, args.html, args.md, args.meta, args.report, load_config(args.config),
        source_path=args.source_md,
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
