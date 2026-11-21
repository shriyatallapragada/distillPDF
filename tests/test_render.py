from __future__ import annotations

import re

from pipeline.math_svg import latex_to_lines
from pipeline.structure import normalize_structure
from pipeline.render import (
    _align_circuit_lines,
    _markdown_to_html,
    _safe_script,
    build_self_contained_html,
)

MARKDOWN = """## Topic

The bound $\\theta^* \\le \\eta > 0$ stays intact.

$$\\frac{a}{b} + \\alpha$$

| A | B |
| --- | --- |
| 1 | 2 |

```mermaid
flowchart TD
    A[Start] --> B[Done]
```
"""


def test_math_is_not_mutated_by_markdown_it():
    body, toc, count = _markdown_to_html(MARKDOWN)
    # Math is rendered at build time as static SVG, pinned to the same
    # monospace grid used by the circuit diagrams.
    assert "nlmdf-symbol-svg" in body
    assert "θ" in body and "η" in body and "α" in body
    assert "@@NLMDFMATH" not in body
    assert "<table>" in body
    assert "language-mermaid" in body
    assert toc == ""  # the generated Contents block was removed
    assert count == 2


def test_multiline_display_math_with_trailing_closer():
    markdown = (
        "$$F_n = \\frac{1}{\\sqrt{n}} \\begin{bmatrix} \n"
        "1 & 1 \\\\ \n"
        "\\end{bmatrix}$$\n"
    )
    body, _, count = _markdown_to_html(markdown)
    assert count == 1
    assert "nlmdf-symbol display" in body
    assert "nlmdf-symbol-svg" in body
    assert "$$" not in body
    assert "\\begin{bmatrix}" not in body
    assert "F" in body and "√n" in body
    assert 'class="nlmdf-sub"' in body


def test_display_math_mid_paragraph_is_rendered():
    markdown = (
        "The matrix is $$U = \\begin{bmatrix} 1 & 0 \\\\ \n"
        "0 & 1 \\end{bmatrix}$$ and it is unitary.\n"
    )
    body, _, count = _markdown_to_html(markdown)
    assert count == 1
    assert "nlmdf-symbol display" in body
    assert "nlmdf-symbol-svg" in body
    assert "$$" not in body
    assert "and it is unitary" in body


def test_multi_control_connectors_are_rebuilt_under_controls():
    lines = [
        "Control 1 ──────■────────────■───────",
        "│ │",
        "Control 2 ──────┼────■────────┼───────",
        "│ │ │",
        "Target ───H──⊕───T†───⊕───────⊕───────",
    ]
    out = _align_circuit_lines(lines)
    assert out[1].index("│") == lines[0].index("■")
    assert out[1].rindex("│") == lines[0].rindex("■")
    bar_columns = [index for index, char in enumerate(out[3]) if char == "│"]
    control_columns = [
        index for index, char in enumerate(lines[2]) if char in "■┼"
    ]
    assert bar_columns == control_columns


def test_self_contained_html_has_no_external_references():
    page, counts = build_self_contained_html(MARKDOWN)
    assert "src=\"http" not in page
    assert "href=\"http" not in page
    assert "url(fonts/" not in page
    assert "data:font/woff2;base64" in page
    assert page.count("<script>") == 3  # KaTeX, Mermaid, boot
    assert "window.__NLMDF" in page
    assert counts["formulas_in_markdown"] == 2
    assert counts["toc_entries"] == 0
    assert "<nav" not in page


def test_safe_script_escapes_closing_tag():
    assert _safe_script("a</script>b") == "a<\\/script>b"


def test_table_after_numbered_line_renders_as_table():
    markdown = (
        "4. Comprehensive Comparison Table: Bit vs. Qubit\n"
        "| Feature | Classical Bit |\n"
        "| --- | --- |\n"
        "| Definition | Discrete 0 or 1 |\n"
    )
    body, _, _ = _markdown_to_html(markdown)
    assert "<table>" in body
    assert "Comprehensive Comparison Table" in body
    assert "Discrete 0 or 1" in body


