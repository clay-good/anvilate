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

__all__ = ["render", "render_dual", "decimals_for"]

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
    pretty: bool = False,
) -> str:
    """Render ``quantity`` at conventional precision.

    ``unit`` forces a target unit. Otherwise, if ``system`` is given the value
    is converted to that system's conventional unit for its dimension; if
    neither is given the quantity's own unit is used.

    ``pretty`` writes compound units the way a document does — ``"N·m"`` and
    ``"mm⁴"`` rather than the machine-readable ``"m * N"`` and ``"mm ** 4"`` a
    spec card echoes. The magnitude and its precision are identical either way.
    """
    target = unit
    if target is None and system is not None:
        target = _system_unit(quantity, system)
    shown = quantity if target is None else quantity.to(target)
    places = decimals_for(shown.unit)
    label = _engineering_order(f"{shown.pint.units:~P}") if pretty else shown.unit
    return f"{shown.magnitude:.{places}f} {label}"


def render_dual(quantity: Quantity, *, primary: UnitSystem) -> str:
    """Render ``quantity`` in the ``primary`` system with the other bracketed.

    Dual dimensioning shows the primary-system value and, in brackets, the same
    value in the opposite system — the drafting convention for a drawing that
    serves readers of both. Each side uses its system's conventional unit and
    precision, e.g. ``"25.40 mm [1.000 in]"`` for an SI-primary length.
    """
    secondary = UnitSystem.US if primary is UnitSystem.SI else UnitSystem.SI
    return f"{render(quantity, system=primary)} [{render(quantity, system=secondary)}]"


# Pint prints the factors of a compound unit alphabetically, so a moment comes out
# "m·N" and "in·kip" where every engineering document writes "N·m" and "kip·in". The
# values are right and only the label reads oddly, but a submittal is read by people
# who will trust a familiar label and squint at an unfamiliar one. Force leads, then
# length, then everything else in the order Pint gave — this reorders factors, it never
# changes, drops, or invents one.
_FACTOR_RANK = {
    "N": 0,
    "kN": 0,
    "MN": 0,
    "lbf": 0,
    "kip": 0,
    "kgf": 0,
    "mm": 1,
    "cm": 1,
    "m": 1,
    "km": 1,
    "in": 1,
    "ft": 1,
    "yd": 1,
}
_MULTIPLY = "·"


def _engineering_order(label: str) -> str:
    """Reorder a compound unit label force-first, then length, then as given.

    Only the numerator of a simple product is reordered. A label carrying a division or
    an exponent on a reordered factor is left exactly as Pint wrote it — a wrong label is
    worse than an unfamiliar one, and there is no engineering convention to appeal to for
    those anyway.
    """
    if _MULTIPLY not in label or "/" in label:
        return label
    factors = label.split(_MULTIPLY)
    if any(factor not in _FACTOR_RANK for factor in factors):
        return label
    if len({_FACTOR_RANK[f] for f in factors}) == 1:
        return label
    return _MULTIPLY.join(sorted(factors, key=lambda f: _FACTOR_RANK[f]))


def _system_unit(quantity: Quantity, system: UnitSystem) -> str | None:
    """The conventional unit for ``quantity``'s dimension in ``system``."""
    dim = quantity.pint.dimensionality
    mapping = [
        ("[length]", system.length_unit),
        ("[force]", system.force_unit),
        ("[pressure]", system.stress_unit),
        ("[mass]", system.mass_unit),
        # A moment and a second moment of area were unmapped, so a US-system derivation
        # converted its lengths to inches and left M in N·m and I in mm⁴ beside them —
        # a substituted line mixing two systems, which is worse than either.
        ("[force] * [length]", system.moment_unit),
        ("[length] ** 4", system.second_moment_unit),
    ]
    for token, unit in mapping:
        if dim == UREG.get_dimensionality(token):
            return unit
    return None
