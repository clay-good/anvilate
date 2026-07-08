"""The :class:`Quantity` type: a magnitude plus an explicit unit.

Quantities are the only way a physical value enters the Spec IR. They carry the
unit *as entered* so the spec card can echo it and line-based diffs stay
meaningful, while exposing the canonical Pint quantity on demand for
computation and conversion. Dimensional consistency is checked on construction
and again wherever a field pins an expected dimension.
"""

from __future__ import annotations

from typing import Any

import pint
from pydantic import BaseModel, ConfigDict, model_validator

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


class Quantity(BaseModel):
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
