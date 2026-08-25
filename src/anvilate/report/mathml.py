"""Derivation formulas as MathML, or not at all.

A calculation report's whole claim is that a reviewer can check the work. A linear string —
``σ_b = M · c / I`` — is checkable; the same formula with the fraction stacked and the
radical drawn is checkable *faster*, which is the entire value of typesetting it. So the
symbolic and substituted lines render as MathML where they can.

**MathML rather than a script or a picture, and the reason is the air gap.** MathML Core is
laid out by the browser itself, so the report stays one self-contained file with no external
asset, no script, and no font to ship — which is what the report's air-gapped render test
already requires. MathJax would mean bundling a JavaScript engine into a document an
engineer of record may seal; a drawn SVG would mean shipping a layout engine and a font
inside this library. Both are larger commitments than stacking a fraction is worth.

**The formula that does not round-trip is not typeset.** This module parses the restricted
grammar the library's derivations are written in, and before emitting anything it writes the
parse tree back out and compares it, ignoring whitespace, to the string it was given. A
mismatch means the parse is not the formula the check cited, and the caller falls back to the
plain-text line. That is the same rule the derivation layer already follows for a numerically
solved result: **a tidy rendering of something other than what was computed is worse than an
untidy rendering of the truth**, and in a document somebody seals it is much worse.

**The round trip is necessary and it is not sufficient**, which is worth stating because it
is easy to trust it further than it goes. It catches a token dropped, added or reordered; it
cannot catch a *precedence* error, because the wrong tree writes back out as exactly the
string it came from. One shipped in the first draft — juxtaposition at the same precedence as
division read a substituted ``1.00 kN / 10.00 mm²`` as ``(1.00 kN / 10.00) · mm²``, a stress
drawn as a force over a number times an area. What found it was rendering a real report, not
a unit test, which is why CI typesets the library's whole derivation corpus rather than a few
examples.

The grammar is deliberately small, because it is not a general mathematical typesetter — it
is a renderer for formulas this library writes:

* names (``M``, ``σ_b``, ``f′c``, ``d₁``), numbers, and juxtaposition as multiplication
  (``6.00 mm``, a value beside its unit)
* ``·`` and ``*`` for product, ``/`` for quotient, ``+`` and ``-``/``−`` for sum
* ``**`` and the superscript digits ``x²`` for powers
* ``√`` for a square root, and parentheses
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape

__all__ = ["formula_to_mathml"]

# The superscript digits, and the ordinary digit each one means. A formula writes ``d²``;
# MathML wants the 2 as an exponent, and the round-trip has to put the ⁴ back.
_SUPERSCRIPT_DIGITS = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
}

_PRODUCT = ("·", "*")
_SUM = ("+", "-", "−")


def _is_name_char(char: str) -> bool:
    """Whether ``char`` continues a symbol name.

    The same alphabet :mod:`anvilate.derivation` substitutes over — Latin and Greek
    letters, digits, underscores, subscript digits and both prime marks — minus the
    superscript digits, which exponentiate a name rather than belong to it.
    """
    if char in _SUPERSCRIPT_DIGITS:
        return False
    return char.isalnum() or char in "_'′₀₁₂₃₄₅₆₇₈₉"


@dataclass(frozen=True)
class _Node:
    """One parsed piece. ``kind`` decides how ``text`` and ``children`` are read."""

    kind: str
    text: str = ""
    children: tuple[_Node, ...] = ()


class _ParseError(Exception):
    """The formula is outside the grammar. Callers fall back to plain text."""


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith("**", index):
            tokens.append("**")
            index += 2
            continue
        if char in _SUPERSCRIPT_DIGITS:
            run = ""
            while index < len(text) and text[index] in _SUPERSCRIPT_DIGITS:
                run += text[index]
                index += 1
            tokens.append(run)
            continue
        if char.isdigit():
            run = ""
            # One decimal point, and only between digits: "1.5" is a number, "1." is not,
            # and neither is the "." of an ellipsis or an abbreviation.
            while index < len(text) and (
                text[index].isdigit()
                or (
                    text[index] == "."
                    and "." not in run
                    and index + 1 < len(text)
                    and text[index + 1].isdigit()
                )
            ):
                run += text[index]
                index += 1
            # A digit run that flows straight into letters is a name, not a number beside
            # a unit: "2A" is one symbol nobody declared, and calling it 2 times A would
            # invent an operator the formula does not contain.
            if index < len(text) and _is_name_char(text[index]) and not text[index].isdigit():
                while index < len(text) and _is_name_char(text[index]):
                    run += text[index]
                    index += 1
            tokens.append(run)
            continue
        if _is_name_char(char):
            run = ""
            while index < len(text) and _is_name_char(text[index]):
                run += text[index]
                index += 1
            tokens.append(run)
            continue
        if char in {*_PRODUCT, *_SUM, "/", "(", ")", "√"}:
            tokens.append(char)
            index += 1
            continue
        raise _ParseError(f"{char!r} is not part of the formula grammar")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._at = 0

    def _peek(self) -> str | None:
        return self._tokens[self._at] if self._at < len(self._tokens) else None

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise _ParseError("the formula ends in the middle of an expression")
        self._at += 1
        return token

    def parse(self) -> _Node:
        node = self._sum()
        if self._peek() is not None:
            raise _ParseError(f"trailing {self._peek()!r}")
        return node

    def _sum(self) -> _Node:
        node = self._product()
        while (token := self._peek()) in _SUM and token is not None:
            self._take()
            node = _Node("binary", token, (node, self._product()))
        return node

    def _product(self) -> _Node:
        node = self._juxtaposition()
        while (token := self._peek()) in (*_PRODUCT, "/") and token is not None:
            self._take()
            node = _Node("binary", token, (node, self._juxtaposition()))
        return node

    def _juxtaposition(self) -> _Node:
        """Two factors written with no operator between them: a value beside its unit.

        **Binds tighter than division, and that is not a stylistic choice.** At the same
        precedence, "1.00 kN / 10.00 mm²" reads left to right as
        "(1.00 kN / 10.00) · mm²" — a stress rendered as a force over a number, times an
        area. The round trip cannot see it: the wrong tree writes back out as exactly the
        string it came from. It took a report rendering a real substituted line to surface,
        which is the argument for typesetting the corpus in CI rather than a few examples.
        """
        node = self._power()
        while (token := self._peek()) is not None and (
            token[0].isdigit() or _is_name_char(token[0]) or token in {"(", "√"}
        ):
            node = _Node("binary", "", (node, self._power()))
        return node

    def _power(self) -> _Node:
        node = self._atom()
        token = self._peek()
        if token == "**":
            self._take()
            return _Node("power", "**", (node, self._power()))
        if token is not None and token[0] in _SUPERSCRIPT_DIGITS:
            self._take()
            digits = "".join(_SUPERSCRIPT_DIGITS[char] for char in token)
            return _Node("superscript", token, (node, _Node("number", digits)))
        return node

    def _atom(self) -> _Node:
        token = self._take()
        if token == "√":
            return _Node("root", "√", (self._atom(),))
        if token == "(":
            inner = self._sum()
            if self._take() != ")":
                raise _ParseError("unbalanced parentheses")
            return _Node("group", "", (inner,))
        if token[0].isdigit():
            return _Node("number", token)
        if _is_name_char(token[0]):
            return _Node("name", token)
        raise _ParseError(f"{token!r} cannot start an expression")


def _unparse(node: _Node) -> str:
    """The parse tree written back out, for comparison against the input."""
    if node.kind in {"number", "name"}:
        return node.text
    if node.kind == "group":
        return f"({_unparse(node.children[0])})"
    if node.kind == "root":
        return f"√{_unparse(node.children[0])}"
    if node.kind == "superscript":
        return f"{_unparse(node.children[0])}{node.text}"
    if node.kind == "power":
        return f"{_unparse(node.children[0])}**{_unparse(node.children[1])}"
    return f"{_unparse(node.children[0])}{node.text}{_unparse(node.children[1])}"


def _name_element(text: str) -> str:
    """A symbol as MathML, splitting an underscore subscript into ``msub``.

    ``σ_b`` is sigma-sub-b and reads as one symbol; the subscript digits in ``d₁`` are
    already laid out by the font, so they stay inside the ``mi`` where the round-trip can
    put them back verbatim.
    """
    base, sep, subscript = text.partition("_")
    if not sep or not base or not subscript:
        return f"<mi>{escape(text)}</mi>"
    return f"<msub><mi>{escape(base)}</mi><mi>{escape(subscript)}</mi></msub>"


def _emit(node: _Node, *, unwrap: bool = False) -> str:
    """One node as MathML.

    ``unwrap`` drops a redundant pair of parentheses where the surrounding construct
    already groups — a fraction's numerator, a radicand. That is the only liberty taken
    with the author's text, and it cannot change what the formula means, because an
    ``mfrac`` and an ``msqrt`` group their arguments by construction.
    """
    if node.kind == "number":
        return f"<mn>{escape(node.text)}</mn>"
    if node.kind == "name":
        return _name_element(node.text)
    if node.kind == "group":
        inner = _emit(node.children[0])
        if unwrap:
            return inner
        return f"<mo>(</mo>{inner}<mo>)</mo>"
    if node.kind == "root":
        return f"<msqrt>{_emit(node.children[0], unwrap=True)}</msqrt>"
    if node.kind in {"superscript", "power"}:
        return (
            f"<msup><mrow>{_emit(node.children[0])}</mrow>"
            f"<mrow>{_emit(node.children[1], unwrap=True)}</mrow></msup>"
        )
    left, right = node.children
    if node.text == "/":
        return (
            f"<mfrac><mrow>{_emit(left, unwrap=True)}</mrow>"
            f"<mrow>{_emit(right, unwrap=True)}</mrow></mfrac>"
        )
    if node.text == "":
        # Juxtaposition. A thin space, so a value does not run into its unit.
        return f"{_emit(left)}<mspace width='0.17em'/>{_emit(right)}"
    return f"{_emit(left)}<mo>{escape(node.text)}</mo>{_emit(right)}"


def formula_to_mathml(formula: str) -> str | None:
    """``formula`` as a MathML ``<math>`` element, or ``None`` if it cannot be trusted.

    ``None`` on anything the grammar does not cover **and** on anything that parses to a
    tree which does not write back out as the same string. The caller renders the plain
    text instead: a report that shows a stacked fraction of a formula the check did not
    cite is a document that lies more convincingly than one that shows a line of text.

    An ``=`` splits the formula into a left and a right side, each typeset on its own; a
    second ``=`` is outside the grammar and falls back.
    """
    left, sep, right = formula.partition("=")
    if sep and "=" in right:
        return None
    parts = [left, right] if sep else [formula]
    emitted: list[str] = []
    for part in parts:
        if not part.strip():
            return None
        try:
            tree = _Parser(_tokenize(part)).parse()
        except _ParseError:
            return None
        if "".join(_unparse(tree).split()) != "".join(part.split()):
            return None
        emitted.append(_emit(tree))
    body = "<mo>=</mo>".join(emitted)
    return f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">{body}</math>'
