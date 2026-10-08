"""The :class:`Quantity` type: a magnitude plus an explicit unit.

Quantities are the only way a physical value enters the Spec IR. They carry the
unit *as entered* so the spec card can echo it and line-based diffs stay
meaningful, while exposing the canonical Pint quantity on demand for
computation and conversion. Dimensional consistency is checked on construction
and again wherever a field pins an expected dimension.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from functools import lru_cache
from math import isfinite
from typing import Any

import pint
from pydantic import ConfigDict, model_validator

from .._models import RevalidatedModel
from ..refusal import RefusalError, Remedy
from .registry import UREG

__all__ = [
    "Quantity",
    "UnitError",
    "MissingUnitError",
    "DimensionError",
    "require_dimension",
    "require_finite",
]


# The offset temperature units pint constructs but will not parse from a string, and the
# angle units it parses as dimensionless. Both are spellings this library emits.
_OFFSET_TEMPERATURE_UNITS = frozenset(
    {"degc", "degf", "celsius", "fahrenheit", "degree_celsius", "degree_fahrenheit"}
)
# The angle units, by identity rather than by dimensionality: pint gives an angle the
# same empty dimensionality as a ratio, so `12 %` converts to radians perfectly happily
# and only the unit itself says which of the two a value is.
_ANGLE_UNITS = frozenset(
    UREG.Unit(name)
    for name in (
        "radian",
        # Pointing and line-of-sight errors are written in the prefixed radians, and the
        # library prints them; leaving them out refused "50 µrad" as a bare number.
        "milliradian",
        "microradian",
        "nanoradian",
        "degree",
        "arcminute",
        "minute_of_angle",
        "arcsecond",
        "gradian",
        "turn",
    )
)


def _offset_temperature(text: str) -> pint.Quantity | None:
    """``text`` as an offset-temperature quantity, or ``None`` if it is not one.

    Deliberately narrow: only a plain magnitude followed by an offset temperature unit.
    Anything else — a range, a tolerance, a second value hiding in the unit half — falls
    through to the text parser's refusal, which is the behaviour that keeps
    ``"45-50 kN"`` from becoming 2250 kN.
    """
    match = re.fullmatch(r"\s*([-+]?[\d.eE+]+)\s*(°?[A-Za-z_]+)\s*", text)
    if match is None:
        return None
    spelling = match.group(2)
    # `C` alone is the coulomb and stays the coulomb; `°C` is not ambiguous. Requiring the
    # degree sign cannot be reached today — a bare `C` parses as the coulomb, so this
    # fallback never sees one — and it is here so that if that ever stops being true the
    # fallback cannot invent a temperature out of a charge.
    named = spelling.lower().lstrip("°")
    degrees = spelling.startswith("°")
    if named not in _OFFSET_TEMPERATURE_UNITS and not (degrees and named in {"c", "f"}):
        return None
    if degrees:
        spelling = "degC" if named in {"c", "celsius"} else "degF"
    try:
        return UREG.Quantity(float(match.group(1)), match.group(2))
    except Exception:
        return None


def _is_angle(quantity: pint.Quantity) -> bool:
    """Whether a dimensionless pint quantity carries an angle unit rather than none."""
    return quantity.units in _ANGLE_UNITS


# The leading magnitude of a quantity: a decimal, optionally signed, with an exponent, or a
# simple fraction ("3/4 in").
_MAGNITUDE = re.compile(r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:\s*/\s*\d+)?")
# What a unit may hold a number for: an exponent, and the "1/" of a reciprocal the library
# itself writes ("10 1/s").
_EXPONENT = re.compile(r"(?:\*\*|\^)\s*\(?\s*[+-]?\d+(?:\.\d+)?\s*\)?")
_RECIPROCAL = re.compile(r"^\s*\(?\s*1\s*/")
# A number not glued to a unit name: `inch_H2O_39F` is one unit, `mm 2` is two tokens.
_LOOSE_NUMBER = re.compile(r"(?<!\w)\d")


def _not_one_quantity(text: str) -> str | None:
    """Why ``text`` is not one magnitude and one unit, or ``None`` when it is.

    pint reads juxtaposition as multiplication and drops what it cannot tokenize, so every
    shape below parsed, to a number nobody wrote: "1 000 mm" as 1 × 000 = 0 mm, "1,5 mm"
    (a decimal comma) as 15 mm, "10 mm ± 0.1" as 1 mm, the range "45–50 kN" as 2,250 kN,
    and "–10 mm" with an en dash as +10 mm.
    """
    if "," in text:
        return (
            "writes its magnitude with a comma, which is a thousands separator in one "
            "convention and the decimal point in another (1,500 is 1500 or 1.5); write the "
            "number with no separators and a point for the decimal"
        )
    if "±" in text:
        return "carries a tolerance; a quantity is one value, and a tolerance is stated apart"
    dashes = sorted({c for c in text if c != "-" and unicodedata.category(c) == "Pd"})
    if dashes:
        names = ", ".join(f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in dashes)
        return (
            f"contains {names}, which is neither a minus sign nor part of a unit; a range is "
            "two quantities, and a negative value is written with '-'"
        )
    magnitude = _MAGNITUDE.match(text)
    if magnitude is None:
        return None
    unit = _RECIPROCAL.sub("", _EXPONENT.sub("", text[magnitude.end() :]))
    if _LOOSE_NUMBER.search(unit) is None:
        return None
    # Thousands grouping is three digits a group: "1 000" is that, "45 50" is two numbers.
    if re.fullmatch(r"\d{1,3}", magnitude.group().strip().lstrip("+-")) and re.match(
        r"(?:[\s\u00a0\u2009\u202f]+\d{3})+(?!\d)", text[magnitude.end() :]
    ):
        return (
            "separates digits with a space, which reads as multiplication "
            "(1 000 is 1 × 000 = 0); write the number with no separators"
        )
    return "holds a second number; a quantity is one magnitude and one unit"


class UnitError(RefusalError, ValueError):
    """A unit or dimension request that cannot be used without correction."""

    def __init__(
        self,
        message: str,
        *,
        action: str = "correct",
        subject: str = "the unit or quantity named in this refusal",
        source: str = "the originating document and the applicable unit definition",
    ) -> None:
        super().__init__(
            message,
            remedies=(Remedy(action=action, subject=subject, source=source),),
        )


class MissingUnitError(UnitError):
    """A physical quantity was given without a unit; we never assume one."""


class DimensionError(UnitError):
    """A quantity's dimension does not match what a field requires."""


