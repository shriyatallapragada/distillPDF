"""Shared helpers for the four pipeline stages.

Nothing in here calls a model or a browser; it is pure text/JSON handling so
each stage stays independently testable.
"""

from __future__ import annotations

import html
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ANSWER_START_RE = re.compile(
    r"<!--\s*nlmdf:answer\s+index=(\d+)\s+ordinal=(\d+)\s*-->"
)
ANSWER_END = "<!-- nlmdf:end -->"

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "qwen3:8b",
    "ollama_url": "http://localhost:11434",
    "strip_citations": True,
    "page_size": "A4",
    "enhance": {
        "enabled": True,
        "temperature": 0.1,
        "timeout_seconds": 120,
        "no_think": True,
        "user_instructions": "",
    },
    "render": {
        "chrome_channel": "chrome",
        "margin_mm": 16,
        "body_font": "Inter",
    },
}


# ---------------------------------------------------------------------------
# Config / JSON
# ---------------------------------------------------------------------------
def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config.yaml over the built-in defaults."""
    if path is None:
        return deepcopy(DEFAULT_CONFIG)
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config must be a mapping: {config_path}")
    return _deep_merge(DEFAULT_CONFIG, loaded)


def read_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


# ---------------------------------------------------------------------------
# chat.json handling
# ---------------------------------------------------------------------------
def load_chat(path: str | Path) -> dict[str, Any]:
    """Load chat JSON or preserve a Markdown answer as a single turn."""
    source = Path(path)
    if source.suffix.lower() in {".md", ".markdown"}:
        return {
            "title": source.stem,
            "source": f"markdown:{source.resolve()}",
            "turns": [{"role": "assistant", "markdown": source.read_text(encoding="utf-8")}],
        }
    data = read_json(source)
    if isinstance(data, list):
        return {"turns": data}
    if not isinstance(data, dict) or "turns" not in data:
        raise ValueError(
            f"{path} must contain a 'turns' array (or be a bare array of turns)"
        )
    return data


def assistant_turns(chat: dict[str, Any]) -> list[dict[str, Any]]:
    """User turns are discarded in plain code, never by the model."""
    turns = []
    for position, turn in enumerate(chat.get("turns", [])):
        if not isinstance(turn, dict):
            continue
        if str(turn.get("role", "")).lower() != "assistant":
            continue
        item = dict(turn)
        item.setdefault("index", position)
        item["markdown"] = str(item.get("markdown", ""))
        turns.append(item)
    return turns


# ---------------------------------------------------------------------------
# Text normalization (Stage 2, deterministic)
# ---------------------------------------------------------------------------
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
_SPACE_CHARS = {
    "\u00a0": " ",  # no-break space
    "\u202f": " ",  # narrow no-break space
    "\u2009": " ",  # thin space
    "\u2007": " ",  # figure space
    "\u3000": " ",  # ideographic space
}
# Some exports escape the backslash itself (\\( ... \\)); accept one or more.
_LATEX_PARENS = re.compile(r"\\+\[(.+?)\\+\]", re.S)
_LATEX_INLINE = re.compile(r"\\+\((.+?)\\+\)", re.S)
# An inline $...$ that contains a newline or a LaTeX environment (bmatrix,
# aligned, cases, ...) is really display math. It must be promoted to $$...$$
# before protection/rendering: the inline matchers deliberately stop at \n.
_INLINE_MATH_ANY = re.compile(
    r"(?<!\\$)(?<!\\\\)\\$(?!\\$)((?:\\[$]|[^$])+?)(?<!\\\\)\\$(?!\\$)",
    re.S,
)
_ENV_MATH_RE = re.compile(r"\\begin\{[^{}]+\}")
_CITATION_RES = (
    # Keep compact matrices like ``[0110]``: citations use 1-3 digit numbers,
    # optionally in a short comma/dash list.
    re.compile(r"\[\s*\d{1,3}(?:\s*(?:,|–|-)\s*\d{1,3})*\s*\]"),
    re.compile(r"【\s*\d+\s*】"),
    re.compile(r"\[\s*(?:citation|source)(?:\s+needed)?\s*\]", re.I),
)
_BULLET_RE = re.compile(r"(?m)^([ \t]*)[*+-][ \t]+(.*)$")

# Only whole, known conversational replies qualify for automatic removal.
_NLM_INTRO_RE = re.compile(
    r"(?:hi|hello|hey)[.!]?[ \t]+how can i help(?: you)?(?: today)?[?]?",
    re.I,
)
_NLM_OUTRO_RE = re.compile(
    r"hope (?:this|that) helps[.!]?|"
    r"let me know if you (?:need anything else|have any questions)[.!]?",
    re.I,
)


def is_notebooklm_boilerplate(text: str, where: str) -> bool:
    """Match an entire generic greeting or closing reply."""
    pattern = _NLM_INTRO_RE if where == "start" else _NLM_OUTRO_RE
    return bool(pattern.fullmatch(text.strip()))


_FENCE_BLOCK_RE = re.compile(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$")


def _outside_fences(text: str, transform) -> str:
    """Apply ``transform`` only to prose; fenced blocks stay byte-for-byte."""
    pieces: list[str] = []
    cursor = 0
    for match in _FENCE_BLOCK_RE.finditer(text):
        pieces.append(transform(text[cursor : match.start()]))
        pieces.append(match.group(0))
        cursor = match.end()
    pieces.append(transform(text[cursor:]))
    return "".join(pieces)


def _inside_fences(text: str, transform) -> str:
    """Apply ``transform`` only to fenced code/ASCII-diagram blocks."""
    return _FENCE_BLOCK_RE.sub(lambda match: transform(match.group(0)), text)


def normalize_unicode(text: str) -> str:
    """Fix prose whitespace artifacts; keep diagram/code whitespace intact.

    Non-breaking spaces are folded to ordinary spaces in prose so lines can
    wrap, but are preserved inside fenced blocks where they carry alignment.
    Tabs become four spaces inside fences (matching ``tab-size: 4`` in CSS).
    Leading/trailing spaces and blank lines are left for the Markdown parser.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    def prose(part: str) -> str:
        part = part.translate(_ZERO_WIDTH)
        for source, target in _SPACE_CHARS.items():
            part = part.replace(source, target)
        return _BULLET_RE.sub(r"\1- \2", part)

    text = _outside_fences(text, prose)
    return _inside_fences(text, lambda block: block.replace("\t", "    "))


