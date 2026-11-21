from __future__ import annotations

import json
from pathlib import Path

from pipeline.common import (
    normalize_math_delimiters,
    normalize_unicode,
    read_json,
    restore_placeholders,
    split_answers,
    strip_citations,
)
from pipeline.clean import clean, discard_artifact_blocks
from pipeline.restore import EXTENDED_MARKER, restore_extended_answer


def test_escaped_math_delimiters_from_markdown_export():
    # NotebookLM markdown exports double the backslash: \\(x\\) and \\[y\\].
    text = "inline \\(x(t)\\) and display \\[\nE = mc^2\n\\] plus \\(a \\\\ b\\)"
    normalized = normalize_math_delimiters(text)
    assert "inline $x(t)$" in normalized
    assert "$$" in normalized and "E = mc^2" in normalized
    assert "\\\\(" not in normalized and "\\\\[" not in normalized
    assert "a \\\\ b" in normalized  # LaTeX commands themselves are untouched


def test_multiline_matrix_becomes_display_math():
    # A matrix in \(...\) spans lines; promotion to $$...$$ is what lets the
    # protection layer and KaTeX see it as one formula.
    text = (
        "Operator \\(U_{\\text{Fredkin}} = \\begin{bmatrix} 1 & 0 \\\\ \n"
        "0 & 1 \\end{bmatrix}\\) acts on two qubits."
    )
    normalized = normalize_math_delimiters(text)
    assert normalized.startswith("Operator $$U_{\\text{Fredkin}}")
    assert normalized.count("$$") == 2
    assert "\\end{bmatrix}$$ acts on two qubits." in normalized


def test_diagram_whitespace_is_untouched_by_normalization():
    diagram = (
        "  prose\u00a0word [1]  \n\n"
        "```text\n"
        "C1 ──■─────\n"
        "\t│\u00a0\u00a0  \n"
        "T  ──[T]────\n"
        "```\n"
    )
    text = strip_citations(normalize_unicode(diagram))
    assert text.startswith("  prose word")  # NBSP folds; trailing space survives
    assert "word   \n" in text  # citation removed, original trailing spaces kept
    assert "[1]" not in text
    assert "\t" not in text and "\u00a0" in text
    assert "    │\u00a0\u00a0  \n" in text  # diagram columns intact
    assert "```text\nC1 ──■─────\n    │\u00a0\u00a0  \nT  ──[T]────\n```" in text


def test_malformed_matrix_summary_block_is_discarded_but_other_fences_keep():
    text = (
        "Before\n"
        "```text\n"
        "  Single-Qubit Gate Matrix Summary:\n"
        "  X =     Y = [0 -i]    Z =     H = 1/√2     S =     T =\n"
        "              [i  0]        [8]                     [0  i]        [0  e^(iπ/4)]\n"
        "```\n"
        "After\n"
        "```text\n"
        "Real circuit ───■───\n"
        "```\n"
    )
    result = discard_artifact_blocks(text)
    assert "Single-Qubit Gate Matrix Summary" not in result
    assert "[0 -i]" not in result
    assert "Before\nAfter" in result
    assert "Real circuit ───■───" in result


def test_titled_fence_with_emoji_or_prose_is_kept():
    emoji_block = (
        "```text\n"
        "  Single-Qubit Gate Matrix Summary: 💡\n"
        "  X =     Y = [0 -i]    Z =     H = 1/√2     S =     T =\n"
        "              [i  0]        [8]                     [0  i]        [0  e^(iπ/4)]\n"
        "```\n"
    )
    prose_block = (
        "```text\n"
        "  Single-Qubit Gate Matrix Summary:\n"
        "  X =     Y = [0 -i]    Z =     H = 1/√2     S =     T =\n"
        "  Verification of H X H = Z follows below.\n"
        "```\n"
    )
    assert discard_artifact_blocks(emoji_block) == emoji_block
    assert discard_artifact_blocks(prose_block) == prose_block


def test_mislabelled_prompt_turn_is_dropped(tmp_path: Path):
    chat = {
        "turns": [
            {
                "role": "assistant",
                "markdown": (
                    "Explain the following topics to me using the textbook with "
                    "easy language in detail:\nIt looks like you might have "
                    "forgotten to list the specific topics after your prompt!"
                    "\nPlease let me know which specific topics you want."
                ),
            },
            {"role": "assistant", "markdown": "Real answer content for the notes."},
        ]
    }
    chat_path = tmp_path / "chat.json"
    chat_path.write_text(json.dumps(chat, ensure_ascii=False), encoding="utf-8")
    clean(chat_path, tmp_path / "clean.md")
    out = (tmp_path / "clean.md").read_text(encoding="utf-8")
    assert "Explain the following topics" not in out
    assert "forgotten to list" not in out
    assert "Real answer content" in out
    assert out.count("nlmdf:answer") == 1
    assert "Section 1" not in out


def test_prompt_glued_in_front_of_answer_is_stripped(tmp_path: Path):
    answer = "UNIT - I: Complete 10-Mark Breakdown\nReal answer content. " + "x" * 250
    chat = {
        "turns": [
            {
                "role": "assistant",
                "markdown": (
                    "no expand more on all of the sub topics as they will be "
                    "given for 10 marks each and give all the needed matrices "
                    "and diagrams\n\n---\n" + answer
                ),
            }
        ]
    }
    chat_path = tmp_path / "chat.json"
    chat_path.write_text(json.dumps(chat, ensure_ascii=False), encoding="utf-8")
    clean(chat_path, tmp_path / "clean.md")
    out = (tmp_path / "clean.md").read_text(encoding="utf-8")
    assert "no expand more" not in out
    assert "UNIT - I" in out
    assert "Real answer content" in out


