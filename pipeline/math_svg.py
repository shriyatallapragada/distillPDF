"""Render math and symbol runs as static inline SVG text.

This uses the exact same technique as the circuit diagrams in render.py:
one monospace <text> node per source line, pinned with ``textLength`` so every
glyph (Greek letters, bras/kets, operators, box drawing) sits on a fixed grid.
It replaces KaTeX, whose HTML+MathML output mangles the plain-unicode symbols
that NotebookLM puts in prose and mis-typesets markdown text (``10 Marks``)
that was accidentally fenced as display math.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from typing import Iterable, NamedTuple

# A run is treated as symbolic when it contains at least one of these chars.
# Deliberately broad: any of them means the surrounding expression should use
# the symbol font instead of Inter (which lacks most math glyphs).
SYMBOL_CHARS = set(
    "∣⟨⟩αβγδϵεζηθικλμνξοπρστυφϕχψω"
    "∈∉∋⊆⊇⊂⊃∪∩∅∀∃∄≤≥≪≫≡≈≅≠∝∞∂∇∑∏∫√"
    "⊕⊗⊙⋅×÷°†‡→←↔⇒⇐⟹⟺↦↑↓±∓−²³ⁿⁱ"
    "ℂℝℤℚℕℏ■│─┌┐└┘├┤┬┴┼"
)

# LaTeX command -> unicode glyph. Ordered longest-first so \dfrac wins over
# \d, \trightarrow over \rightarrow, etc.
SYMBOL_MAP: dict[str, str] = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ϵ", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "omicron": "ο",
    "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ", "sigma": "σ",
    "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "ϕ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ",
    "Psi": "Ψ", "Omega": "Ω",
    "langle": "⟨", "rangle": "⟩", "lceil": "⌈", "rceil": "⌉",
    "lfloor": "⌊", "rfloor": "⌋", "lvert": "|", "rvert": "|",
    "mid": "∣", "Vert": "‖", "Vert": "‖", "parallel": "‖",
    "in": "∈", "notin": "∉", "ni": "∋",
    "subset": "⊂", "supset": "⊃", "subseteq": "⊆", "supseteq": "⊇",
    "cup": "∪", "cap": "∩", "emptyset": "∅", "varnothing": "∅",
    "forall": "∀", "exists": "∃", "nexists": "∄",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "ll": "≪", "gg": "≫", "equiv": "≡", "approx": "≈", "cong": "≅",
    "neq": "≠", "ne": "≠", "propto": "∝", "infty": "∞",
    "partial": "∂", "nabla": "∇", "sum": "∑", "prod": "∏", "int": "∫",
    "sqrt": "√", "oplus": "⊕", "otimes": "⊗", "odot": "⊙",
    "cdot": "⋅", "times": "×", "div": "÷", "circ": "∘", "bullet": "•",
    "dagger": "†", "ddagger": "‡", "degree": "°",
    "rightarrow": "→", "leftarrow": "←", "leftrightarrow": "↔",
    "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔",
    "implies": "⟹", "iff": "⟺", "mapsto": "↦",
    "uparrow": "↑", "downarrow": "↓", "pm": "±", "mp": "∓",
    "mathbb{C}": "ℂ", "mathbb{R}": "ℝ", "mathbb{Z}": "ℤ",
    "mathbb{Q}": "ℚ", "mathbb{N}": "ℕ", "mathbb{H}": "ℍ",
    "hbar": "ℏ", "ell": "ℓ", "prime": "′", "angle": "∠",
    "perp": "⊥", "top": "⊤", "bot": "⊥",
    "setminus": "∖", "neg": "¬", "land": "∧", "lor": "∨",
    "to": "→", "longrightarrow": "⟶", "longleftarrow": "⟵",
    "cdots": "⋯", "ldots": "…", "vdots": "⋮", "ddots": "⋱",
}
SYMBOL_CHARS.update(symbol for symbol in SYMBOL_MAP.values() if len(symbol) == 1 and not symbol.isascii())

# Commands that take one braced argument and should be dropped or rewritten.
_STYLE_COMMANDS = {
    "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathscr",
    "boldsymbol", "text", "textrm", "textbf", "textit", "textsf", "texttt",
    "operatorname", " underlined", "overline", "hat", "bar", "vec", "tilde",
    "dot", "ddot", "widehat", "widetilde", "overline", "underline",
    "displaystyle", "textstyle", "scriptstyle", "limits", "nolimits",
    "left", "right", "big", "Big", "bigg", "Bigg", "quad", "qquad",
    "!,", ";", ":", ",", " ",
}


def _balanced_arg(source: str, start: int) -> tuple[str, int]:
    """Return the content of the {...} at ``start`` and the index after it."""
    if start >= len(source) or source[start] != "{":
        return "", start
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : index], index + 1
    return source[start + 1 :], len(source)


_LATEX_COMMAND_RE = re.compile(r"\\([A-Za-z]+|[{}%*$#&_,;:! ])")
_LATEX_LITERAL_CHARS = "{}%*$#&_"
_LATEX_SPACES = {"quad": "  ", "qquad": "    ", ",": " ", ":": " ", ";": " ", " ": " ", "!": ""}


def _command_atom(source: str, index: int) -> tuple[str, int] | None:
    r"""Consume a LaTeX command as one atom after ``^`` or ``_``.

    Without this, ``^\dagger`` takes only the leading backslash as its
    exponent and leaves ``dagger`` as ordinary text, which printed as a stray
    slash followed by the command name.
    """
    if index >= len(source) or source[index] != "\\":
        return None
    match = _LATEX_COMMAND_RE.match(source, index)
    if match is None:
        return None
    command = match.group(1)
    end = match.end()
    if command in {"frac", "dfrac", "tfrac", "cfrac"}:
        first, after_first = _balanced_arg(source, end)
        second, after_second = _balanced_arg(source, after_first)
        if first and second:
            return source[index:after_second], after_second
        return source[index:end], end
    if source[end : end + 1] == "{":
        argument, after_argument = _balanced_arg(source, end)
        if argument:
            return source[index:after_argument], after_argument
    return source[index:end], end


def _fraction_arguments(source: str) -> tuple[str, str, int] | None:
    for command in ("\\dfrac", "\\tfrac", "\\frac", "\\cfrac"):
        if source.startswith(command):
            numerator, pos = _balanced_arg(source, len(command))
            denominator, end = _balanced_arg(source, pos)
            return (numerator, denominator, end) if numerator and denominator else None
    return None


def _linear_fraction(numerator: str, denominator: str) -> str:
    def format_part(part: str) -> str:
        part = part.strip()
        if re.fullmatch(r"(?:\d+(?:\.\d+)?|[A-Za-z])", part):
            return part
        converted = "".join(_convert_plain(_normalize_latex(part)))
        return f"({part})" if len(converted) > 1 else part

    return f"{format_part(numerator)}/{format_part(denominator)}"


class _TextPart(NamedTuple):
    """One styled piece of a formula line.

    ``kind`` is ``normal``, ``sup`` or ``sub``. Exponents are kept as separate
    pieces so the SVG can raise them with a <tspan> instead of flattening
    ``e^(iφ)`` into ``eiφ``.
    """

    text: str
    kind: str = "normal"
    fraction: tuple[list[_TextPart], list[_TextPart]] | None = None


@dataclass
class _TextAtom:
    parts: list[_TextPart]


@dataclass
class _MatrixAtom:
    rows: list[list[list[_TextPart]]]


_MathAtom = _TextAtom | _MatrixAtom


def _merge_parts(parts: list[_TextPart]) -> list[_TextPart]:
    merged: list[_TextPart] = []
    for part in parts:
        if part.fraction is not None:
            merged.append(part)
            continue
        if not part.text:
            continue
        if merged and merged[-1].fraction is None and merged[-1].kind == part.kind:
            previous = merged[-1]
            merged[-1] = _TextPart(previous.text + part.text, previous.kind)
        else:
            merged.append(part)
    return merged


def _mark_parts(parts: list[_TextPart], kind: str) -> list[_TextPart]:
    return [
        part._replace(kind=kind) if part.kind == "normal" else part
        for part in parts
    ]


def _exponent_arg(source: str, index: int) -> tuple[str, int]:
    """Return the argument after ^ or _ and the index following it.

    ``^{...}``, ``^(...)`` and a single following glyph are all accepted; the
    chat export uses the parenthesis form while LaTeX uses braces.
    """
    if index >= len(source):
        return "", index
    command = _command_atom(source, index)
    if command is not None:
        return command
    if source[index] == "{":
        return _balanced_arg(source, index)
    if source[index] == "(":
        depth = 0
        for position in range(index, len(source)):
            if source[position] == "(":
                depth += 1
            elif source[position] == ")":
                depth -= 1
                if depth == 0:
                    return source[index + 1 : position], position + 1
        return source[index + 1 :], len(source)
    return source[index], index + 1


def rich_parts(source: str, kind: str = "normal", *, stacked: bool = False) -> list[_TextPart]:
    """Parse math into styled text and, for prose equations, stacked fractions."""
    def parse(argument: str, style: str = kind) -> list[_TextPart]:
        return rich_parts(argument, style, stacked=stacked)

    parts: list[_TextPart] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char in "^_":
            argument, position = _exponent_arg(source, index + 1)
            if argument:
                exponent_kind = "sup" if char == "^" else "sub"
                parts.extend(_mark_parts(parse(argument, "normal"), exponent_kind))
                index = position
                continue
            parts.append(_TextPart(char, kind))
            index += 1
            continue
        if char == "\\":
            if index + 1 < len(source) and source[index + 1] == "\\":
                parts.append(_TextPart(" ", kind))
                index += 2
                continue
            fraction = _fraction_arguments(source[index:])
            if fraction is not None:
                numerator, denominator, consumed = fraction
                if stacked:
                    parts.append(_TextPart("", kind, (
                        parse(numerator.strip(), "normal"), parse(denominator.strip(), "normal")
                    )))
                else:
                    parts.extend(parse(_linear_fraction(numerator, denominator)))
                index += consumed
                continue
            match = _LATEX_COMMAND_RE.match(source, index)
            if not match:
                parts.append(_TextPart(char, kind))
                index += 1
                continue
            command = match.group(1)
            after_command = match.end()
            if len(command) == 1 and command in _LATEX_LITERAL_CHARS:
                parts.append(_TextPart(command, kind))
                index = after_command
                continue
            if command in _LATEX_SPACES:
                parts.append(_TextPart(_LATEX_SPACES[command], kind))
                index = after_command
                continue
            if command == "sqrt":
                root = re.match(r"(?:\[([^\]]+)\])?\s*", source[after_command:])
                assert root is not None
                start = after_command + root.end()
                argument, position = _balanced_arg(source, start)
                if argument:
                    if root[1]:
                        parts.extend(_mark_parts(parse(root[1], "normal"), "sup"))
                    parts.append(_TextPart("√", kind))
                    radicand = argument.strip()
                    if len(radicand) > 1 and not radicand.isdecimal():
                        radicand = f"({radicand})"
                    parts.extend(parse(radicand))
                    index = position
                    continue
            if source[after_command : after_command + 1] == "{":
                argument, position = _balanced_arg(source, after_command)
                combined = command + argument
                if combined in SYMBOL_MAP:
                    parts.append(_TextPart(SYMBOL_MAP[combined], kind))
                    index = position
                    continue
                if command in SYMBOL_MAP and command not in _STYLE_COMMANDS:
                    parts.append(_TextPart(SYMBOL_MAP[command], kind))
                    parts.extend(parse(argument))
                    index = position
                    continue
                parts.extend(parse(argument))
                index = position
                continue
            if command in _STYLE_COMMANDS:
                if command in {
                    "hat", "bar", "vec", "tilde", "dot", "ddot", "widehat",
                    "widetilde", "overline", "underline", "boldsymbol",
                    "mathrm", "mathbf", "mathit", "mathsf", "mathtt",
                    "mathcal", "mathscr", "text", "textrm", "textbf", "textit",
                    "textsf", "texttt", "operatorname",
                }:
                    argument, position = _balanced_arg(source, after_command)
                    parts.extend(parse(argument))
                    index = position
                else:
                    index = after_command
                continue
            parts.append(_TextPart(SYMBOL_MAP.get(command, command), kind))
            index = after_command
            continue
        if char in "{}":
            index += 1
            continue
        parts.append(_TextPart(char, kind))
        index += 1
    return _merge_parts(parts)


def _normalize_latex(source: str) -> str:
    """Undo the extension's escapeMd doubling and escaped underscores."""
    return source.replace("\\_", "_").replace("\\\\", "\\")


