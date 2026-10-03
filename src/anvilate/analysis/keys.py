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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SHAFT_DRAWING_SOURCE = "the shaft and hub drawing (shaft diameter, key or spline dimensions)"
_DUTY_SOURCE = "the shaft's design torque from the load case"
_ALLOWABLE_SOURCE = "the key or spline material's allowable stresses from the design basis"
_SPLINE_STANDARD_SOURCE = "the spline standard (tooth count and load-sharing fraction)"


class _KeysInputError(RefusalError, ValueError):
    """A shaft-key or spline input that cannot be used without correction."""


def _keys_refusal(message: str, *, subject: str, source: str) -> _KeysInputError:
    return _KeysInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _keys_input_source(name: str) -> str:
    if name == "torque":
        return _DUTY_SOURCE
    if name in {"allowable_bearing", "allowable_pressure", "allowable_shear"}:
        return _ALLOWABLE_SOURCE
    if name in {"load_fraction", "number_of_teeth"}:
        return _SPLINE_STANDARD_SOURCE
    return _SHAFT_DRAWING_SOURCE


__all__ = [
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
    "KeyLengthRequirement",
    "key_length_for_torque",
    "spline_torque_capacity",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _keys_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_keys_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _keys_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_keys_input_source(name),
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
    if shaft_diameter.magnitude <= 0:
        raise _keys_refusal(
            f"shaft_diameter must be positive; got {shaft_diameter}",
            subject="shaft_diameter",
            source=_SHAFT_DRAWING_SOURCE,
        )
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
    if key_width.magnitude <= 0:
        raise _keys_refusal(
            f"key_width must be positive; got {key_width}",
            subject="key_width",
            source=_SHAFT_DRAWING_SOURCE,
        )
    _require(key_length, "[length]", "key_length")
    if key_length.magnitude <= 0:
        raise _keys_refusal(
            f"key_length must be positive; got {key_length}",
            subject="key_length",
            source=_SHAFT_DRAWING_SOURCE,
        )
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
    if key_height.magnitude <= 0:
        raise _keys_refusal(
            f"key_height must be positive; got {key_height}",
            subject="key_height",
            source=_SHAFT_DRAWING_SOURCE,
        )
    _require(key_length, "[length]", "key_length")
    if key_length.magnitude <= 0:
        raise _keys_refusal(
            f"key_length must be positive; got {key_length}",
            subject="key_length",
            source=_SHAFT_DRAWING_SOURCE,
        )
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
    if key_width.magnitude <= 0:
        raise _keys_refusal(
            f"key_width must be positive; got {key_width}",
            subject="key_width",
            source=_SHAFT_DRAWING_SOURCE,
        )
    _require(key_height, "[length]", "key_height")
    if key_height.magnitude <= 0:
        raise _keys_refusal(
            f"key_height must be positive; got {key_height}",
            subject="key_height",
            source=_SHAFT_DRAWING_SOURCE,
        )
    _require(allowable_shear, "[pressure]", "allowable_shear")
    _require(allowable_bearing, "[pressure]", "allowable_bearing")
    for subject, magnitude in (
        ("allowable_shear", allowable_shear.to("MPa").magnitude),
        ("allowable_bearing", allowable_bearing.to("MPa").magnitude),
    ):
        if magnitude <= 0:
            raise _keys_refusal(
                "allowable_shear and allowable_bearing must be positive",
                subject=subject,
                source=_ALLOWABLE_SOURCE,
            )
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
    # Ahead of the coercion: `int(inf)` raises OverflowError before the refusal below.
    require_finite(number_of_teeth, name="number_of_teeth")
    if int(number_of_teeth) != number_of_teeth or number_of_teeth <= 0:
        raise _keys_refusal(
            f"number_of_teeth must be a positive whole number; got {number_of_teeth}",
            subject="number_of_teeth",
            source=_SPLINE_STANDARD_SOURCE,
        )
    if not 0 < load_fraction <= 1:
        raise _keys_refusal(
            f"load_fraction must be in (0, 1]; got {load_fraction}",
            subject="load_fraction",
            source=_SPLINE_STANDARD_SOURCE,
        )
    p = allowable_pressure.to("MPa").magnitude
    r = mean_radius.to("mm").magnitude
    h = tooth_height.to("mm").magnitude
    length = spline_length.to("mm").magnitude
    for subject, magnitude in (
        ("allowable_pressure", p),
        ("mean_radius", r),
        ("tooth_height", h),
        ("spline_length", length),
    ):
        if magnitude <= 0:
            raise _keys_refusal(
                "pressure, mean_radius, tooth_height, and spline_length must be positive",
                subject=subject,
                source=_keys_input_source(subject),
            )
    torque_n_mm = load_fraction * p * number_of_teeth * h * length * r
    return Quantity(magnitude=torque_n_mm / 1000.0, unit="N*m")
