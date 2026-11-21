"""Stage 4 -- Markdown to a self-contained HTML file and a printed PDF.

Everything the browser needs (CSS, fonts, KaTeX, Mermaid) is inlined into
study-notes.html, so it works offline and doubles as the fallback document.
The PDF is produced by headless Chrome through Playwright.

    python -m pipeline.render sample/out/enhanced.md sample/out/study-notes.pdf
"""

from __future__ import annotations

import argparse
import base64
import html as html_lib
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

try:  # mdit-py-plugins >= 0.7 renamed the module/plugin (singular -> plural)
    from mdit_py_plugins.anchors import anchors_plugin as anchor_plugin
except ImportError:  # pragma: no cover - older installation
    from mdit_py_plugins.anchor import anchor_plugin  # type: ignore[no-redef]
from playwright.sync_api import sync_playwright

from .common import load_config, write_json
from .structure import normalize_structure
from .math_svg import (
    SYMBOL_CHARS,
    convert_math_source,
    expand_flat_matrix,
    inline_svg,
    matrix_fragment,
    matrix_rows_from_content,
    rich_parts,
    _MATRIX_CELL_RE,
    _matrix_layout,
)

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
VENDOR = TEMPLATES / "vendor"
_KATEX_CSS = VENDOR / "katex" / "katex.min.css"
_KATEX_JS = VENDOR / "katex" / "katex.min.js"
_MERMAID_JS = VENDOR / "mermaid" / "mermaid.min.js"
_INTER = {
    400: VENDOR / "fonts" / "inter-latin-400-normal.woff2",
    600: VENDOR / "fonts" / "inter-latin-600-normal.woff2",
    700: VENDOR / "fonts" / "inter-latin-700-normal.woff2",
}
_ITALIC = VENDOR / "fonts" / "inter-latin-400-italic.woff2"