_MATRIX_NAMES = "bmatrix|Bmatrix|pmatrix|vmatrix|Vmatrix|array|matrix"
_MATRIX_BEGIN_RE = re.compile(r"\\{1,}begin\{(" + _MATRIX_NAMES + r")\}")
_MATRIX_END_RE = re.compile(r"\\{1,}end\{(" + _MATRIX_NAMES + r")\}")


def _matrix_lines(body: str, environment: str) -> list[str] | None:
    """Turn one matrix environment body into aligned monospace lines."""
    body = re.sub(r"^\s*\{[^}]*\}", "", body)  # array's {cc} column spec
    rows = re.split(r"\\\\+", body)
    cells = [
        ["".join(_convert_plain(_normalize_latex(cell))).strip() for cell in row.split("&")]
        for row in rows
    ]
    cells = [[cell for cell in row if cell] for row in cells]
    cells = [row for row in cells if row]
    if not cells:
        return None
    opening, closing = {
        "bmatrix": ("[", "]"), "pmatrix": ("(", ")"),
        "Bmatrix": ("{", "}"), "vmatrix": ("|", "|"),
        "Vmatrix": ("‖", "‖"), "array": ("[", "]"), "matrix": ("[", "]"),
    }[environment]
    widths = [
        max(len(row[col]) for row in cells if col < len(row))
        for col in range(max(len(row) for row in cells))
    ]
    lines: list[str] = []
    for index, row in enumerate(cells):
        content = "  ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)).rstrip()
        prefix = opening if index == 0 else " "
        suffix = closing if index == len(cells) - 1 else " "
        lines.append(prefix + content + suffix)
    return lines


