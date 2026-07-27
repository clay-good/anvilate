"""Worked derivations: the symbolic formula, the substitution, and the result.

A verdict is not a calculation. What a checker, an engineer of record, or a
permitting jurisdiction reviews is the *work*: the governing formula as the source
writes it, that same formula with the actual values (each carrying its unit) put
in, and the result. This module holds that three-line record.

A :class:`Derivation` is declared next to the check that produces it — the
symbolic form, one :class:`SymbolValue` per input with a plain-language gloss, the
result, and the citation the number rests on. Substitution is mechanical: the
symbolic string is scanned once, left to right, and each declared symbol is
replaced by its rendered value, so no substituted text can ever be substituted
again (a rendered ``"1500.0 N"`` cannot have its ``N`` mistaken for a symbol).

Rendering runs through :mod:`anvilate.units.format`, so every value appears in the
project's unit system at the precision engineers expect for that unit, and the same
derivation renders character-identically on every rebuild.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..units import Quantity, UnitSystem, render

__all__ = [
    "SymbolValue",
    "Derivation",
]


def _is_symbol_char(char: str) -> bool:
    """Whether ``char`` can be part of a symbol name (so a match needs a boundary).

    Covers Latin and Greek letters, digits, underscores, subscript digits, and the
    prime mark — the alphabet handbook symbols are written in (σ_b, τ, d₁, r').
    """
    return char.isalnum() or char in "_'₀₁₂₃₄₅₆₇₈₉"


class SymbolValue(BaseModel):
    """One symbol in a derivation: its name, what it means, and its value.

    ``symbol`` is the token as it appears in the symbolic formula (``"M"``,
    ``"σ_b"``), ``description`` the plain-language gloss a reviewer unfamiliar with
    the source text needs, and ``value`` either a :class:`~anvilate.units.Quantity`
    or a bare float for a genuinely dimensionless number (a friction coefficient, a
    count). ``unit`` forces a display unit; without it the value renders in the
    report's unit system.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    description: str
    value: Quantity | float
    unit: str | None = None

    def rendered(self, *, system: UnitSystem | None = None) -> str:
        """The value as it appears in a substituted formula, with its unit."""
        if isinstance(self.value, Quantity):
            if self.unit is not None:
                return render(self.value, unit=self.unit, pretty=True)
            return render(self.value, system=system, pretty=True)
        # A dimensionless number: %g keeps 0.3 as "0.3" and 12.0 as "12", and is
        # stable across rebuilds.
        return f"{self.value:g}"


class Derivation(BaseModel):
    """A check's worked calculation: formula, substitution, result, citation.

    ``symbolic`` is the governing formula written the way the source writes it
    (``"σ_b = M · c / I"``); ``inputs`` supply every symbol on its right-hand side;
    ``result`` is the left-hand side with the computed value; and ``citation`` names
    the handbook section or standard clause the formula comes from. Every symbol
    used carries its own glossary line, so the derivation is readable without the
    source book open.
    """

    model_config = ConfigDict(frozen=True)

    symbolic: str
    inputs: tuple[SymbolValue, ...]
    result: SymbolValue
    citation: str

    def substituted(self, *, system: UnitSystem | None = None) -> str:
        """The symbolic formula with every input symbol replaced by its value.

        The left-hand side keeps its symbol — the reader is looking for what the
        formula produces, not a restatement of the answer — and every right-hand
        symbol becomes a rendered value with its unit.
        """
        by_symbol = {inp.symbol: inp.rendered(system=system) for inp in self.inputs}
        lhs, sep, rhs = self.symbolic.partition("=")
        if not sep:
            return _substitute(self.symbolic, by_symbol)
        return f"{lhs}={_substitute(rhs, by_symbol)}"

    def unresolved_symbols(self) -> tuple[str, ...]:
        """Symbols left standing on the right-hand side after substitution.

        A non-empty result means the derivation declares fewer inputs than its
        formula uses, so the rendered work would show a bare symbol where a number
        belongs. Callers gate on this; the report refuses to render such a
        derivation as worked.
        """
        _, sep, rhs = self.symbolic.partition("=")
        source = rhs if sep else self.symbolic
        declared = {inp.symbol for inp in self.inputs}
        return tuple(sorted(set(_tokens(source)) - declared))

    def lines(self, *, system: UnitSystem | None = None) -> tuple[str, str, str]:
        """The three lines of the worked calculation: formula, substitution, result."""
        return (
            self.symbolic,
            self.substituted(system=system),
            f"{self.result.symbol} = {self.result.rendered(system=system)}",
        )

    def glossary(self, *, system: UnitSystem | None = None) -> tuple[tuple[str, str, str], ...]:
        """Every symbol in the derivation as ``(symbol, description, value)`` rows."""
        return tuple(
            (item.symbol, item.description, item.rendered(system=system))
            for item in (*self.inputs, self.result)
        )


def _tokens(text: str) -> list[str]:
    """Every maximal run of symbol characters in ``text``."""
    tokens: list[str] = []
    current: list[str] = []
    for char in text:
        if _is_symbol_char(char):
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return [token for token in tokens if not token.replace(".", "").isdigit()]


def _substitute(text: str, by_symbol: dict[str, str]) -> str:
    """Replace declared symbols in ``text`` with their rendered values.

    Scans once, left to right, taking the longest declared symbol that matches at
    each position with symbol-character boundaries on both sides. Because output is
    emitted rather than rescanned, a substituted value is never itself substituted.
    """
    if not by_symbol:
        return text
    candidates = sorted(by_symbol, key=len, reverse=True)
    out: list[str] = []
    index = 0
    while index < len(text):
        matched = None
        # A symbol can only start here if the previous character is not itself a
        # symbol character (otherwise we would be mid-token).
        if index == 0 or not _is_symbol_char(text[index - 1]):
            for symbol in candidates:
                end = index + len(symbol)
                if text.startswith(symbol, index) and (
                    end == len(text) or not _is_symbol_char(text[end])
                ):
                    matched = symbol
                    break
        if matched is None:
            out.append(text[index])
            index += 1
        else:
            out.append(by_symbol[matched])
            index += len(matched)
    return "".join(out)