class _HeadingCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._math_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"h1", "h2", "h3"}:
            self._current = {
                "level": int(tag[1]),
                "id": attributes.get("id") or "",
                "text": "",
            }
        if "math-source" in (attributes.get("class") or "").split():
            self._math_depth += 1

    def handle_data(self, data: str) -> None:
        if self._current is not None and not self._math_depth:
            self._current["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._math_depth:
            self._math_depth -= 1
        if tag in {"h1", "h2", "h3"} and self._current is not None:
            self.headings.append(self._current)
            self._current = None


def _escape_math(source: str) -> str:
    return html_lib.escape(source.strip(), quote=False)


def _prepare_math(text: str) -> tuple[str, dict[str, str]]:
    """Swap $...$ for inert tokens, returning their final KaTeX HTML snippets.

    The snippets are re-inserted *after* markdown-it has run: raw HTML inline
    tokens do not protect their children from emphasis/escape parsing, which
    would silently corrupt LaTeX such as ``\\theta^*``.
    """
    stashed: dict[str, str] = {}
    snippets: dict[str, str] = {}
    lines: list[str] = []
    index = 0
    source_lines = text.split("\n")

    def token(source: str, display: bool) -> str:
        key = f"@@NLMDFMATH{len(snippets)}END@@"
        css = "nlmdf-symbol" + (" display" if display else "")
        snippets[key] = f'<span class="{css}">{convert_math_source(source)}</span>'
        return key

    while index < len(source_lines):
        line = source_lines[index]
        opening = re.match(r"^\s*(`{3,}|~{3,})", line)
        if opening:
            marker = opening.group(1)[0]
            width = len(opening.group(1))
            block = [line]
            index += 1
            closing = re.compile(rf"^\s*{re.escape(marker)}{{{width},}}\s*$")
            while index < len(source_lines) and not closing.match(source_lines[index]):
                block.append(source_lines[index])
                index += 1
            if index < len(source_lines):
                block.append(source_lines[index])
                index += 1
            key = f"@@NLMDF_FENCE_{len(stashed)}@@"
            stashed[key] = "\n".join(block)
            lines.append(key)
            continue
        lines.append(line)
        index += 1

    body = "\n".join(lines)
    # Display math may start mid-paragraph (e.g. "the matrix is $$...$$") and
    # may span several lines (bmatrix/array environments). The lookarounds keep
    # it from stealing the inner $ of an existing $$ pair.
    body = re.sub(
        r"(?s)(?<!\$)\$\$(?!\$)(.*?)(?<!\$)\$\$(?!\$)",
        lambda m: token(m.group(1), True),
        body,
    )

    def inline(line: str) -> str:
        codes: list[str] = []

        def stash_code(match: re.Match[str]) -> str:
            codes.append(match.group(0))
            return f"@@NLMDF_INLINE_{len(codes) - 1}@@"

        line = re.sub(r"`+[^`\n]+`+", stash_code, line)
        line = re.sub(r"\$\$(.+?)\$\$", lambda m: token(m.group(1), True), line)
        line = re.sub(
            r"(?<!\\)\$([^\n$]+?)(?<!\\)\$", lambda m: token(m.group(1), False), line
        )
        for position, code in enumerate(codes):
            line = line.replace(f"@@NLMDF_INLINE_{position}@@", code)
        return line

    body = "\n".join(inline(line) for line in body.split("\n"))
    for key, block in stashed.items():
        body = body.replace(key, block)
    return body, snippets


def _markdown_to_html(markdown_text: str) -> tuple[str, str, int]:
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    md.use(footnote_plugin)
    try:
        md.use(anchor_plugin, min_level=1, max_level=3, permalink=False)
    except TypeError:  # pragma: no cover - older plugin signature
        md.use(anchor_plugin, permalink=False)
    prepared, snippets = _prepare_math(normalize_structure(markdown_text))
    body = md.render(prepared)
    for key, snippet in snippets.items():
        body = body.replace(key, snippet)

    # The generated Contents block was removed at the user's request. Anchors
    # from the Markdown headings are kept, but no separate navigation is built.
    return body, "", len(snippets)


def _data_uri(path: Path, mime: str = "font/woff2") -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _inlined_katex_css() -> str:
    css = _KATEX_CSS.read_text(encoding="utf-8")
    # Keep only the woff2 source; the woff/ttf fallbacks are not bundled.
    css = re.sub(
        r',url\(fonts/[^)]+\.(?:woff|ttf)\) format\("[^"]+"\)', "", css
    )

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        font = VENDOR / "katex" / "fonts" / name
        if not font.exists():
            raise FileNotFoundError(f"Missing KaTeX font: {font}")
        return f"url({_data_uri(font)})"

    return re.sub(r"url\(fonts/([^)]+\.woff2)\)", replace, css)


def _inlined_font_css() -> str:
    rules = [
        f'@font-face{{font-family:Inter;font-style:normal;font-weight={weight};'
        f'src:url({_data_uri(path)}) format("woff2")}}'
        for weight, path in _INTER.items()
    ]
    rules.append(
        f'@font-face{{font-family:Inter;font-style:italic;font-weight:400;'
        f'src:url({_data_uri(_ITALIC)}) format("woff2")}}'
    )
    return "\n".join(rules)


def _safe_script(source: str) -> str:
    """Prevent a literal </script> inside a vendor bundle from ending the tag."""
    return source.replace("</script", "<\\/script")


_CIRCUIT_CHARS = set("─│┌┐└┘├┤┬┴┼═║■►▼◆◀")
_CODE_BLOCK_RE = re.compile(r"<pre><code[^>]*>(.*?)</code></pre>", re.S)

# Geometry of the monospace code style in print.css (7.744pt -> 10.33px).
_CIRCUIT_CELL = 6.2
_CIRCUIT_FONT = 10.33
_CIRCUIT_LINE = 15.0


_VERTICAL_SYMBOLS = set("■┼┬┴│⊕⊙◉●")
_BAR_ROW_RE = re.compile(r"^[ \t]*(?:│[ \t]*)+$")


def _candidate_columns(row: str) -> list[int]:
    return [index for index, char in enumerate(row) if char in _VERTICAL_SYMBOLS]


def _align_circuit_lines(lines: list[str]) -> list[str]:
    """Restore connectors that a chat export collapsed into ``│ │ │``.

    NotebookLM flattens runs of spaces in ASCII circuits. A connector row is
    rebuilt only when its bar count matches the vertical-control symbols in
    the row above (preferred) or below; otherwise the author's spacing is kept
    untouched. This handles a single control as well as multi-control gates.
    """
    out = list(lines)
    for row_index, row in enumerate(out):
        if not _BAR_ROW_RE.match(row):
            continue
        bars = [index for index, char in enumerate(row) if char == "│"]
        if not bars:
            continue

        above = _candidate_columns(out[row_index - 1]) if row_index else []
        below = (
            _candidate_columns(out[row_index + 1])
            if row_index + 1 < len(out)
            else []
        )
        chosen: list[int] | None = None
        for pool in (above, below):
            if len(pool) == len(bars):
                chosen = pool
                break
        if chosen is None:
            common = [column for column in above if column in below]
            if len(common) == len(bars):
                chosen = common
        if chosen is None:
            continue  # ambiguous: leave the source exactly as written

        width = max(chosen + [len(row) - 1]) + 1
        rebuilt = [" "] * width
        for column in chosen:
            rebuilt[column] = "│"
        out[row_index] = "".join(rebuilt).rstrip()

    # Simple single-control circuit: centre the [gate] under the ■ connector.
    square_row = next((i for i, line in enumerate(out) if "■" in line), -1)
    bar_row = next(
        (i for i, line in enumerate(out) if re.fullmatch(r"\s*│\s*", line)), -1
    )
    if square_row >= 0 and bar_row >= 0 and len(out) == 3:
        col = out[square_row].index("■")
        out[bar_row] = " " * col + "│"  # keep row 0 completely untouched
        for row in range(bar_row + 1, len(out)):
            match = re.search(r"\[[^\]]+\]", out[row])
            if not match:
                continue
            box = match.group(0)
            start = match.start()
            centre = start + (len(box) - 1) / 2
            delta = round(col - centre)
            if delta:
                before, after = out[row][:start], out[row][start + len(box) :]
                if delta > 0:
                    borrowed = after[:delta]
                    if borrowed and set(borrowed) <= {"─"}:
                        after = after[delta:]
                        before += borrowed
                    else:
                        before += " " * delta
                else:
                    need = -delta
                    tail = before[-need:] if need else ""
                    if tail and set(tail) <= {"─"}:
                        before = before[:-need]
                    after = "─" * need + after
                out[row] = before + box + after
            break
    return out


_MATRIX_BRACKET_RE = re.compile(r"\[([^\[\]\n]{1,120})\]")


def _looks_like_matrix_content(content: str) -> bool:
    if matrix_rows_from_content(content) is not None:
        return True
    cells = [cell for cell in re.split(r"\s+", content.strip()) if cell]
    return bool(cells) and all(_MATRIX_CELL_RE.fullmatch(cell) for cell in cells)


def _matrix_groups_in_lines(lines: list[str]) -> tuple[list[dict[str, Any]], list[list[str]]]:
    """Find bracketed matrices and blank their text so SVG can replace it."""
    records: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        for match in _MATRIX_BRACKET_RE.finditer(line):
            content = match.group(1)
            if not _looks_like_matrix_content(content):
                continue
            records.append(
                {
                    "line": line_index,
                    "start": match.start(),
                    "end": match.end(),
                    "content": content,
                }
            )

    blanked = [list(line) for line in lines]
    for record in records:
        for position in range(record["start"], record["end"]):
            blanked[record["line"]][position] = " "

    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for first in range(len(records)):
        for second in range(first + 1, len(records)):
            near_row = abs(records[first]["line"] - records[second]["line"]) <= 1
            near_column = abs(records[first]["start"] - records[second]["start"]) <= 3
            if near_row and near_column:
                parent[find(second)] = find(first)

    grouped: dict[int, list[dict[str, Any]]] = {}
    for index, record in enumerate(records):
        grouped.setdefault(find(index), []).append(record)

    groups: list[dict[str, Any]] = []
    for members in grouped.values():
        members.sort(key=lambda item: (item["line"], item["start"]))
        rows: list[list[str]] = []
        for member in members:
            parsed = matrix_rows_from_content(member["content"])
            if parsed and len(parsed) > 1:
                # A compact matrix carries all of its rows in one bracket.
                rows = parsed
            else:
                cells = parsed[0] if parsed else [
                    cell for cell in re.split(r"\s+", member["content"].strip()) if cell
                ]
                rows.append(cells)
        groups.append(
            {
                "line": members[0]["line"],
                "start": min(member["start"] for member in members),
                "rows": rows,
            }
        )
    return groups, ["".join(line) for line in blanked]


def _static_circuit_svg(html: str, config: dict[str, Any]) -> str:
    """Embed circuits and matrices as build-time SVG in the HTML itself.

    The fallback document therefore shows correctly aligned diagrams even with
    JavaScript disabled. Matrices are drawn with real brackets and an aligned
    cell grid instead of ragged ``[ ...`` text rows.
    """
    margin_mm = float(config.get("render", {}).get("margin_mm", 16))
    available_px = (210 - 2 * margin_mm) / 25.4 * 96 - 26  # padding + border

    def replace(match: re.Match[str]) -> str:
        # Mermaid sources are consumed later by boot.js; leave them as code.
        if "language-mermaid" in match.group(0):
            return match.group(0)
        # Tabs are four columns everywhere (CSS tab-size and boot.js agree);
        # other whitespace, including NBSP used for alignment, is untouched.
        raw = html_lib.unescape(match.group(1)).replace("\t", "    ").rstrip("\n")
        # Circuit diagrams and boxed matrix summaries both rely on column
        # alignment, so both use the same monospace, fit-to-width SVG.
        if not any(char in raw for char in _CIRCUIT_CHARS) and "[" not in raw:
            return match.group(0)

        lines = _align_circuit_lines(raw.split("\n"))
        groups, blanked_lines = _matrix_groups_in_lines(lines)
        cells_by_group = [
            [[rich_parts(cell) for cell in row] for row in group["rows"]]
            for group in groups
        ]
        matrix_heights = [
            _matrix_layout(cells, _CIRCUIT_FONT, _CIRCUIT_CELL)[1]
            for cells in cells_by_group
        ]
        top_pad = max(0.0, max(matrix_heights, default=0.0) / 2 - _CIRCUIT_FONT * 0.65 + 2)
        bottom_pad = top_pad

        max_text_width = max(len(line) for line in lines) * _CIRCUIT_CELL
        max_matrix_right = max(
            (
                group["start"] * _CIRCUIT_CELL
                + _matrix_layout(cells, _CIRCUIT_FONT, _CIRCUIT_CELL)[0]
                for group, cells in zip(groups, cells_by_group)
            ),
            default=0.0,
        )
        width = max(max_text_width, max_matrix_right) + 2
        height = top_pad + len(lines) * _CIRCUIT_LINE + bottom_pad + 2
        scale = available_px / width if available_px > 0 else 1.0
        text_count = len(lines) + sum(
            len(row) for cells in cells_by_group for row in cells
        )

        parts = [
            '<figure class="nlmdf-diagram nlmdf-circuit" data-nlmdf-static="1" '
            f'data-nlmdf-lines="{text_count}" data-nlmdf-scale="{scale:.4f}">',
            f'<svg viewBox="0 0 {width:.2f} {height:.2f}" width="100%" '
            'preserveAspectRatio="xMinYMin meet" role="img" '
            'aria-label="Circuit / diagram">',
        ]
        for index, line in enumerate(blanked_lines):
            baseline = top_pad + index * _CIRCUIT_LINE + _CIRCUIT_FONT
            # Keep circuit rows as literal, pinned text: boot.js checks ■/│/[ ]
            # positions against the original source columns.
            parts.append(
                f'<text x="0" y="{baseline:.2f}" xml:space="preserve" '
                'font-family="SFMono-Regular, Consolas, monospace" '
                f'font-size="{_CIRCUIT_FONT:.2f}px" '
                f'textLength="{len(line) * _CIRCUIT_CELL:.2f}" '
                'lengthAdjust="spacingAndGlyphs" style="white-space:pre">'
                f"{html_lib.escape(line)}</text>"
            )
        for group, cells in zip(groups, cells_by_group):
            baseline = top_pad + group["line"] * _CIRCUIT_LINE + _CIRCUIT_FONT
            markup, _ = matrix_fragment(
                cells,
                baseline,
                _CIRCUIT_FONT,
                _CIRCUIT_CELL,
                x=group["start"] * _CIRCUIT_CELL,
            )
            parts.append(markup)
        parts.append("</svg></figure>")
        return "".join(parts)

    return _CODE_BLOCK_RE.sub(replace, html)


# Characters allowed inside a symbol run: the math glyphs themselves, the
# letters/digits that form a formula around them, and light punctuation.
_RUN_CHARS = SYMBOL_CHARS | set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "()[]{}<>=+-*/|^_,.;:!?~`\"'"
)