# Named dimension tokens, tried in order to give a readable name to a
# quantity's dimensionality (e.g. "[pressure]" rather than the base
# "[mass] / [length] / [time] ** 2").
_NAMED_DIMENSIONS = (
    "[force]",
    "[pressure]",
    "[length]",
    "[mass]",
    "[time]",
    "[area]",
    "[volume]",
    "[energy]",
)


def _friendly_dimension(dimensionality: Any) -> str:
    """A readable name for a Pint dimensionality, falling back to the base form."""
    for token in _NAMED_DIMENSIONS:
        if dimensionality == UREG.get_dimensionality(token):
            return token
    return str(dimensionality)


# BIPM and NIST both allow "L" for the litre, and for one reason: the lowercase "l" is a
# glyph away from the digit 1, so "1 l/s" and "11/s" are hard to tell apart in a printed
# submittal. Pint normalises every litre to the lowercase spelling on the way in, so a
# spec written "50 L/s" was read back to its author as "50.00 l / s" — a different symbol
# from the one they typed, in the document they are asked to check.
#
# The stored `unit` keeps Pint's spelling, which is what a machine record wants and what
# every serialiser round-trips through. This is the DISPLAY spelling, applied by
# `Quantity.__str__` and by `anvilate.units.render`, and what it produces parses back.
#
# The prefix alternatives are what keep it off other units: "mol", "cal", "lm", "lx" and
# "mil" all contain an l and none of them is a litre. Only a bare l, optionally behind an
# SI prefix and bounded on both sides, is one.
_LITRE = re.compile(
    r"(?<![A-Za-z0-9_])(Y|Z|E|P|T|G|M|k|h|da|d|c|m|µ|μ|u|n|p|f|a|z|y)?l(?![A-Za-z0-9_])"
)
_SUPERSCRIPT_DIGITS = frozenset("⁰¹²³⁴⁵⁶⁷⁸⁹")


def _stable_short_unit(label: str) -> str:
    """Pint's machine spelling with its version-dependent micro glyph stabilized."""
    return label.replace("μ", "µ")