def _matrix_cells(body: str, environment: str) -> list[list[list[_TextPart]]] | None:
    """Parse a matrix environment into styled cells, not monospace text rows."""
    body = re.sub(r"^\s*\{[^}]*\}", "", body)  # array's {cc} column spec
    rows: list[list[list[_TextPart]]] = []
    for raw_row in re.split(r"\\\\+", body):
        cells = [
            rich_parts(_normalize_latex(cell).replace("\u200b", "").strip())
            for cell in raw_row.split("&")
        ]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(cells)
    return rows or None


def _split_math_segments_rich(source: str) -> list[tuple[str, object]]:
    """Split math into ``("text", str)`` and ``("matrix", cells)`` pieces."""
    segments: list[tuple[str, object]] = []
    cursor = 0
    while True:
        begin = _MATRIX_BEGIN_RE.search(source, cursor)
        if not begin:
            break
        environment = begin.group(1)
        end = re.search(
            r"\\{1,}end\{" + re.escape(environment) + r"\}", source[begin.end():]
        )
        if not end:
            break
        end_at = begin.end() + end.start()
        finish = begin.end() + end.end()
        if cursor < begin.start():
            segments.append(("text", source[cursor : begin.start()]))
        cells = _matrix_cells(source[begin.end() : end_at], environment)
        if cells is None:
            segments.append(("text", source[begin.start() : finish]))
        else:
            segments.append(("matrix", cells))
        cursor = finish
    if cursor < len(source):
        segments.append(("text", source[cursor:]))
    return segments