def _wrap_text_symbols(text: str) -> str:
    """Wrap maximal symbol-containing runs of ``text`` in inline SVG."""
    pieces: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if not run:
            return
        segment = "".join(run)
        run.clear()
        if any(char in SYMBOL_CHARS for char in segment):
            # Trim leading/trailing spaces out of the SVG; keep them in prose.
            leading = len(segment) - len(segment.lstrip(" "))
            trailing = len(segment) - len(segment.rstrip(" "))
            core = segment.strip(" ")
            if core:
                pieces.append(" " * leading + inline_svg(core) + " " * trailing)
            else:
                pieces.append(segment)
        else:
            pieces.append(segment)

    for char in text:
        if char in _RUN_CHARS:
            run.append(char)
        else:
            flush()
            pieces.append(char)
    flush()
    return "".join(pieces)


_FLAT_BRACKET_RE = re.compile(r"\[([^\[\]{}]{3,40})\]")


def _wrap_prose_symbols(html: str) -> str:
    """Wrap symbol runs in normal prose, leaving pre/code and SVG untouched."""
    parts = re.split(r"(<[^>]+>)", html)
    result: list[str] = []
    stored: dict[str, str] = {}
    skip_depth = 0
    for part in parts:
        if part.startswith("<"):
            name = re.match(r"<\s*(/?)\s*([a-zA-Z][\w-]*)", part)
            if name:
                closing, tag = name.group(1), name.group(2).lower()
                if tag in {"pre", "svg", "script", "style", "code"}:
                    skip_depth += -1 if closing else 1
            result.append(part)
        elif skip_depth:
            result.append(part)
        else:
            # Compact matrices become static SVG before symbol wrapping; the
            # token keeps the generated markup out of the symbol scanner.
            def stash(match: re.Match[str]) -> str:
                svg = expand_flat_matrix(match)
                if svg is None:
                    return match.group(0)
                key = f"@@NLMDF_FLATMAT_{len(stored)}@@"
                stored[key] = svg
                return key

            part = _FLAT_BRACKET_RE.sub(stash, part)
            result.append(_wrap_text_symbols(part))
    body = "".join(result)
    for key, svg in stored.items():
        body = body.replace(key, svg)
    return body


