"""Compare visible content in the initial Markdown and exported documents."""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

from .common import normalize_math_delimiters, normalize_unicode, strip_citations
from .render import _markdown_to_html, _static_circuit_svg, _wrap_prose_symbols

_BLOCK_TAGS = {"p", "li", "pre", "td", "th", "blockquote", "br",
               "h1", "h2", "h3", "h4", "h5", "h6"}
_IGNORED_CHARS = str.maketrans({
    "\u00ad": None, "\u200b": None, "\ufeff": None,
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
})


def _characters(text: str) -> str:
    return "".join(unicodedata.normalize("NFC", text.translate(_IGNORED_CHARS)).split())


class _VisibleBlocks(HTMLParser):
    def __init__(self, document: bool) -> None:
        super().__init__()
        self.document = document
        self.active = not document
        self.skipping: str | None = None
        self.parts: list[str] = []
        self.blocks: list[str] = []

    def boundary(self) -> None:
        if self.parts:
            text = "".join(self.parts).strip()
            if text:
                self.blocks.append(text)
            self.parts.clear()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "main" and self.document:
            self.active = True
        if not self.active or self.skipping:
            return
        classes = (dict(attrs).get("class") or "").split()
        if tag in {"script", "style"} or tag == "code" and "language-mermaid" in classes:
            self.skipping = tag
        elif tag in _BLOCK_TAGS:
            self.boundary()
        elif tag == "img":
            self.parts.append(dict(attrs).get("alt") or "")

    def handle_endtag(self, tag: str) -> None:
        if self.skipping:
            if self.skipping == tag:
                self.skipping = None
            return
        if self.active and (tag in _BLOCK_TAGS or tag == "main"):
            self.boundary()
        if tag == "main" and self.document:
            self.active = False

    def handle_data(self, data: str) -> None:
        if self.active and not self.skipping:
            self.parts.append(data)


def _visible_blocks(html: str, *, document: bool = False) -> list[str]:
    parser = _VisibleBlocks(document)
    parser.feed(html)
    parser.close()
    parser.boundary()
    return parser.blocks


def compare_source(
    markdown: str, pdf_text: str, html: str | None, *, remove_citations: bool = True,
    config: dict | None = None,
) -> dict:
    """Match visible Markdown blocks in order, allowing generated additions."""
    source = normalize_math_delimiters(normalize_unicode(markdown))
    if remove_citations:
        source = strip_citations(source)
    # The expected text uses the project's Markdown and LaTeX notation rules.
    # Compare it with the actual output, rather than enhanced Markdown.
    body, _, _ = _markdown_to_html(source)
    body = _static_circuit_svg(_wrap_prose_symbols(body), config or {})
    blocks = _visible_blocks(body)
    expected = [(block, _characters(block)) for block in blocks]
    outputs = {"pdf": pdf_text}
    if html is not None:
        outputs["html"] = "\n".join(_visible_blocks(html, document=True))

    results = {}
    for name, output in outputs.items():
        text = _characters(output)
        offset = 0
        matched_characters = 0
        missing = []
        for block, characters in expected:
            if not characters:
                continue
            index = text.find(characters, offset)
            if index < 0:
                missing.append(" ".join(block.split())[:200])
            else:
                offset = index + len(characters)
                matched_characters += len(characters)
        results[name] = {
            "expected_blocks": len(expected),
            "unmatched_blocks": len(missing),
            "expected_characters": sum(len(characters) for _, characters in expected),
            "matched_block_characters": matched_characters,
            "examples": missing[:12],
        }
    return results
