"""T1 analytical helical compression-spring check (closed-form).

A round-wire helical spring under an axial force ``F`` carries a torsional shear
stress in the wire, ``τ = K_w · 8·F·D/(π·d³)``, where ``D`` is the mean coil
diameter, ``d`` the wire diameter, and ``K_w`` the Wahl factor correcting for
curvature and the direct shear (Shigley). The spring index ``C = D/d`` sets the
correction. As with the other checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "spring_index",
    "wahl_factor",
    "spring_shear_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def spring_index(*, mean_coil_diameter: Quantity, wire_diameter: Quantity) -> float:
    """The spring index C = D/d (mean coil diameter over wire diameter).

    Practical springs run C ≈ 4–12; the wire diameter must be below the mean coil
    diameter, else :class:`ValueError`.
    """
    _require(mean_coil_diameter, "[length]", "mean_coil_diameter")
    _require(wire_diameter, "[length]", "wire_diameter")
    big = mean_coil_diameter.to("mm").magnitude
    small = wire_diameter.to("mm").magnitude
    if not 0 < small < big:
        raise ValueError(
            f"wire_diameter ({wire_diameter}) must be positive and below the mean coil "
            f"diameter ({mean_coil_diameter})"
        )
    return big / small


def wahl_factor(spring_index: float) -> float:
    """The Wahl stress-correction factor K_w = (4C−1)/(4C−4) + 0.615/C for a
    spring of index ``spring_index`` (C), correcting the nominal shear stress for
    curvature and direct shear. ``spring_index`` must exceed 1."""
    c = spring_index
    if c <= 1:
        raise ValueError(f"spring_index must exceed 1; got {c}")
    return (4 * c - 1) / (4 * c - 4) + 0.615 / c


def spring_shear_stress(
    *,
    force: Quantity,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
) -> Quantity:
    """The Wahl-corrected torsional shear stress τ = K_w·8·F·D/(π·d³) in the wire
    of a round-wire helical compression spring.

    ``force`` is the axial spring force, ``mean_coil_diameter`` D, ``wire_diameter``
    d. Returns the peak shear stress in MPa; every quantity is dimension-checked.
    """
    _require(force, "[force]", "force")
    c = spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    kw = wahl_factor(c)
    stress = kw * 8 * force.pint * mean_coil_diameter.pint / (pi * wire_diameter.pint**3)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")
