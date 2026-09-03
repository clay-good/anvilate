"""Code-conventional rendering of quantities for reports and drawings.

Reports show values at the precision engineers expect for the unit (kips and
stresses to one decimal, millimeters to two, inches to three). Rendering is a
pure function of the quantity and target unit, so the same value renders
character-identically on every rebuild — no conversion jitter across
regenerations.
"""

from __future__ import annotations

from math import isfinite

from .quantity import Quantity, _unit_object, display_unit
from .registry import UREG
from .system import UnitSystem

__all__ = ["render", "render_dual", "decimals_for", "decimals_distinguishing"]

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


# The most a fixed-decimal rendering may round a value by, as a fraction of the value.
# The conventional decimal places above are fixed per unit and per dimension, which is
# fine at everyday magnitudes and wrong at small ones: a stress of 0.087 ksi printed to
# the pressure convention of one decimal reads "0.1 ksi", a 15% error — and that number
# then appears in a calculation report's substituted line, which a reviewer is told to
# check by hand. Below this bound the places are increased until the rounding is
# negligible, so a printed line reproduces its own printed result.
_MAX_RELATIVE_ROUNDING = 0.005

# Units that share a moment's dimensionality but are energies; see _system_unit.
#: Energy and moment share one dimensionality, and pint has 49 units in it. Named here so
#: the two can be told apart *structurally* rather than by a list of spellings.
_ENERGY_DIMENSIONALITY = UREG.Unit("joule").dimensionality


def _is_written_as_energy(quantity: Quantity) -> bool:
    """Whether ``quantity`` is written in an energy unit rather than a force times a length.

    Energy, work and torque are one dimensionality and only one of them is a moment, so
    relabelling a strain energy or a heat duty as "9.34 kip·in" is arithmetically right and
    unreadable. Telling them apart used to be a set of fourteen spellings plus eight
    substrings, and both are lists: pint has **49** units in this dimensionality, and the one
    a US mechanical engineer actually writes — ``ft_lb`` — was on neither.

    There is no dimension to test, because that is the whole problem. There is a *structure*:
    every energy unit pint defines is a single named unit (``joule``, ``foot_pound``,
    ``kilowatt_hour``, ``british_thermal_unit``, ``hartree``), and every moment is a force
    times a length (``newton * meter``, ``kip * inch``, ``force_pound * foot``). One
    component means energy; two mean a moment.
    """
    components = dict(_unit_object(quantity.unit)._units)
    return len(components) == 1 and next(iter(components.values())) == 1


def decimals_for(unit: str, magnitude: float | None = None) -> int:
    """Conventional decimal places for a unit, widened when they would lose the value.

    ``magnitude`` is optional and, when given, raises the precision for a value small
    enough that the conventional places would round it by more than half a percent.
    """
    if unit in _UNIT_DECIMALS:
        places = _UNIT_DECIMALS[unit]
    else:
        # Through the memoised choke point, not `UREG.Unit` directly: that is where an
        # unreadable spelling becomes this library's `UnitError` instead of pint's
        # `UndefinedUnitError` (an AttributeError), and it is also the cache every other
        # unit lookup already shares.
        dim = str(_unit_object(unit).dimensionality)
        places = _DIM_DECIMALS.get(dim, 2)
    if magnitude is None:
        return places
    value = abs(magnitude)
    if value == 0 or not isfinite(value):
        return places
    # Half a unit in the last printed place is the worst-case rounding.
    while 0.5 * 10.0**-places > _MAX_RELATIVE_ROUNDING * value and places < 12:
        places += 1
    return places


def decimals_distinguishing(value: float, reference: float, *, minimum: int = 2) -> int:
    """Decimal places at which ``value`` does not print identically to ``reference``.

    For a sentence that argues from a comparison — "exceeds the band by", "transmissibility
    above 1" — the figure it prints has to still be on the right side of the boundary after
    rounding. It was not, in the two places this was written for:

    * ``safety factor 2.50 exceeds target band 1.50–2.50 by 0.00 — over-engineered``
    * ``mount amplifies: transmissibility 1.00 > 1``

    Both are contradicted by the numbers inside them. This is the same widening rule
    :func:`decimals_for` applies to a magnitude small enough that conventional precision
    would round it away, pointed at a *difference* rather than at a value.

    Capped at twelve places, and ``minimum`` is the conventional precision to start from. A
    value genuinely equal to the reference gets ``minimum`` back rather than twelve, because
    no number of places separates them and the caller has a different sentence to write.
    """
    if value == reference or not isfinite(value) or not isfinite(reference):
        return minimum
    places = minimum
    while places < 12 and f"{value:.{places}f}" == f"{reference:.{places}f}":
        places += 1
    return places


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
    places = decimals_for(shown.unit, shown.magnitude)
    label = _engineering_order(f"{shown.pint.units:~P}") if pretty else shown.unit
    label = display_unit(label)
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
    # A quantity already written in an energy unit keeps it — see `_is_written_as_energy`
    # for why that cannot be decided by the unit's spelling.
    if dim == _ENERGY_DIMENSIONALITY and _is_written_as_energy(quantity):
        return None
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
        # Areas were the remaining hole: a US-system line printed "1.5 · 6.0 kN /
        # 5000.00 mm²" against a result in ksi — SI force over SI area, US stress.
        ("[length] ** 2", system.area_unit),
        # And two more, found the same way: an SI report printing
        # "σ = M / Z = 169477.24 N·mm / 3.00 in³" and "M = wL²/8 = 100.00 lbf/ft ·
        # (3048.00 mm)² / 8". Every other factor had been converted and these had not.
        ("[length] ** 3", system.section_modulus_unit),
        ("[force] / [length]", system.distributed_load_unit),
    ]
    for token, unit in mapping:
        if dim == UREG.get_dimensionality(token):
            return unit
    return None
