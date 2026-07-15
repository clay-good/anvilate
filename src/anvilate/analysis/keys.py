"""T1 analytical checks for a shaft key (parallel/square key, closed-form).

A key transmits torque between a shaft and a hub through the tangential force it
carries at the shaft surface, ``F = 2·T/d`` for torque ``T`` and shaft diameter
``d``. That force shears the key across its width and bears on its side:

    shear:   τ = F/(w·L)          over the width w and length L
    bearing: σ_b = F/((h/2)·L)    over the half-height h/2 in the hub

Both are the Shigley closed forms for a parallel key. Sizing runs the other way —
:func:`key_length_for_torque` inverts both to the key length each limit state
needs and reports which governs. Inputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
    "KeyLengthRequirement",
    "key_length_for_torque",
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


class KeyLengthRequirement(BaseModel):
    """The key length each limit state needs, and which one governs.

    ``shear_length`` is the length that brings the key shear to its allowable and
    ``bearing_length`` the length that brings the side bearing to its allowable.
    ``required_length`` is the larger of the two — the length that satisfies both —
    and ``governing_mode`` is ``"shear"`` or ``"bearing"`` accordingly.
    """

    model_config = ConfigDict(frozen=True)

    shear_length: Quantity
    bearing_length: Quantity
    required_length: Quantity
    governing_mode: str


def key_length_for_torque(
    *,
    torque: Quantity,
    shaft_diameter: Quantity,
    key_width: Quantity,
    key_height: Quantity,
    allowable_shear: Quantity,
    allowable_bearing: Quantity,
) -> KeyLengthRequirement:
    """The minimum key length to carry ``torque`` within both limit states.

    Inverts the two stress checks: the tangential force F = 2·T/d needs
    L_shear = F/(w·τ_allow) to keep the key shear within ``allowable_shear`` and
    L_bearing = F/((h/2)·σ_allow) to keep the side bearing within
    ``allowable_bearing``; the key must be at least the larger of the two.
    ``key_width`` is w, ``key_height`` h. Returns a :class:`KeyLengthRequirement`
    reporting both lengths, the governing one, and its mode. Every quantity is
    dimension-checked and the allowables must be positive.
    """
    _require(key_width, "[length]", "key_width")
    _require(key_height, "[length]", "key_height")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    _require(allowable_bearing, "[pressure]", "allowable_bearing")
    if allowable_shear.to("MPa").magnitude <= 0 or allowable_bearing.to("MPa").magnitude <= 0:
        raise ValueError("allowable_shear and allowable_bearing must be positive")
    force = key_tangential_force(torque=torque, shaft_diameter=shaft_diameter).pint
    l_shear = (force / (key_width.pint * allowable_shear.pint)).to("mm").magnitude
    l_bearing = (force / ((key_height.pint / 2) * allowable_bearing.pint)).to("mm").magnitude
    governing = "shear" if l_shear >= l_bearing else "bearing"
    return KeyLengthRequirement(
        shear_length=Quantity(magnitude=l_shear, unit="mm"),
        bearing_length=Quantity(magnitude=l_bearing, unit="mm"),
        required_length=Quantity(magnitude=max(l_shear, l_bearing), unit="mm"),
        governing_mode=governing,
    )