def _math_fence(body: str) -> str:
    body = body.strip()
    if "\n" in body or _ENV_MATH_RE.search(body):
        return f"$${body}$$"
    return f"${body}$"


def normalize_math_delimiters(text: str) -> str:
    r"""Fold \(..\) / \[..\] into $ / $$.

    Multiline or environment-based expressions become display math so the
    downstream protection and KaTeX matchers can handle them. A matrix in a
    heading such as ``\begin{bmatrix}...\end{bmatrix}`` is the common case.
    """
    text = _LATEX_PARENS.sub(lambda m: f"$${m.group(1).strip()}$$", text)
    text = _LATEX_INLINE.sub(lambda m: _math_fence(m.group(1)), text)
    text = _INLINE_MATH_ANY.sub(lambda m: _math_fence(m.group(1)), text)
    return text


def strip_citations(text: str) -> str:
    """Drop prose citations while preserving math, code and indentation."""

    def prose(part: str) -> str:
        part, protected = protect_content(part)
        for pattern in _CITATION_RES:
            part = pattern.sub("", part)
        # Only touches runs between visible characters: indentation, trailing
        # spaces and fenced diagrams are never rewritten.
        part = re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", part)
        return restore_placeholders(part, protected)

    return _outside_fences(text, prose)


def word_count(text: str) -> int:
    """Whitespace-token count; stable across placeholder protection."""
    return len(text.split())


# ---------------------------------------------------------------------------
# Placeholder protection
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$")
_MATH_BLOCK_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
_INLINE_CODE_RE = re.compile(r"`+[^`\n]+`+")
_INLINE_MATH_RE = re.compile(r"(?<!\\)\$([^\n$]+?)(?<!\\)\$")


