"""Anvilate units layer: SI and US customary as first-class citizens.

Physical values enter the system as :class:`Quantity` objects that keep the
unit as entered, expose the canonical Pint quantity for computation, and are
dimensionally checked wherever a field pins an expected dimension.
"""

from __future__ import annotations

from .format import decimals_for, render
from .quantity import (
    DimensionError,
    MissingUnitError,
    Quantity,
    UnitError,
    require_dimension,
)
from .registry import UREG
from .system import UnitSystem

__all__ = [
    "Quantity",
    "UnitError",
    "MissingUnitError",
    "DimensionError",
    "require_dimension",
    "UnitSystem",
    "UREG",
    "render",
    "decimals_for",
]