def build_self_contained_html(
    markdown_text: str,
    title: str = "Study notes",
    config: dict[str, Any] | None = None,
) -> tuple[str, dict[str, int]]:
    """Return the offline HTML and the counts observed while building it."""
    config = config or load_config()
    body, toc, formula_count = _markdown_to_html(markdown_text)
    body = _wrap_prose_symbols(body)
    body = _static_circuit_svg(body, config)
    template = (TEMPLATES / "page.html").read_text(encoding="utf-8")
    page = (
        template.replace("{{TITLE}}", html_lib.escape(title))
        .replace("{{KATEX_CSS}}", _inlined_katex_css())
        .replace("{{FONT_CSS}}", _inlined_font_css())
        .replace("{{PRINT_CSS}}", (TEMPLATES / "print.css").read_text(encoding="utf-8"))
        .replace("{{CONTENT}}", body)
        .replace("{{KATEX_JS}}", _safe_script(_KATEX_JS.read_text(encoding="utf-8")))
        .replace("{{MERMAID_JS}}", _safe_script(_MERMAID_JS.read_text(encoding="utf-8")))
        .replace("{{BOOT_JS}}", _safe_script((TEMPLATES / "boot.js").read_text(encoding="utf-8")))
    )
    return page, {
        "formulas_in_markdown": formula_count,
        "toc_entries": 0,
        "html_bytes": len(page.encode("utf-8")),
    }