def display_unit(label: str) -> str:
    """A stable unit label as a document writes it.

    Pint 0.26 changed its Unicode product from the middle dot to the dot operator and its
    micro prefix from the micro sign to Greek mu. Both are mathematically equivalent, but
    neither is equivalent in a signed report or a line-based diff. Normalize those
    dependency-controlled glyphs here, beside the existing litre normalization, so every
    document surface keeps one spelling across supported Pint releases.
    """
    # The same ``⋅`` is also Pint's decimal point in a superscript exponent (``MPa⁰⋅⁵``).
    # Preserve that case; it is a number, not a product separator.
    stable = "".join(
        "·"
        if character == "⋅"
        and not (
            index > 0
            and index + 1 < len(label)
            and label[index - 1] in _SUPERSCRIPT_DIGITS
            and label[index + 1] in _SUPERSCRIPT_DIGITS
        )
        else character
        for index, character in enumerate(label)
    )
    stable = _stable_short_unit(stable)
    return _LITRE.sub(lambda match: f"{match.group(1) or ''}L", stable)


@lru_cache(maxsize=8192)
def _unit_object(unit: str) -> pint.Unit:
    """``UREG.Unit(unit)``, parsed once per spelling.

    Every construction validates its unit and every conversion builds a pint quantity, and
    both parsed the unit *string* again each time — 310 pint unit parses per lifting lug
    screened. The registry's unit objects are immutable and the spelling is the whole of the
    key, so the parse is memoised here rather than repeated at each call site.

    It is also the one place an unreadable spelling can become this library's own refusal.
    `UREG.Unit` answers one with pint's `UndefinedUnitError`, which is an **AttributeError**
    — the most misleading signal available, because it reads as a bug in the callee rather
    than a typo in the argument, and it escapes every `except ValueError` guard in the
    library and in its callers. `Quantity.parse` already raised `UnitError` for the same
    mistake at the front door, while `Quantity.to("mm2")`, `render(unit="mm2")` and
    `decimals_for("mm2")` all leaked pint's. `mm2` for `mm**2` is a spelling somebody types.
    """
    try:
        return UREG.Unit(unit)
    except Exception as failure:
        # `except Exception`, deliberately, and it is the second version of this guard. The
        # first caught `PintError` and covered **2 of 26** ways a malformed spelling actually
        # fails. Over 37 odd strings pint answers with a bare `AssertionError` 22 times — for
        # `-`, `+`, `*`, `/`, `**` among them — with an EMPTY message, which is the worst
        # failure available: no message, no type information, and it reads as a broken
        # invariant rather than a typo. Two more come out of Python's own tokenizer as
        # `TokenError`. Only one is `UndefinedUnitError`.
        #
        # `-` matters most: it is what an engineer writes for "no units" on every drawing
        # there is, and it reached `Quantity.to`, `render` and `decimals_for`.
        #
        # Enumerating a dependency's undocumented failure modes is a list that goes stale, and
        # this function has exactly one job — turn a string into a Unit. Any failure to do
        # that is an unreadable spelling, so any failure gets the same sentence. The message
        # is kept when there is one, and named when there is not.
        detail = str(failure) or f"{type(failure).__name__} with no message"
        raise UnitError(
            f"could not read the unit {unit!r}: {detail}",
            action="replace",
            subject=f"the unit expression {unit!r}",
            source="a valid spelling from the bundled unit registry",
        ) from failure


@lru_cache(maxsize=8192)
def _short_spelling(unit: str) -> str:
    """The short (``~``) spelling of ``unit``, formatted once per spelling.

    `to()` rendered `f"{converted.units:~}"` on every conversion, and the target units are
    `_unit_object(unit)` — so the spelling is a pure function of the argument that was being
    recomputed through pint's formatter at each call. It was 2,400 `format_unit` calls and
    13% of the time to screen one lifting lug.
    """
    return _stable_short_unit(f"{_unit_object(unit):~}")


@lru_cache(maxsize=8192)
def _dimensionality_of_unit(unit: str) -> object:
    """The dimensionality of ``unit``, derived once per spelling.

    `has_dimension` read `self.pint.dimensionality`, which builds a whole pint Quantity —
    magnitude, registry dispatch and all — to answer a question about the unit alone. The
    dimensionality of a quantity is the dimensionality of its units, and the spelling is the
    whole of the key.
    """
    return _unit_object(unit).dimensionality


@lru_cache(maxsize=1024)
def _dimensionality_of(expected: str) -> object:
    """``UREG.get_dimensionality(expected)``, for the same reason."""
    return UREG.get_dimensionality(expected)