def test_clean_restores_hadamard_and_gate_proofs_before_counting(tmp_path: Path):
    # This is the post-normalize_unicode form: zero-width spaces are already
    # gone, so the repair must match the flattened text clean.py actually sees.
    markdown = (
        "**D. Hadamard Gate (**H**)** Creates: "
        "H≡21[111−1],H∣0⟩=2∣0⟩+∣1⟩=∣+⟩,H∣1⟩=2∣0⟩−∣1⟩=∣−⟩"
        "**B. Algebraic Gate Identifications & Proofs**\n"
        "```text\nToffoli Gate Decomposition Circuit\n```\n"
    )
    chat = {
        "title": "Repair check",
        "turns": [{"role": "assistant", "markdown": markdown}],
    }
    chat_path = tmp_path / "chat.json"
    chat_path.write_text(json.dumps(chat, ensure_ascii=False), encoding="utf-8")
    meta_path = tmp_path / "clean.meta.json"
    clean(chat_path, tmp_path / "clean.md", meta_path)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    originals = " ".join(meta["placeholders"].values())
    clean_text = (tmp_path / "clean.md").read_text(encoding="utf-8")
    assert r"\frac{1}{\sqrt{2}}" in originals
    assert "Verification of" in clean_text
    assert "H X H = \\frac{1}{\\sqrt{2}}" in originals
    assert meta["expected"]["formulas"] >= 5


def test_extended_answer_restores_dropped_vectors_and_examples(tmp_path: Path):
    # Chrome's copy of this answer has no KaTeX annotations: every bullet list
    # containing LaTeX disappears and only flattened glyphs survive.
    markdown = (
        "## UNIT - I (Extended): Foundational Mathematics, Physics, and Biology\n"
        "SECTION 1: BACKGROUND MATHEMATICS 10 Marks\n"
        "A. Dirac Bra-Ket Notation and State Vectors\n"
        "B. Vector and Operator Multiplication\n"
        "Given the state ∣ψ⟩ = α∣0⟩ + β∣1⟩:\n"
        "💡 **Next Steps**: Would you like to continue?\n"
    )
    chat = {
        "title": "Extended restore check",
        "turns": [{"role": "assistant", "markdown": markdown, "index": 11}],
    }
    chat_path = tmp_path / "chat.json"
    chat_path.write_text(json.dumps(chat, ensure_ascii=False), encoding="utf-8")
    meta_path = tmp_path / "clean.meta.json"
    clean(chat_path, tmp_path / "clean.md", meta_path)

    out = (tmp_path / "clean.md").read_text(encoding="utf-8")
    manifest = json.loads(meta_path.read_text(encoding="utf-8"))
    originals = " ".join(manifest["placeholders"].values())
    assert out.startswith("<!-- nlmdf:answer index=11 ordinal=1 -->\n# " + EXTENDED_MARKER)
    assert "Ket Vector" in out
    assert "Worked Dual Computation" in out
    assert r"\begin{bmatrix}" in originals
    assert r"\langle\alpha|\beta\rangle" in originals
    assert "Next Steps" in out
    assert "∣ψ⟩ = α∣0⟩" not in out


def test_intact_extended_answer_is_not_overwritten():
    intact = (
        EXTENDED_MARKER + "\n"
        + r"\begin{bmatrix}" * 8 + "\n"
        + "keep this exact wording"
    )
    assert restore_extended_answer(intact) == intact


def test_user_turns_are_dropped_and_answers_ordered(small_chat: Path, tmp_path: Path):
    manifest = clean(small_chat, tmp_path / "clean.md", config={"strip_citations": True})
    answers = manifest["answers"]
    assert [answer["index"] for answer in answers] == [1, 2]
    assert [answer["ordinal"] for answer in answers] == [1, 2]
    assert "Please explain this" not in (tmp_path / "clean.md").read_text()


def test_math_and_code_are_protected(small_chat: Path, tmp_path: Path):
    manifest = clean(small_chat, tmp_path / "clean.md")
    clean_text = (tmp_path / "clean.md").read_text(encoding="utf-8")
    assert "$" not in clean_text
    assert "@@NLMDF_MATH_" in clean_text
    assert "@@NLMDF_CODEINLINE_" in clean_text
    assert any("$\\alpha \\le 1$" in value for value in manifest["placeholders"].values())


def test_placeholders_are_unique_across_answers(small_chat: Path, tmp_path: Path):
    manifest = clean(small_chat, tmp_path / "clean.md")
    first, second = manifest["answers"]
    assert not (set(first["placeholders"]) & set(second["placeholders"]))
    for answer in split_answers((tmp_path / "clean.md").read_text()):
        restored = restore_placeholders(answer["text"], manifest["placeholders"])
        assert "@@NLMDF_" not in restored
    assert "`code_0`" in restore_placeholders(
        first["original_text"], manifest["placeholders"]
    )
    assert "`code_1`" in restore_placeholders(
        second["original_text"], manifest["placeholders"]
    )


def test_citations_stripped_only_when_configured(small_chat: Path, tmp_path: Path):
    kept = clean(small_chat, tmp_path / "kept.md", config={"strip_citations": False})
    removed = clean(small_chat, tmp_path / "removed.md", config={"strip_citations": True})
    assert "[1]" in kept["answers"][1]["original_text"]
    assert "[1]" not in removed["answers"][1]["original_text"]


def test_expected_counts_read_from_source(small_chat: Path, tmp_path: Path):
    manifest = clean(small_chat, tmp_path / "clean.md")
    assert manifest["expected"] == {"formulas": 1, "tables": 1, "mermaid": 0}
    assert read_json(tmp_path / "clean.meta.json") == manifest