def test_bold_lettered_label_becomes_bullet():
    body, _, _ = _markdown_to_html("**A. Pauli-X Gate**Flips bits.\n")
    assert "<li>A. Pauli-X Gate" in body
    assert "Flips bits." in body
    assert "**A." not in body


def test_nested_bold_label_keeps_whole_name():
    body, _, _ = _markdown_to_html("**D. Hadamard Gate (**H**)**Creates superposition.\n")
    assert "Hadamard Gate (H)" in body
    assert "Creates superposition." in body
    assert "**H**" not in body


def test_numbered_bold_item_is_not_swallowed_by_label_scanner():
    markdown = (
        "3. **Toffoli Construction Decomposition**:\n"
        "   A 3-qubit gate built from CNOTs.\n"
    )
    body, _, _ = _markdown_to_html(markdown)
    assert "<strong>Toffoli Construction Decomposition</strong>" in body
    assert "A 3-qubit gate built from CNOTs." in body
    assert "<li>\n</li>" not in body


def test_multiple_matrices_share_aligned_grid():
    lines = latex_to_lines(
        r"S \equiv \begin{bmatrix} 1 & 0 \\ 0 & i \end{bmatrix} = "
        r"\begin{bmatrix} 1 & 0 \\ 0 & e^{i\pi/2} \end{bmatrix}"
    )
    joined = "\n".join(lines)
    assert len(lines) == 2
    assert "bmatrix" not in joined
    assert lines[1].startswith(" ")
    assert "e^(iπ/2)" in joined


def test_matrix_summary_block_uses_static_svg():
    markdown = (
        "```text\n"
        " Single-Qubit Gate Matrix Summary:\n"
        " X = Y = [0 -i]\n"
        " [i 0]\n"
        "```\n"
    )
    page, _ = build_self_contained_html(markdown)
    assert "nlmdf-circuit" in page
    assert "nlmdf-matrix-svg" in page
    assert "Single-Qubit Gate Matrix Summary" in page
    assert "<pre><code" not in page


def test_math_matrix_uses_drawn_brackets_and_cell_grid():
    body, _, _ = _markdown_to_html(
        r"$$\begin{bmatrix} 0 & 1 \\ 1 & 0 \end{bmatrix}$$"
    )
    assert "nlmdf-matrix-svg" in body
    assert 'stroke="currentColor"' in body
    assert "begin{bmatrix}" not in body
    assert "[0" not in body


def test_exponents_are_raised_instead_of_flattened():
    body, _, _ = _markdown_to_html(r"The state $|\psi\rangle=e^{i\phi}$ is ready.\n")
    assert 'class="nlmdf-sup"' in body
    assert "iϕ" in body
    assert "e^(iϕ)" not in body
    assert "baseline-shift" not in body


def test_exponent_sits_above_the_base_glyph():
    body, _, _ = _markdown_to_html(r"$e^{i\phi}$")
    nodes = re.findall(
        r'<text class="([^"]*)" x="([-\d.]+)" y="([-\d.]+)"[^>]*>(.*?)</text>',
        body,
    )
    base = next(node for node in nodes if node[3] == "e")
    exponent = next(node for node in nodes if "iϕ" in node[3])
    assert "nlmdf-sup" in exponent[0]
    assert float(exponent[2]) < float(base[2])


def test_command_exponent_is_one_superscript_atom():
    body, _, _ = _markdown_to_html(r"$A^\dagger = A$")
    nodes = re.findall(
        r'<text class="([^"]*)" x="([-\d.]+)" y="([-\d.]+)"[^>]*>(.*?)</text>',
        body,
    )
    dagger = next(node for node in nodes if node[3] == "†")
    assert dagger[0] == "nlmdf-sup"
    assert "dagger" not in body
    assert r"\dagger" not in body