def _math_atoms(source: str) -> list[_MathAtom]:
    atoms: list[_MathAtom] = []
    for kind, value in _split_math_segments_rich(source):
        if kind == "matrix":
            atoms.append(_MatrixAtom(value))
            continue
        text = str(value).replace("\n", " ")
        parts = rich_parts(_normalize_latex(text), stacked=True)
        if parts:
            atoms.append(_TextAtom(parts))
    while atoms and isinstance(atoms[0], _TextAtom):
        first = atoms[0].parts
        if not first or first[0].fraction is not None or first[0].text.strip():
            break
        leading = len(first[0].text) - len(first[0].text.lstrip())
        if leading >= len(first[0].text):
            atoms.pop(0)
        else:
            atoms[0] = _TextAtom([_TextPart(first[0].text[leading:], first[0].kind), *first[1:]])
        break
    while atoms and isinstance(atoms[-1], _TextAtom):
        last = atoms[-1].parts
        if not last or last[-1].fraction is not None or last[-1].text.strip():
            break
        trailing = len(last[-1].text) - len(last[-1].text.rstrip())
        if trailing >= len(last[-1].text):
            atoms.pop()
        else:
            atoms[-1] = _TextAtom([*last[:-1], _TextPart(last[-1].text[:-trailing], last[-1].kind)])
        break
    return atoms


def _split_math_segments(source: str) -> list[tuple[str, object]]:
    """Split math source into ``("text", str)`` and ``("matrix", lines)`` pieces.

    NotebookLM formulas regularly contain several matrices in one expression
    (a product in a proof, ``S = A = B``, a bra-ket column vector followed by
    its dual, ...). Converting only the first one left raw ``bmatrix`` text in
    the PDF, so every environment is converted and laid out on a shared grid.
    """
    segments: list[tuple[str, object]] = []
    cursor = 0
    while True:
        begin = _MATRIX_BEGIN_RE.search(source, cursor)
        if not begin:
            break
        environment = begin.group(1)
        end = re.search(
            r"\\{1,}end\{" + re.escape(environment) + r"\}", source[begin.end():]
        )
        if not end:
            break
        end_at = begin.end() + end.start()
        finish = begin.end() + end.end()
        if cursor < begin.start():
            segments.append(("text", source[cursor : begin.start()]))
        lines = _matrix_lines(source[begin.end() : end_at], environment)
        if lines is None:
            segments.append(("text", source[begin.start() : finish]))
        else:
            segments.append(("matrix", lines))
        cursor = finish
    if cursor < len(source):
        segments.append(("text", source[cursor:]))
    return segments


