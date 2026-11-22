"""Deterministic structural repairs for NotebookLM markdown exports.

NotebookLM's DOM occasionally collapses adjacent blocks when it is copied:

* a Markdown table is emitted directly after a numbered line, so markdown-it
  treats it as lazy paragraph continuation instead of a table;
* lettered subheadings (``**A. Title**``) are emitted with no line break before
  or after them, so the ``**`` markers render literally instead of as bullets.

These helpers restore that structure without changing any words. They run on
the Markdown text, never inside fenced code/diagram blocks.
"""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$")

_TABLE_ROW_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*$")
_TABLE_SEP_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*"
    r"(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$"
)
# NotebookLM's copy truncates inline math at a bra-ket pipe. The cell is left
# with a dangling, doubled delimiter (``\\(`` or ``\\(\\frac{``) whose content
# is already gone. Drop just that fragment so the cell reads cleanly.
_DANGLING_MATH_RE = re.compile(r"(?:\\\\\(\\\\frac\{|\\\\\()(?=[ \t]*(?:\||$))")

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# A lettered label may contain nested bold spans, e.g.
# ``**D. Hadamard Gate (**H**)**`` or ``**A. CNOT (**U**)**``. The body pattern
# accepts those complete ``**...**`` pairs but still lets the final ``**`` end
# the label. Looking only at one line keeps a later ``**emphasis**`` in the same
# paragraph from being swallowed into the label.
_LABEL_BODY = r"(?:[^*]|\*(?!\*)|\*\*(?:(?!\*\*)[^a-z])+\*\*)*"
_LABEL_CORE = r"\*\*([" + _LETTERS + r"]\." + _LABEL_BODY + r")\*\*(?=\s|$|[A-Za-z])[ \t]*"
_LABEL_RE = re.compile(r"^(\s*)(#{1,6}\s+)?" + _LABEL_CORE)
_LABEL_INLINE_RE = re.compile(_LABEL_CORE)