def _dimensionality_str(units: str) -> str:
    """Human-readable dimensionality, e.g. ``[pressure]`` or the base form."""
    return _friendly_dimension(_unit_object(units).dimensionality)


# Case-variant spellings pint accepts that differ from the intended unit by a power of ten
# and **not** by dimension. That combination is the one unit typo a dimension guard
# structurally cannot catch: `Quantity.parse("80 Mm")` is 80 megametres, passes
# `has_dimension("[length]")`, and screens a beam 80,000 km deep as comfortably passing.
#
# Derived rather than remembered: over the 177 units this library converts to, every
# same-dimension case collision is this one root — `Mm` for `mm`, propagated through
# `Mm**4`, `Mm/s` and the rest — plus `ML`/`Ml` for `mL`. The test re-derives the set from
# the registry and fails if pint ever grows another, so this is a probe table and not a
# list of names somebody once wrote down.
#
# The other mis-casings are safe *because* they change dimension: "80 MM" is megamolar and
# "3 PA" is petaamperes, and the guard on every function refuses them by name.
_CASE_TRAPS = {
    "Mm": "megametres, where 'mm' is millimetres — a factor of 1e9 at the same dimension",
    "ML": "megalitres, where 'mL' is millilitres — a factor of 1e9 at the same dimension",
    "Ml": "megalitres, where 'mL' is millilitres — a factor of 1e9 at the same dimension",
}
# The remedy each refusal names, and it has to be one that works: writing the unit out as
# "megameter" does *not*, because pint canonicalises it straight back to "Mm" and lands on
# this same check. Scaling into the base unit does, and a test proves each of these rather
# than quoting it.
_CASE_TRAPS_REMEDY = {
    "Mm": "1 Mm is 1e6 m",
    "ML": "1 ML is 1e3 m**3",
    "Ml": "1 Ml is 1e3 m**3",
}


# A product of units written glued together, the way a moment is written on a drawing. pint
# does not read any of them as the product: `Nm` is number·metre and `kNm` kilo-number·metre
# (both [length]/[mass]), `ftlb` is femto-troy-pounds (a mass), and the rest are undefined.
# A moment field refused `50 kNm` as "not a [force]·[length] quantity", which reads as the
# library being wrong about what a kilonewton-metre is. Each is refused naming the product.
_GLUED_PRODUCTS = {
    "Nm": "N*m",
    "kNm": "kN*m",
    "MNm": "MN*m",
    "Nmm": "N*mm",
    "kNmm": "kN*mm",
    "ftlb": "ft*lbf",
    "ftlbf": "ft*lbf",
    "lbft": "lbf*ft",
    "lbfft": "lbf*ft",
    "inlb": "in*lbf",
    "inlbf": "in*lbf",
    "lbin": "lbf*in",
    "lbfin": "lbf*in",
    "kipft": "kip*ft",
    "ftkip": "ft*kip",
    "kipin": "kip*in",
    "inkip": "in*kip",
}
# `kN-m` and `ft-lb` are the same product with a hyphen, and pint answered them with a bare
# TypeError. A hyphen between two letters is never a unit's own spelling.
_HYPHENATED = re.compile(r"[A-Za-z]-[A-Za-z]")


# What a unit expression is made of. pint drops any other character without a word, so
# `30 MPa√m` was 30 MPa·m, `1 N÷m` and `1 N∕m` were N·m (a division read as a product),
# and `≤ 5 mm` was 5 mm. Letters, digits (superscripts included) and spaces, plus:
_UNIT_PUNCTUATION = frozenset("*/^().-+_·×⋅°%")
# Keyed by name: several of these have no glyph in the report font, and the PDF gate reads
# every string constant in the package as something it might draw.
_UNREAD_REMEDY = {
    unicodedata.lookup(name): remedy
    for name, remedy in (
        ("SQUARE ROOT", "write a root as a power: m**0.5"),
        ("CUBE ROOT", "write a root as a power: m**(1/3)"),
        ("FOURTH ROOT", "write a root as a power: m**0.25"),
        ("DIVISION SIGN", "write a division with '/'"),
        ("DIVISION SLASH", "write a division with '/'"),
        ("FRACTION SLASH", "write a division with '/'"),
        ("DEGREE CELSIUS", "write degC"),
        ("DEGREE FAHRENHEIT", "write degF"),
        ("PRIME", "write ft or arcminute"),
        ("DOUBLE PRIME", "write in or arcsecond"),
    )
}


