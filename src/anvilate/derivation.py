"""Worked derivations: the symbolic formula, the substitution, and the result.

A verdict is not a calculation. What a checker, an engineer of record, or a
permitting jurisdiction reviews is the *work*: the governing formula as the source
writes it, that same formula with the actual values (each carrying its unit) put
in, and the result. This module holds that three-line record.

A :class:`Derivation` is declared next to the check that produces it — the
symbolic form, one :class:`SymbolValue` per input with a plain-language gloss, the
result, and the citation the number rests on — and rides on the
:class:`~anvilate.scorecard.ScorecardEntry` the check returns, so the work travels
with the verdict instead of being reconstructed by whoever renders it later.
Substitution is mechanical: the
symbolic string is scanned once, left to right, and each declared symbol is
replaced by its rendered value, so no substituted text can ever be substituted
again (a rendered ``"1500.0 N"`` cannot have its ``N`` mistaken for a symbol).

Rendering runs through :mod:`anvilate.units.format`, so every value appears in the
project's unit system at the precision engineers expect for that unit, and the same
derivation renders character-identically on every rebuild.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._models import Provenance
from .units import Quantity, UnitSystem, render

__all__ = [
    "SymbolValue",
    "Derivation",
    "DerivationAbsence",
    "Underived",
]


# Superscript digits exponentiate a symbol rather than naming it: the λ in "λ²" is
# the same λ the caller declares. Subscripts do the opposite — A₁ and A₂ are two
# different areas — so they stay part of the name.
_SUPERSCRIPTS = frozenset("⁰¹²³⁴⁵⁶⁷⁸⁹")


def _is_symbol_char(char: str) -> bool:
    """Whether ``char`` can be part of a symbol name (so a match needs a boundary).

    Covers Latin and Greek letters, digits, underscores, subscript digits, both prime
    marks, and the perpendicular sign — the alphabet handbook symbols are written in
    (σ_b, τ, d₁, r', f′c, and the NDS bearing value F'_c⊥, where ⊥ is part of the name
    and not an operator).
    """
    if char in _SUPERSCRIPTS:
        return False
    return char.isalnum() or char in "_'′⊥₀₁₂₃₄₅₆₇₈₉"


# Mathematical constants a formula may name without them being inputs: they carry
# no value the caller supplies, so they are not missing when left unsubstituted.
#
# `e` is deliberately NOT in this set. In engineering formulas `e` is the eccentricity far
# more often than it is Euler's number (σ = P/A + P·e/S), and excusing it meant a
# derivation that forgot to declare its eccentricity reported zero unresolved symbols,
# rendered as a complete worked calculation with a bare `e` where a dimensioned number
# belongs, and was counted by `derivation_coverage()` as covered. A formula that really
# does use Euler's number declares it as an input like any other value; a false gap is a
# nuisance, a hidden one is the failure `is_worked` exists to prevent.
_CONSTANTS = frozenset({"π"})

# Operators a formula writes as a word rather than as a sign. `min` in
# "k_a = min(1, a·S_u^b)" is not an input the caller forgot to declare — it is the cap
# itself, and the cap is the part of that formula that matters: the fit crosses one for a
# ground surface on low-strength steel, so a derivation of "k_a = a·S_u^b" alone would
# disagree with the value used wherever the cap binds. Excusing the word is what lets the
# capped form be written at all.
_OPERATORS = frozenset({"min", "max"})


class DerivationAbsence(StrEnum):
    """Why a check renders no worked calculation — the two kinds that are finished.

    Neither is a shortfall. A ``LOOKUP`` has no arithmetic between its two numbers:
    an exemption, an identification line, a table comparison, a consistency verdict.
    A ``NUMERIC_RESULT`` has real mathematics behind it and no substitutable line —
    its value is the root of an equation, solved rather than evaluated, so the
    inputs/outputs table is the correct rendering for it rather than a shortfall.

    The third kind a check can be in — **debt**, a closed form nobody has written
    down yet — is deliberately not a member. Debt is the *absence* of a declaration,
    recorded per clause in ``docs/api/underived-checks.txt`` where the ratchet keeps
    the list downward-only. Making it declarable here would let a check retire its
    own debt by describing it, which is the collapse this vocabulary exists to refuse.
    """

    LOOKUP = "lookup"
    NUMERIC_RESULT = "numeric_result"


class Underived(BaseModel):
    """A check's own statement that it has no formula to show, and why.

    It rides on the :class:`~anvilate.scorecard.ScorecardEntry` in the place the
    :class:`Derivation` would have taken, so it travels into the evidence bundle and
    the JSON alongside the verdict it explains. That is the point of putting it here
    rather than in a file addressed by citation: a clause cited by two checks — one
    that computes and one that does not — cannot be answered once.
    """

    model_config = ConfigDict(frozen=True)

    kind: DerivationAbsence
    # A reason that says nothing is the silence this declaration replaces, so a blank
    # one is refused rather than stored. The requirement's own words are "registered
    # as tabular-only WITH A STATED REASON".
    reason: str

    @field_validator("reason")
    @classmethod
    def _reason_must_say_something(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "an Underived declaration needs a stated reason; a blank one is the "
                "silence the declaration exists to replace"
            )
        return value

    def __str__(self) -> str:
        return f"{self.kind.value}: {self.reason}"


class SymbolValue(BaseModel):
    """One symbol in a derivation: its name, what it means, and its value.

    ``symbol`` is the token as it appears in the symbolic formula (``"M"``,
    ``"σ_b"``), ``description`` the plain-language gloss a reviewer unfamiliar with
    the source text needs, and ``value`` either a :class:`~anvilate.units.Quantity`
    or a bare float for a genuinely dimensionless number (a friction coefficient, a
    count). ``unit`` is a *preferred* display unit, used only when the document declares
    no unit system; a document that declares one gets that system. Set ``unit_is_required``
    where the preference is arithmetic rather than taste — see the field.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    description: str
    value: Quantity | float
    # A preference, not a pin — the system is the reader's stated choice and this is the
    # library's taste. It used to win either way, and eighty-seven of these across the
    # packs meant a US-customary report rendered
    #     σ_b = 10.00 kN·m · 2.953 in / 28125000.00 mm⁴
    # — three unit systems in one substituted line, arriving at ksi by conversions the
    # document does not show. A reviewer cannot check that line by hand, which is the only
    # thing the line is for.
    #
    # Nothing in the arithmetic wanted it: every formula in this library is dimensionally
    # homogeneous, and `anvilate.units.render` already picks units that COMPOSE within a
    # system — N·mm, mm, mm⁴, MPa for SI; kip·in, in, in⁴, ksi for US. The preference was
    # destroying exactly that property. It is kept for the document that declares nothing,
    # where the packs' per-discipline choices (kPa for a soil pressure, m for a pump head)
    # are what a reader of that discipline expects and SI's canonical units are not.
    unit: str | None = None
    # Set where the preferred unit is not taste but arithmetic: the system's table maps one
    # unit per DIMENSION, and a dimension can mean two things. `[length]³` is a section
    # modulus in nine derivations out of ten and the table says so — which renders a room's
    # volume as 1,415,842,329,600.00 mm³ beside an airflow in ft³/min, a line off by nine
    # orders of magnitude. A symbol the table would mangle keeps its unit under every
    # system; everything else yields to the reader's.
    unit_is_required: bool = False

    def rendered(self, *, system: UnitSystem | None = None) -> str:
        """The value as it appears in a substituted formula, with its unit."""
        if isinstance(self.value, Quantity):
            if self.unit is not None and (system is None or self.unit_is_required):
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
    # At least one. A derivation with no inputs renders as its own formula with
    # nothing substituted into it — which is the reconstruction this type exists to
    # replace, dressed as a worked calculation.
    inputs: tuple[SymbolValue, ...] = Field(min_length=1)
    result: SymbolValue
    citation: Provenance

    def substituted(self, *, system: UnitSystem | None = None) -> str:
        """The symbolic formula with every input symbol replaced by its value.

        The left-hand side keeps its symbol — the reader is looking for what the
        formula produces, not a restatement of the answer — and every right-hand
        symbol becomes a rendered value with its unit.
        """
        lhs, sep, rhs = self.symbolic.partition("=")
        substituted, _ = _scan(rhs if sep else self.symbolic, self._by_symbol(system))
        return substituted if not sep else f"{lhs}={substituted}"

    def unresolved_symbols(self) -> tuple[str, ...]:
        """Symbols left standing on the right-hand side after substitution.

        A non-empty result means the derivation declares fewer inputs than its
        formula uses, so the rendered work would show a bare symbol where a number
        belongs. Callers gate on this; the report refuses to render such a
        derivation as worked. Mathematical constants (π, e) and word-operators
        (``min``, ``max``) are not missing inputs and never appear here.
        """
        _, sep, rhs = self.symbolic.partition("=")
        _, leftover = _scan(rhs if sep else self.symbolic, self._by_symbol(None))
        return tuple(sorted(set(leftover) - _CONSTANTS - _OPERATORS))

    def _by_symbol(self, system: UnitSystem | None) -> dict[str, str]:
        return {inp.symbol: inp.rendered(system=system) for inp in self.inputs}

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


