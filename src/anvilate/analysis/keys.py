"""T1 analytical checks for a shaft key (parallel/square key, closed-form).

A key transmits torque between a shaft and a hub through the tangential force it
carries at the shaft surface, ``F = 2·T/d`` for torque ``T`` and shaft diameter
``d``. That force shears the key across its width and bears on its side:

    shear:   τ = F/(w·L)          over the width w and length L
    bearing: σ_b = F/((h/2)·L)    over the half-height h/2 in the hub

Both are the Shigley closed forms for a parallel key. Inputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def key_tangential_force(*, torque: Quantity, shaft_diameter: Quantity) -> Quantity:
    """The tangential force F = 2·T/d a key carries at the shaft surface.

    ``torque`` is the transmitted torque, ``shaft_diameter`` the shaft diameter.
    Returns the force in newtons.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(shaft_diameter, "[length]", "shaft_diameter")
    force = 2 * torque.pint / shaft_diameter.pint
    converted = force.to("N")
    return Quantity(magnitude=float(converted.magnitude), unit="N")


def key_shear_stress(
    *,
    torque: Quantity,
    shaft_diameter: Quantity,
    key_width: Quantity,
    key_length: Quantity,
) -> Quantity:
    """The shear stress τ = F/(w·L) across a key transmitting ``torque``.

    ``key_width`` is w and ``key_length`` L; the tangential force F = 2·T/d shears
    the key over the width×length plane. Returns the shear stress in MPa.
    """
    _require(key_width, "[length]", "key_width")
    _require(key_length, "[length]", "key_length")
    force = key_tangential_force(torque=torque, shaft_diameter=shaft_diameter)
    stress = force.pint / (key_width.pint * key_length.pint)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def key_bearing_stress(
    *,
    torque: Quantity,
    shaft_diameter: Quantity,
    key_height: Quantity,
    key_length: Quantity,
) -> Quantity:
    """The bearing stress σ_b = F/((h/2)·L) on the side of a key.

    ``key_height`` is h (half of it bears in the hub) and ``key_length`` L; the
    tangential force F = 2·T/d presses on the h/2×L face. Returns the bearing
    stress in MPa.
    """
    _require(key_height, "[length]", "key_height")
    _require(key_length, "[length]", "key_length")
    force = key_tangential_force(torque=torque, shaft_diameter=shaft_diameter)
    stress = force.pint / ((key_height.pint / 2) * key_length.pint)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")