def _unread_character(unit: str) -> str | None:
    """Why ``unit`` holds a character pint would silently drop, or ``None``."""
    for character in unit:
        if character.isalnum() or character.isspace() or character in _UNIT_PUNCTUATION:
            continue
        name = unicodedata.name(character, f"U+{ord(character):04X}")
        remedy = _UNREAD_REMEDY.get(character, "remove it or spell the unit out")
        return (
            f"unit {unit.strip()!r} contains {character!r} ({name}), which is not read as part "
            f"of a unit and would be dropped without a word — {remedy}"
        )
    return None


def _power_hint(text: str) -> str:
    """`; ... write 'mm**2'` when ``text`` reads once its trailing digits are powers, else "".

    `mm2`, `N/mm2` and `m/s2` are how area, stress and acceleration are typed, and pint
    knows none of them: "unknown unit" alone left the reader to find the `**`.
    """
    powered = re.sub(r"(?<=[A-Za-z])([2-4])\b", r"**\1", text)
    if powered == text:
        return ""
    try:
        UREG.Quantity(powered)
    except Exception:
        return ""
    return f": a trailing digit is not read as a power — write {powered!r}"


def _glued_product(unit: str) -> str | None:
    """Why ``unit`` writes a product of units in a form pint misreads, or ``None``."""
    if (unread := _unread_character(unit)) is not None:
        return unread
    unit = unit.strip()
    for token in re.findall(r"[A-Za-z]+", unit):
        if token in _GLUED_PRODUCTS:
            return (
                f"unit {unit!r} writes {token!r}, which is not read as a product of units — "
                f"write {_GLUED_PRODUCTS[token]!r}"
            )
    if _HYPHENATED.search(unit):
        product = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "*", unit)
        # `lb` is the pound mass; the pound in a hyphenated moment is the pound-force.
        product = re.sub(r"\blb\b", "lbf", product)
        return f"unit {unit!r} joins units with '-' — write the product as {product!r}"
    return None


@lru_cache(maxsize=1)
def _unit_names() -> tuple[str, ...]:
    """Every unit name the registry defines, for a near-miss suggestion."""
    return tuple(sorted(str(name) for name in getattr(UREG, "_units", {})))


def _nearest_unit(expression: str) -> str:
    """` (did you mean 'millimeter'?)` for the first word of ``expression`` that is no unit.

    A misspelled unit is an ordinary mistake, `milimeter` for `millimeter`, and "unknown
    unit" alone leaves the reader to find the spelling. The suggestion holds no semicolon,
    because MCP joins a refusal's issues with "; ".
    """
    for word in re.findall(r"[A-Za-z_]+", expression):
        try:
            _unit_object(word)
        except Exception:  # the same several pint errors as above
            near = difflib.get_close_matches(word, _unit_names(), n=1, cutoff=0.8)
            return f" (did you mean {near[0]!r}?)" if near else ""
    return ""


