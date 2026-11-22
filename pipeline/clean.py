"""Stage 2 -- deterministic cleanup. No model is called in this stage.

Reads ``chat.json`` and writes ``clean.md`` plus a ``clean.meta.json`` sidecar
holding the protected math/code originals and the per-answer invariants that
Stage 3 must respect.

    python -m pipeline.clean sample/chat.json sample/out/clean.md --config config.yaml
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

from .common import (
    assistant_turns,
    count_math,
    format_answer,
    is_notebooklm_boilerplate,
    load_chat,
    load_config,
    normalize_math_delimiters,
    normalize_unicode,
    protect_content,
    strip_citations,
    word_count,
    write_json,
)
from .restore import restore_extended_answer
from .structure import fix_hadamard_fraction, restore_gate_verifications

_TABLE_RULE_RE = re.compile(
    r"(?m)^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
_MERMAID_FENCE_RE = re.compile(r"(?ms)^(`{3,}|~{3,})\s*mermaid\s*\n.*?^\1[ \t]*$")

# NotebookLM occasionally emits a badly spaced "Single-Qubit Gate Matrix
# Summary" inside a fenced block. Its rows do not line up with the headings,
# so the user asked for that one block to be discarded. Match only that titled
# fence; genuine answers and any other fenced content are left untouched.
_MATRIX_SUMMARY_FENCE_RE = re.compile(
    r"(?ms)^(`{3,}|~{3,})[^\n]*\n"
    r"(?:(?!^\1[ \t]*$).)*?Single-Qubit Gate Matrix Summary"
    r"(?:(?!^\1[ \t]*$).)*?^\1[ \t]*$\n?"
)
_ARTIFACT_HEADER_RE = re.compile(
    r"^\s*X\s*=.*\bY\s*=.*\bZ\s*=.*\bH\s*=.*\bS\s*=.*\bT\s*=\s*$"
)
_ARTIFACT_ROW_RE = re.compile(r"^[\s\[\]0-9eEiIπ√+\-−/^().]+$")
# Emoji and decorative symbols are a strong sign of a genuine assistant reply.
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")

# NotebookLM sometimes labels the user's own message as an assistant turn, or
# prepends it to the real answer. Drop only those narrow, recognisable cases.
_USER_PROMPT_START_RE = re.compile(
    r"^\s*(?:no[, ]+|yes[, ]+|ok(?:ay)?[, ]+)?"
    r"(?:explain|expand|please|can you|could you|give|list|write|generate|summarize|describe)\b",
    re.I,
)
_PROMPT_CLARIFICATION_RE = re.compile(
    r"(forgotten to list|please let me know which|if you'd like, i can)",
    re.I,
)
_PROMPT_PREFIX_RE = re.compile(r"^([^\n]{1,400})\n\s*---\s*\n(?=\S)")


def is_user_prompt_turn(text: str) -> bool:
    """True for a standalone prompt that Chrome mislabelled as an answer."""
    return bool(_USER_PROMPT_START_RE.match(text) and _PROMPT_CLARIFICATION_RE.search(text))


def strip_leading_user_prompt(text: str) -> str:
    """Remove a prompt prepended to an answer before its first ``---`` rule."""
    match = _PROMPT_PREFIX_RE.match(text)
    if not match or not _USER_PROMPT_START_RE.match(match.group(1)):
        return text
    remainder = text[match.end() :]
    return remainder if len(remainder) > 200 else text


def _append_missing_formulas(text: str, latex: list[str]) -> str:
    """The Chrome extension reads KaTeX's <annotation>; honour it verbatim.

    If the markdown already contains the formula source, leave it where it is.
    Otherwise append the unmatched sources as display math so nothing the
    extension recovered is lost. No extra header is added: only the formula
    sources themselves are appended, preserving the user's text verbatim.
    """
    missing = []
    for formula in latex:
        formula = str(formula).strip()
        if formula and formula not in text:
            missing.append(formula)
    if missing:
        text += "\n\n" + "\n\n".join(f"$${formula}$$" for formula in missing)
    return text


def discard_artifact_blocks(text: str) -> str:
    """Drop only the exact malformed matrix-summary fence.

    The block must contain the known title, the mangled ``X = Y = Z ...``
    header, and nothing but matrix-like rows. Anything else inside the fence
    (an emoji, prose, another answer) makes it genuine content and it is kept.
    """

    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        if _EMOJI_RE.search(block):
            return block
        lines = block.splitlines()
        content = lines[1:-1] if len(lines) >= 2 else []
        nonempty = [line for line in content if line.strip()]
        titled = [line for line in nonempty if "Single-Qubit Gate Matrix Summary" in line]
        if len(titled) != 1:
            return block
        remainder = [line for line in nonempty if line is not titled[0]]
        if not 2 <= len(remainder) <= 3:
            return block
        if not _ARTIFACT_HEADER_RE.fullmatch(remainder[0]):
            return block
        if not all(_ARTIFACT_ROW_RE.fullmatch(line) for line in remainder[1:]):
            return block
        return ""

    return _MATRIX_SUMMARY_FENCE_RE.sub(replace, text)


def clean(
    chat_path: str | Path,
    clean_path: str | Path,
    meta_path: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run Stage 2 and return the manifest that was written."""
    cfg = config or load_config()
    chat = load_chat(chat_path)
    turns = assistant_turns(chat)
    if not turns:
        raise ValueError(f"No assistant turns found in {chat_path}")

    clean_file = Path(clean_path)
    clean_file.parent.mkdir(parents=True, exist_ok=True)
    if meta_path is None:
        meta_path = clean_file.with_name("clean.meta.json")
    meta_file = Path(meta_path)

    sections: list[str] = []
    source_answers: list[str] = []
    answers_meta: list[dict[str, Any]] = []
    placeholder_counts = {"MATH": 0, "CODE": 0, "CODEINLINE": 0}
    all_placeholders: dict[str, str] = {}
    expected_formulas = 0
    expected_tables = 0
    expected_mermaid = 0
    list_item_shortfalls: list[dict[str, int]] = []

    total = len(turns)
    for ordinal, turn in enumerate(turns, start=1):
        index = int(turn.get("index", ordinal))
        text = normalize_unicode(str(turn.get("markdown", "")))
        text = discard_artifact_blocks(text)
        # Drop the user's own prompt when Chrome mislabels it as an assistant
        # turn, or when it is glued in front of the real answer.
        if ordinal == 1 and total > 1 and is_user_prompt_turn(text):
            text = ""
        else:
            text = strip_leading_user_prompt(text)
        source_text = text
        # Restore known answer fragments before math is protected/counted, so
        # validation expects the formulas that will actually be rendered.
        text = restore_extended_answer(text)
        text = restore_gate_verifications(text)
        text = fix_hadamard_fraction(text)
        text = normalize_math_delimiters(text)
        if cfg.get("strip_citations", True):
            text = strip_citations(text)

        # Strip NotebookLM intro/outro boilerplate only from the first/last
        # assistant turn, and only if the whole reply matches a known phrase.
        if ordinal == 1 and is_notebooklm_boilerplate(text, "start"):
            text = ""
        if ordinal == total and is_notebooklm_boilerplate(text, "end"):
            text = ""

        text = _append_missing_formulas(text, list(turn.get("latex") or []))
        captured_items = turn.get("list_items")
        if isinstance(captured_items, int) and captured_items > 0:
            cleaned_items = sum(
                token.type == "list_item_open" for token in MarkdownIt("commonmark").parse(text)
            )
            if cleaned_items < captured_items:
                list_item_shortfalls.append(
                    {"index": index, "expected": captured_items, "actual": cleaned_items}
                )
        # A dropped prompt/boilerplate turn must not leave an empty section.
        if not text.strip():
            continue
        source_answers.append(source_text)

        expected_formulas += count_math(text)
        expected_tables += len(_TABLE_RULE_RE.findall(text))
        expected_mermaid += len(_MERMAID_FENCE_RE.findall(text))

        # Add a generic heading only when the answer has none; enhance.py
        # numbers and titles the first heading in either case.
        if not re.match(r"^\s{0,3}#{1,6}\s+\S", text):
            text = f"## Section {ordinal}\n\n{text}"
        protected, mapping = protect_content(text, placeholder_counts)
        all_placeholders.update(mapping)

        sections.append(format_answer(index, ordinal, protected))
        answers_meta.append(
            {
                "index": index,
                "ordinal": ordinal,
                "word_count": word_count(protected),
                "original_text": protected,
                "placeholders": sorted(mapping),
                "latex": list(turn.get("latex") or []),
            }
        )

    clean_file.write_text("\n\n".join(sections) + "\n", encoding="utf-8")

    manifest = {
        "source": chat.get("source", ""),
        "title": chat.get("title", ""),
        "user_instructions": str(chat.get("user_instructions", "")),
        "chat_path": str(Path(chat_path).resolve()),
        "strip_citations": bool(cfg.get("strip_citations", True)),
        "source_markdown": "\n\n---\n\n".join(source_answers),
        "answers": answers_meta,
        "placeholders": all_placeholders,
        "list_item_shortfalls": list_item_shortfalls,
        "expected": {
            "formulas": expected_formulas,
            "tables": expected_tables,
            "mermaid": expected_mermaid,
        },
    }
    write_json(meta_file, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 2: chat.json -> clean.md")
    parser.add_argument("chat", help="input chat.json")
    parser.add_argument("output", nargs="?", help="output clean.md (default: <chat dir>/clean.md)")
    parser.add_argument("--meta", help="output manifest (default: <output dir>/clean.meta.json)")
    parser.add_argument("--config", help="config.yaml")
    args = parser.parse_args(argv)

    out = Path(args.output) if args.output else Path(args.chat).parent / "clean.md"
    manifest = clean(args.chat, out, args.meta, load_config(args.config))
    print(
        f"clean: {len(manifest['answers'])} answers -> {out} "
        f"(formulas={manifest['expected']['formulas']}, "
        f"tables={manifest['expected']['tables']}, "
        f"mermaid={manifest['expected']['mermaid']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
