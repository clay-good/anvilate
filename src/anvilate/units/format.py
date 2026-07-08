"""Code-conventional rendering of quantities for reports and drawings.

Reports show values at the precision engineers expect for the unit (kips and
stresses to one decimal, millimeters to two, inches to three). Rendering is a
pure function of the quantity and target unit, so the same value renders
character-identically on every rebuild — no conversion jitter across
regenerations.
"""

from __future__ import annotations

from .quantity import Quantity
from .registry import UREG
from .system import UnitSystem

__all__ = ["render", "decimals_for"]

# Decimals by dimensionality string. Falls through to a per-unit override below
# and then to a default.
_DIM_DECIMALS = {
    str(UREG.get_dimensionality("[pressure]")): 1,  # stress
    str(UREG.get_dimensionality("[force]")): 1,
    str(UREG.get_dimensionality("[mass]")): 1,
}
_UNIT_DECIMALS = {
    "mm": 2,
    "in": 3,
    "m": 3,
    "ft": 3,
}


def decimals_for(unit: str) -> int:
    """Conventional decimal places for a unit."""
    if unit in _UNIT_DECIMALS:
        return _UNIT_DECIMALS[unit]
    dim = str(UREG.Unit(unit).dimensionality)
    return _DIM_DECIMALS.get(dim, 2)


def render(
    quantity: Quantity,
    *,
    unit: str | None = None,
    system: UnitSystem | None = None,
) -> str:
    """Render ``quantity`` at conventional precision.

    ``unit`` forces a target unit. Otherwise, if ``system`` is given the value
    is converted to that system's conventional unit for its dimension; if
    neither is given the quantity's own unit is used.
    """
    target = unit
    if target is None and system is not None:
        target = _system_unit(quantity, system)
    shown = quantity if target is None else quantity.to(target)
    places = decimals_for(shown.unit)
    return f"{shown.magnitude:.{places}f} {shown.unit}"


def _system_unit(quantity: Quantity, system: UnitSystem) -> str | None:
    """The conventional unit for ``quantity``'s dimension in ``system``."""
    dim = quantity.pint.dimensionality
    mapping = [
        ("[length]", system.length_unit),
        ("[force]", system.force_unit),
        ("[pressure]", system.stress_unit),
        ("[mass]", system.mass_unit),
    ]
    for token, unit in mapping:
        if dim == UREG.get_dimensionality(token):
            return unit
    return None