def test_nested_bullet_stays_inside_its_numbered_item():
    markdown = (
        "1. **Inner Product**: maps vectors.\n"
        r"   $$\langle 0|0\rangle = 1$$" "\n"
        "   * **Worked Dual Computation**: Given vectors.\n"
        r"     $$\langle\alpha|\beta\rangle = -3i + 7$$" "\n"
        "2. Outer product.\n"
    )
    body, _, _ = _markdown_to_html(markdown)
    assert re.search(
        r"<ol>\s*<li>.*?<ul>\s*<li><strong>Worked Dual Computation</strong>",
        body,
        re.S,
    )
    assert "-3i + 7" in body


def test_bloch_sphere_equation_repairs_missing_fraction_and_exponent():
    body, _, _ = _markdown_to_html(
        "On the **Bloch sphere**:∣ψ⟩=cos(2θ)∣0⟩+eiϕsin(2θ)∣1⟩"
        "where θ∈[0,π].\n"
    )
    assert "cos(θ/2)" in body
    assert "sin(θ/2)" in body
    assert "iϕ" in body
    assert "eiϕ" not in body


def test_verification_formulas_are_preserved_when_present():
    markdown = (
        "erification of $H X H = Z$: $$H X H = \\frac{1}{\\sqrt{2}}"
        "\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix}"
        "\\begin{bmatrix} 0 & 1 \\\\ 1 & 0 \\end{bmatrix} = Z$$"
        "Verification of $H Z H = X$: $$H Z H = \\frac{1}{\\sqrt{2}}"
        "\\begin{bmatrix} 1 & 1 \\\\ 1 & -1 \\end{bmatrix}"
        "\\begin{bmatrix} 1 & 0 \\\\ 0 & -1 \\end{bmatrix} = X$$\n"
    )
    body, _, _ = _markdown_to_html(markdown)
    assert "erification of" in body
    assert "Verification of" in body
    assert "H X H" in body and "H Z H" in body
    assert body.count("nlmdf-matrix-svg") >= 3


def test_hadamard_fraction_and_root_two_are_restored():
    markdown = (
        "- D. Hadamard Gate (H)\n"
        "  Creates an equal superposition state: "
        "H≡2\u200b1\u200b[11\u200b1−1\u200b],"
        "H∣0⟩=2\u200b∣0⟩+∣1⟩\u200b=∣+⟩,"
        "H∣1⟩=2\u200b∣0⟩−∣1⟩\u200b=∣−⟩\n"
    )
    body, _, _ = _markdown_to_html(markdown)
    assert "1/(√2)" in body
    assert "(|0⟩ + |1⟩)/(√2)" in body
    assert "(|0⟩ - |1⟩)/(√2)" in body
    assert "H∣0⟩=2" not in body


def test_gate_proofs_are_restored_after_a_fresh_export_drops_them():
    markdown = (
        "**B. Algebraic Gate Identifications & Proofs**\n\n"
        "```text\n"
        "  Toffoli Gate Decomposition Circuit:\n"
        "  Control 1 ──────■─────────\n"
        "```\n"
    )
    body, _, _ = _markdown_to_html(markdown)
    assert "H X H" in body and "H Z H" in body
    assert body.count("nlmdf-matrix-svg") >= 6


def test_existing_gate_proofs_are_not_duplicated():
    anchor = "**B. Algebraic Gate Identifications & Proofs**"
    present = (
        anchor + "\n\n"
        "Verification of $H X H = Z$: $$H X H = Z$$\n"
        "Verification of $H Z H = X$: $$H Z H = X$$\n\n"
        "```text\nToffoli Gate Decomposition Circuit\n```\n"
    )
    result = normalize_structure(present)
    assert result.count("Verification of $H X H = Z$") == 1
    assert result.count("Verification of $H Z H = X$") == 1


def test_escaped_latex_braces_render_cleanly():
    body, _, _ = _markdown_to_html(r"Set $\{H, T, S\}$ is shown.\n")
    assert "{H, T, S}" in body
    assert "\\}" not in body