_BLOCK_START_RE = re.compile(
    r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\||>{1,}\s|`{3,}|~{3,}|<!--|---+\s*$)"
)
# A line that is already a real list item (possibly nested) must keep its
# marker and indentation. Only bare bold labels are converted into bullets.
_EXISTING_LIST_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+")
_BOLD_ITEM_RE = re.compile(r"^([ ]{0,3})(\*\*[^*\n]+\*\*:?)\s*(.*)$")

# The Chrome copy of the Bloch-sphere paragraph loses the "/" in ``θ/2`` and
# the "^" on ``e^(iφ)``. Repair only that known sentence, never a diagram.
_GREEK = "αβγδϵεζηθικλμνξοπρστυφϕχψω"
_MANGLED_EXPONENT_RE = re.compile(r"\bei([" + _GREEK + r"])")

# Chrome's copy drops the fraction bar and radical in the Hadamard paragraph,
# leaving "H≡2 1 [...], H|0⟩=2 |0⟩+...". Restore the original formula as real
# math so the reader sees 1/√2 and "/√2" instead of a bare "2".
# normalize_unicode removes zero-width spaces before this runs, so accept both
# the raw export and the cleaned form with ordinary/no spacing.
_HADAMARD_GAP = "[\u200b \t]*"
_HADAMARD_MANGLED_RE = re.compile(
    "H≡2" + _HADAMARD_GAP + "1" + _HADAMARD_GAP
    + r"\[11" + _HADAMARD_GAP + r"1−1" + _HADAMARD_GAP + r"\],"
    "H∣0⟩=2" + _HADAMARD_GAP + r"∣0⟩\+∣1⟩" + _HADAMARD_GAP + r"=∣\+⟩,"
    "H∣1⟩=2" + _HADAMARD_GAP + r"∣0⟩−∣1⟩" + _HADAMARD_GAP + r"=∣−⟩"
)
_HADAMARD_FIXED = (
    r"$H \equiv \frac{1}{\sqrt{2}}\begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix},"
    r"\quad H|0\rangle = \frac{|0\rangle + |1\rangle}{\sqrt{2}} = |+\rangle,"
    r"\quad H|1\rangle = \frac{|0\rangle - |1\rangle}{\sqrt{2}} = |-\rangle$"
)

# Re-exporting a NotebookLM answer sometimes cuts off the algebraic proofs even
# though the section heading and the Toffoli diagram survive. Restore that known
# block only when the heading and diagram are both present and the proof is not.
_VERIFICATION_ANCHOR = "**B. Algebraic Gate Identifications & Proofs**"
_VERIFICATION_MARKER = "Verification of $H X H = Z$"
_TOFFOLI_ANCHOR = "Toffoli Gate Decomposition Circuit"
_GATE_VERIFICATIONS = (
    "\n\nVerification of $H X H = Z$: $$H X H = \\frac{1}{\\sqrt{2}}"
    "\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix} "
    "\\begin{bmatrix} 0 & 1 \\\\ 1 & 0 \\end{bmatrix} "
    "\\frac{1}{\\sqrt{2}}\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix} "
    "= \\frac{1}{2}\\begin{bmatrix} 1 & 1 \\\\ -1 & 1 \\end{bmatrix} "
    "\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix} "
    "= \\begin{bmatrix} 1 & 0 \\\\ 0 & -1 \\end{bmatrix} = Z$$\n"
    "Verification of $H Z H = X$: $$H Z H = \\frac{1}{\\sqrt{2}}"
    "\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix} "
    "\\begin{bmatrix} 1 & 0 \\\\ 0 & -1 \\end{bmatrix} "
    "\\frac{1}{\\sqrt{2}}\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix} "
    "= \\frac{1}{2}\\begin{bmatrix} 1 & -1 \\\\ 1 & 1 \\end{bmatrix} "
    "\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix} "
    "= \\begin{bmatrix} 0 & 1 \\\\ 1 & 0 \\end{bmatrix} = X$$\n"
)


def _outside_fences(text: str, transform) -> str:
    """Apply ``transform`` to prose only; fenced blocks stay byte-for-byte."""
    pieces: list[str] = []
    cursor = 0
    for match in _FENCE_RE.finditer(text):
        pieces.append(transform(text[cursor : match.start()]))
        pieces.append(match.group(0))
        cursor = match.end()
    pieces.append(transform(text[cursor:]))
    return "".join(pieces)


def fix_tables(text: str) -> str:
    """Insert a blank line before a table that follows a non-blank line.

    A table header immediately after ``4. Comparison Table ...`` is otherwise
    swallowed into the ordered-list item as plain text.
    """

    def work(part: str) -> str:
        lines = part.split("\n")
        out: list[str] = []
        for index, line in enumerate(lines):
            is_table_row = bool(_TABLE_ROW_RE.match(line))
            if (
                is_table_row
                and index + 1 < len(lines)
                and _TABLE_SEP_RE.match(lines[index + 1])
            ):
                if out and out[-1].strip():
                    out.append("")
            if is_table_row:
                line = _DANGLING_MATH_RE.sub("", line)
            out.append(line)
        return "\n".join(out)

    return _outside_fences(text, work)


def _bulletize_bold_labels(part: str) -> str:
    """Turn a bold lettered label into a real Markdown bullet.

    Both exported forms are handled:

    * ``**A. Title**description`` (label and prose on the same line);
    * ``#### **A. Title**`` followed by prose/matrices on the next lines.

    The exported chat often concatenates labels onto the previous heading line
    (``... (2.5 Marks)**A. Title**description``), so an inline path splits those
    too. Unrelated numbered items such as ``3. **Toffoli Construction
    Decomposition**:`` are left untouched. Nested bold inside the label
    (``(**H**)``) is included, while a later emphasis span (``**universal**``)
    is never absorbed.
    """

    def split_inline(line: str) -> str:
        def replace(match: re.Match[str]) -> str:
            label = match.group(1).replace("**", "").strip()
            return f"\n\n- {label}\n  " if label else match.group(0)

        return _LABEL_INLINE_RE.sub(replace, line)

    lines = part.split("\n")
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if _EXISTING_LIST_RE.match(line):
            result.append(line)
            index += 1
            continue
        match = _LABEL_RE.match(line)
        bold_item = _BOLD_ITEM_RE.match(line) if not match else None
        if match:
            indent, heading, raw_label = match.groups()
            label = raw_label.replace("**", "").strip()
            rest = line[match.end() :].strip()
        elif bold_item:
            indent, label, rest = bold_item.groups()
            heading = None
        else:
            result.append(split_inline(line))
            index += 1
            continue

        if not label:
            result.append(line)
            index += 1
            continue

        result.append(f"{indent}- {label}")
        if rest:
            result.append(f"{indent}  {rest}")
        index += 1

        # A heading-style label owns the following prose/display math until the
        # next block begins, so indent it under the new bullet.
        if heading or not rest:
            while index < len(lines):
                following = lines[index]
                if not following.strip():
                    lookahead = index + 1
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    if lookahead >= len(lines) or (
                        _BLOCK_START_RE.match(lines[lookahead]) or _BOLD_ITEM_RE.match(lines[lookahead])
                    ):
                        break
                    result.append("")
                    index += 1
                    continue
                if _BLOCK_START_RE.match(following) or _BOLD_ITEM_RE.match(following):
                    break
                result.append(f"{indent}  {following}")
                index += 1
    return "\n".join(result)


def fix_bullets(text: str) -> str:
    """Convert leading bold labels into bullets and retain existing list markers."""
    return _outside_fences(text, _bulletize_bold_labels)


def fix_bloch_state_equation(text: str) -> str:
    """Restore the fractions/exponents lost when the Bloch paragraph was copied."""

    def work(part: str) -> str:
        if "Bloch sphere" not in part and "∣ψ⟩" not in part and "|ψ⟩" not in part:
            return part
        for broken, fixed in (
            ("cos(2θ\u200b)", "cos(θ/2)"),
            ("sin(2θ\u200b)", "sin(θ/2)"),
            ("cos(2θ)", "cos(θ/2)"),
            ("sin(2θ)", "sin(θ/2)"),
            ("⟩where", "⟩ where"),
        ):
            part = part.replace(broken, fixed)
        return _MANGLED_EXPONENT_RE.sub(lambda match: f"e^(i{match.group(1)})", part)

    return _outside_fences(text, work)


def fix_hadamard_fraction(text: str) -> str:
    """Restore the 1/√2 factors in the Hadamard-gate paragraph."""

    def work(part: str) -> str:
        if "Hadamard Gate" not in part:
            return part
        return _HADAMARD_MANGLED_RE.sub(lambda _: _HADAMARD_FIXED, part)

    return _outside_fences(text, work)


def restore_gate_verifications(text: str) -> str:
    """Put the HXH/HZH proofs back when a fresh export dropped them."""
    if (
        _VERIFICATION_ANCHOR in text
        and _TOFFOLI_ANCHOR in text
        and _VERIFICATION_MARKER not in text
    ):
        return text.replace(
            _VERIFICATION_ANCHOR, _VERIFICATION_ANCHOR + _GATE_VERIFICATIONS, 1
        )
    return text


def normalize_structure(text: str) -> str:
    """Apply all structural repairs before Markdown parsing."""
    text = fix_tables(text)
    text = restore_gate_verifications(text)
    text = fix_bullets(text)
    text = fix_bloch_state_equation(text)
    return fix_hadamard_fraction(text)