def print_pdf(
    html_path: str | Path,
    pdf_path: str | Path,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Print the already-built HTML to PDF and return browser-side metrics."""
    config = config or load_config()
    render_cfg = config.get("render", {})
    channel = render_cfg.get("chrome_channel", "chrome")
    margin_inches = float(render_cfg.get("margin_mm", 16)) / 25.4
    launch: dict[str, Any] = {"headless": True}
    if channel:
        launch["channel"] = str(channel)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 1800})
            page.goto(Path(html_path).resolve().as_uri(), wait_until="load")
            page.wait_for_function(
                "window.__NLMDF && window.__NLMDF.ready === true", timeout=120_000
            )
            page.evaluate("() => document.fonts.ready")
            metrics = dict(page.evaluate("() => window.__NLMDF"))
            page.emulate_media(media="print")
            page.pdf(
                path=str(Path(pdf_path).resolve()),
                format=str(config.get("page_size", "A4")),
                print_background=True,
                margin={
                    "top": margin_inches,
                    "right": margin_inches,
                    "bottom": margin_inches,
                    "left": margin_inches,
                },
            )
        finally:
            browser.close()
    return metrics


def render(
    enhanced_path: str | Path,
    pdf_path: str | Path,
    html_path: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run Stage 4: write study-notes.html then study-notes.pdf."""
    config = config or load_config()
    enhanced_file = Path(enhanced_path)
    pdf_file = Path(pdf_path)
    pdf_file.parent.mkdir(parents=True, exist_ok=True)
    if html_path is None:
        html_file = pdf_file.with_name("study-notes.html")
    else:
        html_file = Path(html_path)
    html_file.parent.mkdir(parents=True, exist_ok=True)

    markdown_text = enhanced_file.read_text(encoding="utf-8")
    page, build_counts = build_self_contained_html(
        markdown_text, title=config.get("title", "Study notes"), config=config
    )
    html_file.write_text(page, encoding="utf-8")
    metrics = print_pdf(html_file, pdf_file, config)
    report = {
        "html": str(html_file.resolve()),
        "pdf": str(pdf_file.resolve()),
        "build": build_counts,
        "browser": metrics,
    }
    write_json(pdf_file.with_name("render.meta.json"), report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 4: enhanced.md -> PDF + HTML")
    parser.add_argument("input", help="input enhanced.md")
    parser.add_argument("output", nargs="?", help="output PDF (default: study-notes.pdf)")
    parser.add_argument("--html", help="output HTML (default: alongside PDF)")
    parser.add_argument("--config", help="config.yaml")
    args = parser.parse_args(argv)

    out = Path(args.output) if args.output else Path(args.input).with_name("study-notes.pdf")
    report = render(args.input, out, args.html, load_config(args.config))
    metrics = report["browser"]
    print(
        f"render: {report['pdf']} ({metrics.get('katexCount', 0)} formulas, "
        f"{metrics.get('mermaidBlocks', 0)} diagrams, "
        f"{metrics.get('tables', 0)} tables) -> {report['html']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
