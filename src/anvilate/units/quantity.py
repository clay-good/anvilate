"""The :class:`Quantity` type: a magnitude plus an explicit unit.

Quantities are the only way a physical value enters the Spec IR. They carry the
unit *as entered* so the spec card can echo it and line-based diffs stay
meaningful, while exposing the canonical Pint quantity on demand for
computation and conversion. Dimensional consistency is checked on construction
and again wherever a field pins an expected dimension.
"""

from __future__ import annotations

import re
from math import isfinite
from typing import Any

import pint
from pydantic import ConfigDict, model_validator

from .._models import RevalidatedModel
from .registry import UREG

__all__ = [
    "Quantity",
    "UnitError",
    "MissingUnitError",
    "DimensionError",
    "require_dimension",
]


class UnitError(ValueError):
    """Base class for unit and dimension problems."""


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


def _dimensionality_str(units: str) -> str:
    """Human-readable dimensionality, e.g. ``[pressure]`` or the base form."""
    return _friendly_dimension(UREG.Unit(units).dimensionality)


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
        try:
            UREG.Unit(self.unit)
        except Exception as exc:  # pint raises several undefined/parse errors
            raise UnitError(f"unknown unit {self.unit!r}") from exc
        for token in re.findall(r"[A-Za-z]+", self.unit):
            if token in _CASE_TRAPS:
                raise UnitError(
                    f"unit {self.unit!r} contains {token!r}, which is {_CASE_TRAPS[token]}. "
                    f"No dimension check can catch that difference, so this spelling is "
                    f"refused rather than converted. If you meant it, write the magnitude "
                    f"in the base unit — {_CASE_TRAPS_REMEDY[token]}"
                )
        return self

    @classmethod
    def parse(cls, text: str) -> Quantity:
        """Parse ``"75 kip"``-style input.

        A bare number (no unit) raises :class:`MissingUnitError`: a load-bearing
        value must never have its unit silently assumed.
        """
        text = text.strip()
        try:
            float(text)
        except ValueError:
            pass
        else:
            raise MissingUnitError(f"{text!r} has no unit; a physical quantity must state its unit")
        try:
            pq = UREG.Quantity(text)
        except Exception as exc:
            raise UnitError(f"could not parse quantity {text!r}") from exc
        if pq.dimensionless:
            raise MissingUnitError(f"{text!r} has no unit; a physical quantity must state its unit")
        return cls(magnitude=pq.magnitude, unit=f"{pq.units:~}")

    @property
    def pint(self) -> pint.Quantity:
        """The canonical Pint quantity for computation and conversion."""
        return UREG.Quantity(self.magnitude, self.unit)

    @property
    def dimensionality(self) -> str:
        return _dimensionality_str(self.unit)

    def to(self, unit: str) -> Quantity:
        """Return this quantity converted to ``unit`` (preserving as a Quantity)."""
        converted = self.pint.to(unit)
        return Quantity(magnitude=converted.magnitude, unit=f"{converted.units:~}")

    def has_dimension(self, expected: str) -> bool:
        """Whether this quantity's dimension matches ``expected`` (e.g. ``"[pressure]"``)."""
        return self.pint.dimensionality == UREG.get_dimensionality(expected)

    def __str__(self) -> str:
        return f"{self.magnitude:g} {self.unit}"

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

    def _unsupported(self, operation: str, other: object) -> ValueError:
        if isinstance(other, Quantity):
            return ValueError(
                f"{operation} is not defined between two quantities ({self} and {other}); "
                f"convert both to one unit and compare the magnitudes, which is where the "
                f"unit you are comparing in gets written down"
            )
        return ValueError(
            f"{operation} is not defined between a quantity ({self}) and {other!r}. A "
            f"parameter taking a plain number — a ratio, a count, an angle in degrees — was "
            f"given a Quantity; pass {self.magnitude:g} if that is the number you meant"
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
        raise ValueError(
            f"abs() is not defined on a quantity ({self}); a parameter taking a plain "
            f"number was given one. Pass {abs(self.magnitude):g}, or "
            f"abs(q.to(unit).magnitude) where the unit matters"
        )

    def __int__(self) -> int:
        raise ValueError(
            f"int() is not defined on a quantity ({self}); a parameter taking a count was "
            f"given one. A count has no unit — pass {int(self.magnitude)}"
        )

    def __float__(self) -> float:
        raise ValueError(
            f"float() is not defined on a quantity ({self}); a parameter taking a plain "
            f"number was given one. Pass {self.magnitude:g}, or q.to(unit).magnitude where "
            f"the unit matters"
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
        raise ValueError(
            f"{name} must be a finite quantity; got {value}. A non-finite value passes "
            f"every `<= 0` guard (all comparisons with NaN are False) and is then silently "
            f"dropped by the max()/min() that picks the governing case, which turns an "
            f"unknown into a smaller, greener answer"
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
                f"but received {value.dimensionality} ({value})"
            )
        return value

    return _check