def _convert_plain(source: str) -> list[str]:
    """Convert LaTeX without matrix environments into lines of unicode text."""
    out: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char == "\\":
            # \\ is a forced line break.
            if index + 1 < len(source) and source[index + 1] == "\\":
                out.append("")
                index += 2
                continue
            fraction = _fraction_arguments(source[index:])
            if fraction is not None:
                numerator, denominator, consumed = fraction
                out.append("".join(_convert_plain(_linear_fraction(numerator, denominator))))
                index += consumed
                continue
            match = re.match(r"\\([A-Za-z]+|[{}])", source[index:])
            if not match:
                out.append(char)
                index += 1
                continue
            command = match.group(1)
            if command in {"{", "}"}:
                out.append(command)
                index += 2
                continue
            after_command = match.end() + index
            # Commands that take a braced argument and map to a single glyph:
            # \mathbb{Z} -> ℤ, \mathbb{C} -> ℂ, etc.
            if source[after_command:after_command + 1] == "{":
                arg, pos = _balanced_arg(source, after_command)
                combined = command + arg
                if combined in SYMBOL_MAP:
                    out.append(SYMBOL_MAP[combined])
                    index = pos
                    continue
                if command in SYMBOL_MAP and command not in _STYLE_COMMANDS:
                    # \sqrt{n}, \sum_{i}, ... keep the glyph and take the arg.
                    out.append(SYMBOL_MAP[command] + "".join(_convert_plain(arg)))
                    index = pos
                    continue
                # Not a known combined glyph: process the argument normally.
                out.append("".join(_convert_plain(arg)))
                index = pos
                continue
            if command in _STYLE_COMMANDS:
                if command in {"hat", "bar", "vec", "tilde", "dot", "ddot", "widehat", "widetilde", "overline", "underline", "boldsymbol", "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathscr", "text", "textrm", "textbf", "textit", "textsf", "texttt", "operatorname"}:
                    arg, pos = _balanced_arg(source, after_command)
                    out.append("".join(_convert_plain(arg)))
                    index = pos
                else:
                    index = after_command
                continue
            replacement = SYMBOL_MAP.get(command, command)
            out.append(replacement)
            index = match.end() + index
            continue
        if char == "^" or char == "_":
            command = _command_atom(source, index + 1)
            if command is not None:
                arg, pos = command
            else:
                arg, pos = _balanced_arg(source, index + 1)
            if not arg:
                out.append(char)
                index += 1
                continue
            if len(arg) == 1:
                sup = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
                sub = str.maketrans("0123456789+-=()n", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₙ")
                out.append(arg.translate(sup if char == "^" else sub))
            else:
                converted = "".join(_convert_plain(arg))
                out.append("^(" + converted + ")" if char == "^" else "_(" + converted + ")")
            index = pos
            continue
        if char == "{" or char == "}":
            index += 1
            continue
        out.append(char)
        index += 1
    return ["".join(out)]


def latex_to_lines(source: str) -> list[str]:
    """Turn LaTeX math source into readable monospace lines of unicode text.

    Text and every matrix are laid out as cells on a common row grid: a matrix
    gets one line per row, while operators/text sit on the first row and are
    padded underneath. That keeps ``S = [..] = [..]`` and matrix products in a
    proof aligned instead of emitting raw ``bmatrix`` commands.
    """
    segments = _split_math_segments(source)
    if not segments:
        return []

    cells: list[list[str]] = []
    kinds: list[str] = []
    for index, (kind, value) in enumerate(segments):
        if kind == "matrix":
            cells.append([line.rstrip() for line in value])
            kinds.append("matrix")
            continue
        text = str(value)
        # Matrix bodies keep their doubled backslashes; surrounding text needs
        # escapeMd's doubling undone.
        converted = [
            line.strip()
            for line in _convert_plain(_normalize_latex(text))
            if line.strip()
        ]
        if not converted:
            continue
        if index and segments[index - 1][0] == "matrix":
            converted[0] = " " + converted[0]
        if index + 1 < len(segments) and segments[index + 1][0] == "matrix":
            converted[-1] = converted[-1] + " "
        cells.append(converted)
        kinds.append("text")

    if not cells:
        return []
    widths = [max(len(line) for line in cell) for cell in cells]
    height = max(len(cell) for cell in cells)
    lines: list[str] = []
    for row in range(height):
        pieces: list[str] = []
        for position, cell in enumerate(cells):
            piece = (cell[row] if row < len(cell) else "").ljust(widths[position])
            if kinds[position] == "matrix" and position and kinds[position - 1] == "matrix":
                # Adjacent matrices in a product need a visible gap on every row.
                piece = " " + piece
            pieces.append(piece)
        lines.append("".join(pieces).rstrip())
    return [line for line in lines if line.strip()]


def has_symbol(text: str) -> bool:
    return any(char in SYMBOL_CHARS for char in text)


def latex_to_unicode(source: str) -> str:
    return "\n".join(latex_to_lines(source))


# ---------------------------------------------------------------------------
# Inline SVG construction
# ---------------------------------------------------------------------------

_FONT = "SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
_CELL_PX = 8.4
_LINE_PX = 15.0
_FONT_PX = 13.0


_BRACKET_RATIO = 0.55
_INNER_PAD_RATIO = 0.35
_COL_GAP_RATIO = 0.8
_ROW_HEIGHT_RATIO = 1.45
_SUP_SCALE = 0.72
_SUP_RISE = 0.48   # fraction of the base font size above the baseline
_SUB_DROP = 0.22   # fraction of the base font size below the baseline
_FRACTION_SCALE = 0.78
_FRACTION_AXIS = 0.27
_FRACTION_GAP = 0.16


def _part_width(part: _TextPart, cell_px: float) -> float:
    scale = 1.0 if part.kind == "normal" else _SUP_SCALE
    if part.fraction is not None:
        width = max(_parts_width(row, cell_px * _FRACTION_SCALE) for row in part.fraction)
        return (width + 0.45 * cell_px) * scale
    return len(part.text) * cell_px * scale


def _parts_width(parts: list[_TextPart], cell_px: float) -> float:
    return sum(_part_width(part, cell_px) for part in parts)


def _script_offset(kind: str, font_px: float) -> float:
    return {"sup": -font_px * _SUP_RISE, "sub": font_px * _SUB_DROP}.get(kind, 0.0)


def _parts_extents(parts: list[_TextPart], font_px: float) -> tuple[float, float]:
    """Measure the height above and below a row's baseline."""
    ascent = descent = 0.0
    for part in parts:
        size = font_px if part.kind == "normal" else font_px * _SUP_SCALE
        offset = _script_offset(part.kind, font_px)
        if part.fraction is None:
            above, below = size * 0.85, size * 0.28
        else:
            numerator, denominator = part.fraction
            above = sum(_parts_extents(numerator, size * _FRACTION_SCALE))
            below = sum(_parts_extents(denominator, size * _FRACTION_SCALE))
            above += size * (_FRACTION_AXIS + _FRACTION_GAP)
            below += size * (_FRACTION_GAP - _FRACTION_AXIS)
        ascent = max(ascent, above - offset)
        descent = max(descent, below + offset)
    return ascent, descent


def _fraction_markup(
    rows: tuple[list[_TextPart], list[_TextPart]], x: float, baseline: float,
    width: float, size: float, cell_px: float,
) -> str:
    numerator, denominator = rows
    row_size = size * _FRACTION_SCALE
    row_cell = cell_px * _FRACTION_SCALE
    bar = baseline - size * _FRACTION_AXIS
    gap = size * _FRACTION_GAP
    numerator_y = bar - gap - _parts_extents(numerator, row_size)[1]
    denominator_y = bar + gap + _parts_extents(denominator, row_size)[0]
    numerator_x = x + (width - _parts_width(numerator, row_cell)) / 2
    denominator_x = x + (width - _parts_width(denominator, row_cell)) / 2
    return (
        '<g class="nlmdf-fraction"><g class="nlmdf-numerator">'
        + rich_text_markup(numerator, numerator_x, numerator_y, row_size, row_cell)
        + '</g><line '
        f'x1="{x:.2f}" y1="{bar:.2f}" x2="{x + width:.2f}" y2="{bar:.2f}" '
        'stroke="currentColor" stroke-width="0.8"/><g class="nlmdf-denominator">'
        + rich_text_markup(denominator, denominator_x, denominator_y, row_size, row_cell)
        + "</g></g>"
    )


def rich_text_markup(
    parts: list[_TextPart],
    x: float,
    baseline: float,
    font_px: float,
    cell_px: float,
) -> str:
    """Build explicit <text> nodes with raised/lowered fractions of the size.

    ``baseline-shift`` keywords are unreliable in print pipelines (``sup`` is
    not even a valid SVG value), which made ``e^{iφ}`` appear low. Placing each
    part at its own absolute y makes the exponent unambiguously superscript.
    """
    nodes: list[str] = []
    cursor = x
    for part in parts:
        scale = 1.0 if part.kind == "normal" else _SUP_SCALE
        part_y = baseline + _script_offset(part.kind, font_px)
        part_font = font_px * scale
        width = _part_width(part, cell_px)
        if part.fraction is not None:
            nodes.append(_fraction_markup(part.fraction, cursor, part_y, width, part_font, cell_px * scale))
            cursor += width
            continue
        css_class = "" if part.kind == "normal" else f"nlmdf-{part.kind}"
        nodes.append(
            f'<text class="{css_class}" x="{cursor:.2f}" y="{part_y:.2f}" '
            f'xml:space="preserve" font-family="{_FONT}" '
            f'font-size="{part_font:.2f}px" style="white-space:pre">'
            f"{html_lib.escape(part.text)}</text>"
        )
        cursor += width
    return "".join(nodes)


def _matrix_layout(
    rows: list[list[list[_TextPart]]], font_px: float, cell_px: float
) -> tuple[float, float, list[float], float, float, float, float]:
    row_height = font_px * _ROW_HEIGHT_RATIO
    height = len(rows) * row_height
    bracket = font_px * _BRACKET_RATIO
    pad = cell_px * _INNER_PAD_RATIO
    gap = cell_px * _COL_GAP_RATIO
    columns = max((len(row) for row in rows), default=0)
    widths = [
        max(
            (
                _parts_width(row[column], cell_px)
                for row in rows
                if column < len(row)
            ),
            default=cell_px,
        )
        for column in range(columns)
    ]
    width = 2 * bracket + 2 * pad + sum(widths) + gap * max(0, columns - 1)
    return width, height, widths, row_height, bracket, pad, gap


def matrix_fragment(
    rows: list[list[list[_TextPart]]],
    baseline: float,
    font_px: float,
    cell_px: float,
    x: float = 0.0,
) -> tuple[str, float]:
    """Draw a matrix with real brackets and an aligned cell grid.

    The nested SVG is positioned so the matrix is vertically centred on the
    surrounding text baseline. Cell glyphs stay monospace; brackets are drawn
    as paths instead of being faked with ``[`` and ``]`` characters.
    """
    width, height, widths, row_height, bracket, pad, gap = _matrix_layout(
        rows, font_px, cell_px
    )
    top = baseline - font_px * 0.35 - height / 2
    cap = bracket * 0.65
    parts = [
        f'<svg class="nlmdf-matrix-svg" x="{x:.2f}" y="{top:.2f}" '
        f'width="{width:.2f}" height="{height:.2f}" '
        f'viewBox="0 0 {width:.2f} {height:.2f}" aria-hidden="true">',
        '<path d="'
        f'M {bracket + cap:.2f} 1.00 H {bracket:.2f} '
        f'V {height - 1:.2f} H {bracket + cap:.2f} '
        f'M {width - bracket - cap:.2f} 1.00 H {width - bracket:.2f} '
        f'V {height - 1:.2f} H {width - bracket - cap:.2f}" '
        'fill="none" stroke="currentColor" stroke-width="1.1"/>',
    ]
    for row_index, row in enumerate(rows):
        cell_baseline = row_index * row_height + row_height * 0.77
        cursor = bracket + pad
        for column, cell in enumerate(row):
            cell_width = widths[column]
            text_width = _parts_width(cell, cell_px)
            cell_x = cursor + max(0.0, (cell_width - text_width) / 2)
            parts.append(
                rich_text_markup(cell, cell_x, cell_baseline, font_px, cell_px)
            )
            cursor += cell_width + gap
    parts.append("</svg>")
    return "".join(parts), width


def _render_atoms_svg(atoms: list[_MathAtom], font_px: float, cell_px: float) -> str:
    if not atoms:
        return ""
    matrix_heights = [
        _matrix_layout(atom.rows, font_px, cell_px)[1]
        for atom in atoms
        if isinstance(atom, _MatrixAtom)
    ]
    pad_top = max(
        font_px * 0.18,
        max(matrix_heights, default=0.0) / 2 - font_px * 0.65 + 2,
    )
    pad_bottom = max(font_px * 0.18, pad_top)
    extents = [
        _parts_extents(atom.parts, font_px) for atom in atoms if isinstance(atom, _TextAtom)
    ]
    baseline = max(pad_top + font_px, max((above for above, _ in extents), default=0) + 2)
    descent = max(font_px * 0.35 + pad_bottom, max((below for _, below in extents), default=0))
    cursor = 2.0
    pieces: list[str] = []
    for atom in atoms:
        if isinstance(atom, _MatrixAtom):
            markup, width = matrix_fragment(atom.rows, baseline, font_px, cell_px, cursor)
        else:
            markup = rich_text_markup(atom.parts, cursor, baseline, font_px, cell_px)
            width = _parts_width(atom.parts, cell_px)
        pieces.append(markup)
        cursor += width
    width = cursor + 2
    height = baseline + descent + 2
    return (
        f'<svg class="nlmdf-symbol-svg" viewBox="0 0 {width:.2f} {height:.2f}" '
        f'width="{width:.2f}" height="{height:.2f}" '
        f'style="vertical-align:-{height - baseline:.2f}px" '
        'preserveAspectRatio="xMinYMin meet" role="img" '
        'aria-label="Mathematical expression">'
        + "".join(pieces)
        + "</svg>"
    )


def inline_svg(text: str, font_px: float = _FONT_PX) -> str:
    """Build an inline SVG, raising exponents instead of flattening them."""
    lines = text.split("\n")
    if len(lines) > 1:
        width = max(len(line) for line in lines) * _CELL_PX * (font_px / _FONT_PX) + 2
        height = len(lines) * _LINE_PX + 2
        parts = [
            f'<svg class="nlmdf-symbol-svg" viewBox="0 0 {width:.2f} {height:.2f}" '
            f'width="{width:.2f}" height="{height:.2f}" '
            'preserveAspectRatio="xMinYMin meet" role="img" '
            'aria-label="Mathematical expression">'
        ]
        for index, line in enumerate(lines):
            y = index * _LINE_PX + font_px
            parts.append(
                f'<text x="0" y="{y:.2f}" xml:space="preserve" '
                f'font-family="{_FONT}" font-size="{font_px:.2f}px" '
                f'textLength="{len(line) * _CELL_PX * (font_px / _FONT_PX):.2f}" '
                'lengthAdjust="spacingAndGlyphs" style="white-space:pre">'
                f"{html_lib.escape(line)}</text>"
            )
        parts.append("</svg>")
        return "".join(parts)
    return _render_atoms_svg([_TextAtom(rich_parts(text))], font_px, _CELL_PX)


# Flat matrices such as ``[0i-ii0]`` or ``[100-1]`` are how NotebookLM flattens
# a small matrix when it copies a chat. Expand them onto a real grid so the
# rows read as a matrix instead of a single unbroken string.
_FLAT_BRACKET_RE = re.compile(r"\[([^\[\]{}]{3,40})\]")
_FLAT_CONTENT_RE = re.compile(r"[0-9eiπ−\-/^()]+")
_MATRIX_CELL_RE = re.compile(r"^[0-9eEiIπ√+\-−/^().]+$")


def _flat_entries(content: str) -> list[str]:
    """Split a compact matrix body into its individual entries."""
    entries: list[str] = []
    index = 0
    while index < len(content):
        char = content[index]
        if char.isspace():
            index += 1
            continue
        sign = "−" if char in "−-" else ""
        if sign:
            index += 1
            if index >= len(content):
                break
            char = content[index]
        if char == "e":
            end = index + 1
            while end < len(content) and content[end] not in "−-":
                end += 1
            entries.append(sign + content[index:end])
            index = end
        else:
            entries.append(sign + char)
            index += 1
    return entries


def matrix_rows_from_content(content: str) -> list[list[str]] | None:
    """Parse bracket contents as a compact or space-separated matrix."""
    content = content.strip()
    if not content:
        return None
    if _FLAT_CONTENT_RE.fullmatch(content):
        entries = _flat_entries(content)
        size = int(len(entries) ** 0.5)
        if size < 2 or size > 4 or size * size != len(entries):
            return None
        return [entries[offset : offset + size] for offset in range(0, len(entries), size)]
    rows = [
        [cell for cell in re.split(r"[ \t]+", row.strip()) if cell]
        for row in content.split("\n")
    ]
    rows = [row for row in rows if row]
    if not rows or len(rows) > 4 or max(len(row) for row in rows) > 4:
        return None
    if len(rows) == 1 and len(rows[0]) == 1:
        return None
    if not all(_MATRIX_CELL_RE.fullmatch(cell) for row in rows for cell in row):
        return None
    return rows


def matrix_svg_rows(rows: list[list[str]], font_px: float = 11.0) -> str:
    """Return a standalone SVG for a matrix given as rows of cell strings."""
    cells = [[rich_parts(cell) for cell in row] for row in rows]
    return _render_atoms_svg([_MatrixAtom(cells)], font_px, _CELL_PX)


def matrix_fragment_from_content(
    content: str,
    baseline: float,
    font_px: float,
    cell_px: float,
    x: float = 0.0,
) -> tuple[str, float] | None:
    """Draw a bracketed matrix inline; return None if it is not a matrix."""
    rows = matrix_rows_from_content(content)
    if rows is None:
        return None
    cells = [[rich_parts(cell) for cell in row] for row in rows]
    return matrix_fragment(cells, baseline, font_px, cell_px, x)


def expand_flat_matrix(match: re.Match[str]) -> str | None:
    """Return SVG for a compact square matrix, or None if it is not one."""
    rows = matrix_rows_from_content(match.group(1))
    if rows is None:
        return None
    return matrix_svg_rows(rows, font_px=11.0)


def _atoms_plain(atoms: list[_MathAtom]) -> str:
    return "".join(
        "".join(part.text for part in atom.parts)
        for atom in atoms
        if isinstance(atom, _TextAtom)
    )


def convert_math_source(source: str) -> str:
    """Convert one .math-source payload to SVG, or plain text if it is prose."""
    atoms = _math_atoms(source)
    if not atoms:
        return ""
    plain = _atoms_plain(atoms)
    # LaTeX math always uses SVG so matrices/commands keep their exact grid,
    # even when the rendered glyphs are plain ASCII digits. "10 Marks" and
    # other plain prose accidentally fenced as math stays ordinary text.
    has_layout = any(
        isinstance(atom, _MatrixAtom)
        or any(part.kind != "normal" or part.fraction is not None for part in atom.parts)
        for atom in atoms
    )
    if not has_layout and not has_symbol(plain) and not re.search(r"\\[A-Za-z]+", source):
        return html_lib.escape(plain)
    return _render_atoms_svg(atoms, _FONT_PX, _CELL_PX)