def protect_content(
    text: str, counts: dict[str, int] | None = None
) -> tuple[str, dict[str, str]]:
    """Swap math/code for inert tokens so no later step can alter them.

    Pass a shared ``counts`` dict when protecting several answers: tokens must
    stay globally unique or a later answer would overwrite an earlier one in
    the shared manifest.
    """
    mapping: dict[str, str] = {}
    if counts is None:
        counts = {"MATH": 0, "CODE": 0, "CODEINLINE": 0}

    def token(kind: str, original: str) -> str:
        key = f"@@NLMDF_{kind}_{counts[kind]}@@"
        counts[kind] += 1
        mapping[key] = original
        return key

    text = _FENCE_RE.sub(lambda m: token("CODE", m.group(0)), text)
    text = _MATH_BLOCK_RE.sub(lambda m: token("MATH", m.group(0)), text)
    text = _INLINE_CODE_RE.sub(lambda m: token("CODEINLINE", m.group(0)), text)
    text = _INLINE_MATH_RE.sub(lambda m: token("MATH", m.group(0)), text)
    return text, mapping


def restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    for key, original in mapping.items():
        text = text.replace(key, original)
    return text


def placeholder_keys(text: str) -> list[str]:
    return re.findall(r"@@NLMDF_[A-Z]+_\d+@@", text)


# ---------------------------------------------------------------------------
# Section markers in clean.md
# ---------------------------------------------------------------------------
def format_answer(index: int, ordinal: int, text: str) -> str:
    # No .strip(): a diagram can legitimately start with spaces or a blank line.
    return (
        f"<!-- nlmdf:answer index={index} ordinal={ordinal} -->\n"
        f"{text}\n"
        f"{ANSWER_END}"
    )


def split_answers(text: str) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        match = ANSWER_START_RE.search(line)
        if match:
            if current is not None:
                current["text"] = "\n".join(buffer)
                answers.append(current)
            current = {"index": int(match.group(1)), "ordinal": int(match.group(2))}
            buffer = []
            continue
        if line.strip() == ANSWER_END and current is not None:
            current["text"] = "\n".join(buffer)
            answers.append(current)
            current = None
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    if current is not None:
        current["text"] = "\n".join(buffer)
        answers.append(current)
    return answers


# ---------------------------------------------------------------------------
# Math / markdown counting and plain text extraction (used by validate.py)
# ---------------------------------------------------------------------------
_FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _without_fences(text: str) -> str:
    """Drop fenced code blocks so their $ signs are not counted as math."""
    lines: list[str] = []
    inside = False
    marker = ""
    for line in text.splitlines():
        stripped = line.strip()
        match = _FENCE_LINE_RE.match(line)
        token = match.group(1)[0] if match else ""
        if not inside and token:
            inside, marker = True, token
            continue
        if inside and stripped.startswith(marker * 3):
            inside, marker = False, ""
            continue
        if not inside:
            lines.append(line)
    return "\n".join(lines)


def count_math(text: str) -> int:
    """Count $...$ / $$...$$ occurrences outside fenced code blocks."""
    body = _without_fences(text)
    blocks = re.findall(r"\$\$(.+?)\$\$", body, re.S)
    body = re.sub(r"\$\$(.+?)\$\$", " ", body, flags=re.S)
    inline = re.findall(r"(?<!\\)\$([^\n$]+?)(?<!\\)\$", body)
    return len(blocks) + len(inline)


def plain_text_from_markdown(text: str) -> str:
    """Best-effort renderable plain text for the word-count/symbol checks."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"(?ms)^(`{3,}|~{3,})[^\n]*\n(.*?)^\1[ \t]*$", r"\2", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"</?[^>]+>", " ", text)
    text = re.sub(r"\$\$|\$|\\\(|\\\)|\\\[|\\\]", " ", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s{0,3}>+\s?", "", text)
    text = re.sub(r"(?m)^\s{0,3}(?:\d+\.|[-*+])\s+", "", text)
    text = re.sub(r"(?m)^[\s:|-]*-{3,}[\s:|-]*$", " ", text)  # table rule
    text = text.replace("|", " ")
    text = re.sub(r"[*_~`]", "", text)
    text = html.unescape(text)
    # NBSP is spacing, not a glyph to verify: PDF extractors normalize it to
    # an ordinary space even when the source diagram kept it for alignment.
    text = text.replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def html_escape_math(source: str) -> str:
    return html.escape(source, quote=False)
