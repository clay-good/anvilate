"""T1 analytical direct-stress check (axial tension / compression).

The simplest stress state: a member carrying an axial ``force`` over a
cross-sectional ``area`` develops a uniform direct stress ``σ = F/A``. It is the
normal-stress input to the von Mises combination for a tension rod or a bolt
shank, and its own screening check against yield. Area helpers for the common
solid sections are provided. As elsewhere, inputs and outputs are dimension-
checked :class:`~anvilate.units.Quantity` values through Pint.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "circular_area",
    "axial_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


def circular_area(diameter: Quantity) -> Quantity:
    """The area A = π·d²/4 of a solid circular section."""
    _require(diameter, "[length]", "diameter")
    return _as_quantity(pi * diameter.pint**2 / 4, "mm**2")


def axial_stress(*, force: Quantity, area: Quantity) -> Quantity:
    """The direct axial stress σ = F/A over a cross-sectional ``area``.

    A positive result is tension and a negative result compression, following the
    sign of ``force``. ``force`` must be a force and ``area`` an area (length²).
    Returns the stress in MPa.
    """
    _require(force, "[force]", "force")
    _require(area, "[length]**2", "area")
    stress = force.pint / area.pint
    return _as_quantity(stress, "MPa")