class Quantity(RevalidatedModel):
    """A physical value: a magnitude and the unit it was expressed in.

    Construct directly (``Quantity(magnitude=75, unit="kip")``) or parse from
    text (``Quantity.parse("75 kip")``). The stored ``unit`` string is exactly
    what the user wrote, canonicalized only to Pint's spelling of it.
    """

    model_config = ConfigDict(frozen=True)

    magnitude: float
    unit: str

    @model_validator(mode="after")
    def _validate_unit(self) -> Quantity:
        if (glued := _glued_product(self.unit)) is not None:
            raise UnitError(
                glued,
                action="rewrite",
                subject=f"the unit expression {self.unit!r}",
                source="the product of units it names, written with '*'",
            )
        try:
            _unit_object(self.unit)
        except Exception as exc:  # pint raises several undefined/parse errors
            raise UnitError(
                f"unknown unit {self.unit!r}{_power_hint(self.unit) or _nearest_unit(self.unit)}",
                action="replace",
                subject=f"the unit expression {self.unit!r}",
                source="a valid spelling in the bundled unit registry",
            ) from exc
        for token in re.findall(r"[A-Za-z]+", self.unit):
            if token in _CASE_TRAPS:
                raise UnitError(
                    f"unit {self.unit!r} contains {token!r}, which is {_CASE_TRAPS[token]}. "
                    f"No dimension check can catch that difference, so this spelling is "
                    f"refused rather than converted. If you meant it, write the magnitude "
                    f"in the base unit — {_CASE_TRAPS_REMEDY[token]}",
                    action="rewrite",
                    subject=f"the case-sensitive unit {token!r} in {self.unit!r}",
                    source=f"the base-unit equivalence {_CASE_TRAPS_REMEDY[token]}",
                )
        return self

    @classmethod
    def parse(cls, text: str) -> Quantity:
        """Parse ``"75 kip"``-style input.

        A bare number (no unit) raises :class:`MissingUnitError`: a load-bearing
        value must never have its unit silently assumed.

        Two families need more than pint's text constructor, and both are units this
        library itself writes down — so refusing them meant a rendered value could not be
        read back, and a spec could not state what a report had printed:

        * **Offset temperatures.** ``UREG.Quantity("400 degC")`` raises, because
          multiplying a magnitude by an offset unit is ambiguous; the two-argument form
          is not. The fallback is for offset units and nothing else, because a general
          escape hatch here would quietly re-admit everything the text parser declines —
          a range (``"45-50 kN"``), a tolerance, a unit that is not one.
        * **Angles.** ``rad``, ``degree`` and ``arcminute`` are dimensionless in pint,
          so the dimensionless guard rejected them along with ``"12 %"`` and ``"3
          dimensionless"``, which it is there for. An angle states its unit; a ratio does
          not, and that is the line.
        """
        # The minus sign a word processor or a PDF writes. pint dropped it, so "−10 mm" was
        # +10 mm.
        text = text.strip().replace("\u2212", "-")
        problem = _not_one_quantity(text)
        if problem is not None:
            raise UnitError(
                f"{text!r} {problem}",
                action="rewrite",
                subject=f"the physical quantity {text!r}",
                source="a single magnitude and unit from the originating document",
            )
        magnitude = _MAGNITUDE.match(text)
        glued = _glued_product(text[magnitude.end() :] if magnitude else text)
        if glued is not None:
            raise UnitError(
                f"{text!r}: {glued}",
                action="rewrite",
                subject=f"the physical quantity {text!r}",
                source="the product of units it names, written with '*'",
            )
        try:
            float(text)
        except ValueError:
            pass
        else:
            raise MissingUnitError(
                f"{text!r} has no unit; a physical quantity must state its unit",
                action="state",
                subject=f"the unit for physical quantity {text!r}",
                source="the originating design document or measurement record",
            )
        try:
            pq = UREG.Quantity(text)
        except Exception as exc:
            offset = _offset_temperature(text)
            if offset is None and (hint := _power_hint(text)):
                raise UnitError(
                    f"could not parse quantity {text!r}{hint}",
                    action="rewrite",
                    subject=f"the physical quantity {text!r}",
                    source="the same unit with its exponent written as '**'",
                ) from exc
            if offset is None:
                raise UnitError(
                    f"could not parse quantity {text!r}",
                    action="rewrite",
                    subject=f"the physical quantity {text!r}",
                    source="a magnitude and valid unit from the originating document",
                ) from exc
            pq = offset
        if pq.dimensionless and not _is_angle(pq):
            raise MissingUnitError(
                f"{text!r} has no unit; a physical quantity must state its unit",
                action="state",
                subject=f"the unit for physical quantity {text!r}",
                source="the originating design document or measurement record",
            )
        return cls(magnitude=pq.magnitude, unit=_stable_short_unit(f"{pq.units:~}"))

    @property
    def pint(self) -> pint.Quantity:
        """The canonical Pint quantity for computation and conversion."""
        return UREG.Quantity(self.magnitude, _unit_object(self.unit))

    @property
    def dimensionality(self) -> str:
        return _dimensionality_str(self.unit)

    def to(self, unit: str) -> Quantity:
        """Return this quantity converted to ``unit`` (preserving as a Quantity)."""
        # The target spelling is memoised for the same reason the source one is: `.to("MPa")`
        # inside a screen ran pint's unit parser on every call.
        converted = self.pint.to(_unit_object(unit))
        return Quantity(magnitude=converted.magnitude, unit=_short_spelling(unit))

    def has_dimension(self, expected: str) -> bool:
        """Whether this quantity's dimension matches ``expected`` (e.g. ``"[pressure]"``)."""
        return _dimensionality_of_unit(self.unit) == _dimensionality_of(expected)

    def __str__(self) -> str:
        return f"{self.magnitude:g} {display_unit(self.unit)}"

    # --- The operations this type deliberately does not support, saying which ----------
    #
    # A Quantity is a value object: arithmetic and ordering go through `.pint`, or through
    # `.to(unit).magnitude` where the caller has said which unit the comparison is in. None
    # of these operators existed, so every one of them raised
    #
    #     TypeError: '<' not supported between instances of 'Quantity' and 'int'
    #
    # which names neither the parameter nor the mistake. And the mistake is a common one in
    # exactly this library: a caller told that everything is a Quantity wraps a *ratio*, a
    # *count* or an *angle in degrees* — 213 public analysis functions took a plain number
    # for one of those and answered a wrapped one with that sentence. Defining the operators
    # to refuse is what lets the refusal say what happened; it can regress nothing, because
    # every one of these raised before.

    def _unsupported(self, operation: str, other: object) -> UnitError:
        if isinstance(other, Quantity):
            return UnitError(
                f"{operation} is not defined between two quantities ({self} and {other}); "
                f"convert both to one unit and compare the magnitudes, which is where the "
                f"unit you are comparing in gets written down",
                action="replace",
                subject=f"{self} and {other}",
                source="both quantities converted to one unit, compared by magnitude",
            )
        return UnitError(
            f"{operation} is not defined between a quantity ({self}) and {other!r}. A "
            f"parameter taking a plain number — a ratio, a count, an angle in degrees — was "
            f"given a Quantity; pass {self.magnitude:g} if that is the number you meant",
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )

    def __lt__(self, other: object) -> bool:
        raise self._unsupported("<", other)

    def __le__(self, other: object) -> bool:
        raise self._unsupported("<=", other)

    def __gt__(self, other: object) -> bool:
        raise self._unsupported(">", other)

    def __ge__(self, other: object) -> bool:
        raise self._unsupported(">=", other)

    # Arithmetic goes through `.pint`, which is where the unit algebra lives. Refusing here
    # by name beats "unsupported operand type(s) for -: 'Quantity' and 'Quantity'", and the
    # reflected forms are defined too — otherwise `2 * q` and `q * 2` answer differently.
    def __add__(self, other: object) -> Quantity:
        raise self._unsupported("+", other)

    __radd__ = __add__

    def __sub__(self, other: object) -> Quantity:
        raise self._unsupported("-", other)

    __rsub__ = __sub__

    def __mul__(self, other: object) -> Quantity:
        raise self._unsupported("*", other)

    __rmul__ = __mul__

    def __truediv__(self, other: object) -> Quantity:
        raise self._unsupported("/", other)

    __rtruediv__ = __truediv__

    def __abs__(self) -> Quantity:
        raise UnitError(
            f"abs() is not defined on a quantity ({self}); a parameter taking a plain "
            f"number was given one. Pass {abs(self.magnitude):g}, or "
            f"abs(q.to(unit).magnitude) where the unit matters",
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )

    def __int__(self) -> int:
        raise UnitError(
            f"int() is not defined on a quantity ({self}); a parameter taking a count was "
            f"given one. A count has no unit — pass {int(self.magnitude)}",
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )

    def __float__(self) -> float:
        raise UnitError(
            f"float() is not defined on a quantity ({self}); a parameter taking a plain "
            f"number was given one. Pass {self.magnitude:g}, or q.to(unit).magnitude where "
            f"the unit matters",
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )

    # The four operators above were the ones a caller reaches for first, and stopping
    # there left the rest of the numeric protocol answering Python's bare sentence again —
    # `bad operand type for unary -: 'Quantity'` names neither the parameter nor the
    # mistake, which is the whole reason the block above exists. `-stress` on a
    # compression, `d ** 2` in a section property, `round(load, 2)` before printing and
    # `f"{load:.2f}"` in a caller's own report are all ordinary things to write.
    #
    # `tests/test_units.py` holds the *completeness* of this block rather than its members:
    # every numeric dunder Python defines is either written here or named as one this type
    # deliberately leaves to the base class, so the next one cannot be missed the way these
    # were.

    def __neg__(self) -> Quantity:
        raise UnitError(
            f"unary - is not defined on a quantity ({self}); a parameter taking a plain "
            f"number was given one. Pass Quantity(magnitude={-self.magnitude:g}, "
            f"unit={self.unit!r}) for the negated quantity, or -q.to(unit).magnitude "
            f"where a plain number is what is wanted",
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )

    def __pos__(self) -> Quantity:
        raise UnitError(
            f"unary + is not defined on a quantity ({self}); it does nothing to a number "
            f"and the same is true here, so it is refused rather than answered — pass the "
            f"quantity itself",
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )

    def __pow__(self, other: object) -> Quantity:
        raise self._unsupported("**", other)

    __rpow__ = __pow__

    def __floordiv__(self, other: object) -> Quantity:
        raise self._unsupported("//", other)

    __rfloordiv__ = __floordiv__

    def __mod__(self, other: object) -> Quantity:
        raise self._unsupported("%", other)

    __rmod__ = __mod__

    def __divmod__(self, other: object) -> Quantity:
        raise self._unsupported("divmod()", other)

    __rdivmod__ = __divmod__

    def _no_rounding(self, operation: str) -> UnitError:
        return UnitError(
            f"{operation} is not defined on a quantity ({self}); rounding a magnitude "
            f"without saying which unit it is in is how a value gets rounded in metres and "
            f"read in millimetres. Write {operation}(q.to(unit).magnitude) and wrap the "
            f"result, or leave the rounding to the rendering",
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )

    def __round__(self, ndigits: int | None = None) -> Quantity:
        raise self._no_rounding("round()")

    def __floor__(self) -> Quantity:
        raise self._no_rounding("math.floor()")

    def __ceil__(self) -> Quantity:
        raise self._no_rounding("math.ceil()")

    def __trunc__(self) -> Quantity:
        raise self._no_rounding("math.trunc()")

    def __format__(self, format_spec: str) -> str:
        """``f"{q}"`` renders the quantity; ``f"{q:.2f}"`` says what to write instead.

        A format spec is a statement about a *number*, and this object is a number and a
        unit. Applying the spec to the magnitude and appending the unit would answer
        ``f"{q:>12}"`` by padding the number and pushing the unit past the column the
        caller was aligning to — a table that looks aligned and is not. So the spec is
        refused, in the same voice as the operators above, rather than half-honoured.
        """
        if format_spec == "":
            return str(self)
        raise UnitError(
            f"a format spec ({format_spec!r}) is not defined on a quantity ({self}); it "
            f"describes a number and this is a number with a unit. Write "
            f'f"{{q.to(unit).magnitude:{format_spec}}} unit" to control the figure, or '
            f'f"{{q}}" for this library\'s own rendering ({self})',
            action="replace",
            subject=str(self),
            source="the plain number (the magnitude in the documented unit) the parameter takes",
        )


