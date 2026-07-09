"""T1 analytical torsion checks for solid circular shafts (closed-form).

A shaft transmitting torque ``T`` carries a maximum torsional shear stress at its
surface, ``τ_max = T·r/J`` with the polar second moment ``J = π·d⁴/32`` and
``r = d/2`` (so ``τ_max = 16·T/(π·d³)``), and twists through an angle
``θ = T·L/(G·J)``. These are the Roark / Shigley closed forms for a prismatic,
linear-elastic solid round shaft. As with the beam and column checks, inputs and
outputs are dimension-checked :class:`~anvilate.units.Quantity` values and the
arithmetic runs through Pint.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "polar_second_moment_solid",
    "shaft_torsional_stress",
    "shaft_twist_angle",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


def polar_second_moment_solid(diameter: Quantity) -> Quantity:
    """The polar second moment J = π·d⁴/32 of a solid circular section."""
    _require(diameter, "[length]", "diameter")
    return _as_quantity(pi * diameter.pint**4 / 32, "mm**4")


def shaft_torsional_stress(*, torque: Quantity, diameter: Quantity) -> Quantity:
    """The maximum torsional shear stress τ_max = T·r/J = 16·T/(π·d³) at the
    surface of a solid round shaft of ``diameter`` carrying ``torque``.

    ``torque`` must be a torque (force·length) and ``diameter`` a length. Returns
    the peak shear stress as a pressure.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(diameter, "[length]", "diameter")
    d = diameter.pint
    j = pi * d**4 / 32
    r = d / 2
    stress = torque.pint * r / j
    return _as_quantity(stress, "MPa")


def shaft_twist_angle(
    *,
    torque: Quantity,
    length: Quantity,
    diameter: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The angle of twist θ = T·L/(G·J) of a solid round shaft.

    ``torque`` is the applied torque, ``length`` the shaft length, ``diameter``
    the shaft diameter, and ``shear_modulus`` the material's shear (rigidity)
    modulus G (= E/(2(1+ν)) for an isotropic material). Returns the twist in
    degrees. Every quantity argument is dimension-checked.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(length, "[length]", "length")
    _require(diameter, "[length]", "diameter")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    j = pi * diameter.pint**4 / 32
    angle = torque.pint * length.pint / (shear_modulus.pint * j)
    return _as_quantity(angle, "degree")