def _scan(text: str, by_symbol: dict[str, str]) -> tuple[str, list[str]]:
    """Substitute declared symbols in ``text``, reporting the ones left standing.

    One left-to-right pass does both jobs, so what the reader sees and what the
    coverage check counts can never disagree. At each position the longest declared
    symbol that matches with symbol-character boundaries on both sides wins; because
    output is emitted rather than rescanned, a substituted value is never itself
    substituted (the ``N`` in a rendered ``"1500.0 N"`` is not the symbol ``N``).
    Anything else that reads as a symbol — a name the derivation never declared — is
    passed through untouched and returned as leftover.
    """
    candidates = sorted(by_symbol, key=len, reverse=True)
    out: list[str] = []
    leftover: list[str] = []
    index = 0
    while index < len(text):
        # A symbol can only start here if the previous character is not itself a
        # symbol character (otherwise we would be mid-token).
        at_boundary = index == 0 or not _is_symbol_char(text[index - 1])
        matched = None
        if at_boundary:
            for symbol in candidates:
                end = index + len(symbol)
                if text.startswith(symbol, index) and (
                    end == len(text) or not _is_symbol_char(text[end])
                ):
                    matched = symbol
                    break
        if matched is not None:
            index += len(matched)
            value = by_symbol[matched]
            # An exponent applies to the whole value, so it has to be bracketed:
            # "d²" with d = 16 mm is "(16.00 mm)²", never "16.00 mm²" — which a
            # reviewer would read as an area.
            if index < len(text) and text[index] in _SUPERSCRIPTS:
                value = f"({value})"
            out.append(value)
            continue
        if at_boundary and _is_symbol_char(text[index]):
            # An undeclared name: take the whole token so a multi-character symbol
            # is reported as itself rather than as its letters.
            end = index
            while end < len(text) and _is_symbol_char(text[end]):
                end += 1
            token = text[index:end]
            if not token.replace(".", "").isdigit():
                leftover.append(token)
            out.append(token)
            index = end
            continue
        out.append(text[index])
        index += 1
    return "".join(out), leftover