def require_finite(value: Quantity | float, *, name: str) -> float:
    """The magnitude of ``value``, having refused a non-finite one by name.

    The guard shape ``if x <= 0: raise`` is a no-op against NaN, because every comparison
    with NaN is False. That is not a curiosity: a NaN slides past the positivity check,
    poisons one candidate in a governing scan, and ``max``/``min`` then *drop* the poisoned
    candidate rather than propagating it — so the envelope comes back complete, smaller,
    and green. A five-agent audit found thirteen instances of exactly that in this library,
    two of which returned a peak force of ``0 N``, which downstream is an infinite safety
    factor.

    So a function whose result feeds a governing selection calls this instead of comparing.
    It returns the magnitude so the caller can go on to bound it however it needs to; the
    refusal here is only about the value being a number at all.
    """
    magnitude = value.magnitude if isinstance(value, Quantity) else float(value)
    if not isfinite(magnitude):
        raise UnitError(
            f"{name} must be a finite quantity; got {value}. A non-finite value passes "
            f"every `<= 0` guard (all comparisons with NaN are False) and is then silently "
            f"dropped by the max()/min() that picks the governing case, which turns an "
            f"unknown into a smaller, greener answer",
            action="replace",
            subject=name,
            source="a finite measured or specified value for the input",
        )
    return magnitude


def require_dimension(expected: str, *, name: str) -> Any:
    """Build a Pydantic ``AfterValidator`` that enforces a quantity's dimension.

    On mismatch it raises a :class:`DimensionError` naming the received and
    expected dimensions; Pydantic supplies the offending field path.
    """

    def _check(value: Quantity) -> Quantity:
        if not value.has_dimension(expected):
            raise DimensionError(
                f"{name} expects a {expected} quantity "
                f"but received {value.dimensionality} ({value})",
                action="replace",
                subject=f"the {name} value {value}",
                source=f"a quantity matching the field's declared {expected} dimension",
            )
        return value

    return _check
