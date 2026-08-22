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

from ..units import Quantity, require_finite

__all__ = [
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
    "KeyLengthRequirement",
    "key_length_for_torque",
    "spline_torque_capacity",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


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
    ``key_width`` is w, ``key_height`` h. The torque enters by magnitude — a reversing
    drive needs the same key either way — so the answer is the same for ±T. Returns a
    :class:`KeyLengthRequirement` reporting both lengths, the governing one, and its
    mode. Every quantity is dimension-checked and the allowables must be positive.
    """
    _require(key_width, "[length]", "key_width")
    _require(key_height, "[length]", "key_height")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    _require(allowable_bearing, "[pressure]", "allowable_bearing")
    if allowable_shear.to("MPa").magnitude <= 0 or allowable_bearing.to("MPa").magnitude <= 0:
        raise ValueError("allowable_shear and allowable_bearing must be positive")
    # abs(): the key must carry the torque whichever way the shaft drives, and the length it
    # needs depends on the magnitude. Without it a reversing drive's negative torque flipped
    # the max() below into picking the LESS negative length — the shorter key — and named the
    # wrong limit state with it.
    force = abs(key_tangential_force(torque=torque, shaft_diameter=shaft_diameter).pint)
    l_shear = (force / (key_width.pint * allowable_shear.pint)).to("mm").magnitude
    l_bearing = (force / ((key_height.pint / 2) * allowable_bearing.pint)).to("mm").magnitude
    governing = "shear" if l_shear >= l_bearing else "bearing"
    return KeyLengthRequirement(
        shear_length=Quantity(magnitude=l_shear, unit="mm"),
        bearing_length=Quantity(magnitude=l_bearing, unit="mm"),
        required_length=Quantity(magnitude=max(l_shear, l_bearing), unit="mm"),
        governing_mode=governing,
    )


def spline_torque_capacity(
    *,
    allowable_pressure: Quantity,
    mean_radius: Quantity,
    tooth_height: Quantity,
    spline_length: Quantity,
    number_of_teeth: int,
    load_fraction: float = 0.25,
) -> Quantity:
    """The torque a straight-sided spline transmits at an allowable bearing pressure.

    A spline is a shaft with many integral keys, so it carries torque by bearing on the
    sides of its teeth: the tooth-flank contact area is N·h·L (``number_of_teeth`` N times
    the engaged ``tooth_height`` h times the ``spline_length`` L), and pressing on it at the
    ``allowable_pressure`` p over the ``mean_radius`` r gives a torque T = f·p·N·h·L·r. The
    ``load_fraction`` f (default 0.25, the standard conservative value for straight splines —
    manufacturing tolerances mean only about a quarter of the teeth share the load at once)
    folds in the uneven load sharing; supply the value your spline standard specifies. The
    mechanics is exact; the fraction and the engaged geometry are the caller's design values.
    All positive, N a positive whole number. Returns the torque in N·m.
    """
    _require(allowable_pressure, "[pressure]", "allowable_pressure")
    _require(mean_radius, "[length]", "mean_radius")
    _require(tooth_height, "[length]", "tooth_height")
    _require(spline_length, "[length]", "spline_length")
    if int(number_of_teeth) != number_of_teeth or number_of_teeth <= 0:
        raise ValueError(f"number_of_teeth must be a positive whole number; got {number_of_teeth}")
    if not 0 < load_fraction <= 1:
        raise ValueError(f"load_fraction must be in (0, 1]; got {load_fraction}")
    p = allowable_pressure.to("MPa").magnitude
    r = mean_radius.to("mm").magnitude
    h = tooth_height.to("mm").magnitude
    length = spline_length.to("mm").magnitude
    if p <= 0 or r <= 0 or h <= 0 or length <= 0:
        raise ValueError("pressure, mean_radius, tooth_height, and spline_length must be positive")
    torque_n_mm = load_fraction * p * number_of_teeth * h * length * r
    return Quantity(magnitude=torque_n_mm / 1000.0, unit="N*m")
