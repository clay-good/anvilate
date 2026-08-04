"""T1 analytical highway/rail curve superelevation checks (closed-form).

A vehicle rounding a curve needs a centripetal force, supplied by banking the road (superelevation)
and by side friction between tire and pavement. The AASHTO curve-design relations balance the two.

The sharpest curve a design speed allows follows from setting the available cornering — the
superelevation rate e (the pavement's cross-slope, rise over run) plus the side-friction factor f —
equal to the centripetal demand: R_min = v²/(g·(e + f)). A faster road or a lower friction allowance
needs a flatter (larger-radius) curve.

Without any side friction, the curve must be banked so gravity alone turns the vehicle: the ideal
superelevation rate is e = v²/(g·R) — the cross-slope that lets a car round the curve on ice at the
design speed. Turned around, the fastest a given curve can be taken before the tires slide out is
v_max = √(g·R·(e + f)/(1 − e·f)). The friction factor and superelevation rate are the caller's from
the AASHTO tables; the balance is here.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "banked_curve_max_speed",
    "ideal_superelevation_rate",
    "minimum_curve_radius",
]

_GRAVITY = 9.80665  # m/s²


def minimum_curve_radius(
    *,
    design_speed: Quantity,
    superelevation_rate: float,
    side_friction_factor: float,
) -> Quantity:
    """The minimum curve radius for a design speed, R_min = v²/(g·(e + f)) (AASHTO).

    The tightest horizontal curve a road may use at its ``design_speed`` v, given the maximum
    ``superelevation_rate`` e (pavement cross-slope, ~0.04–0.12) and ``side_friction_factor`` f the
    policy allows: R_min = v²/(g·(e + f)). The two cornering contributions add, so a steeper bank or
    a higher friction allowance permits a sharper curve. Returns the minimum radius in metres.
    """
    _check(design_speed, "[length]/[time]", "design_speed")
    v = design_speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("design_speed must be positive")
    combined = superelevation_rate + side_friction_factor
    if combined <= 0:
        raise ValueError("superelevation_rate + side_friction_factor must be positive")
    return Quantity(magnitude=v**2 / (_GRAVITY * combined), unit="m")


def ideal_superelevation_rate(*, speed: Quantity, radius: Quantity) -> float:
    """The superelevation rate that needs no side friction, e = v²/(g·R).

    The pavement cross-slope (tan of the bank angle) at which gravity alone supplies the centripetal
    force, so a vehicle rounds the curve at ``speed`` v on ``radius`` R with zero reliance on tire
    friction — the rate that keeps a car on line even on ice: e = v²/(g·R). Real designs bank less
    than this and let friction make up the rest, but it is the ceiling the geometry works toward.
    Returns the dimensionless superelevation rate.
    """
    _check(speed, "[length]/[time]", "speed")
    _check(radius, "[length]", "radius")
    v = speed.to("m/s").magnitude
    r = radius.to("m").magnitude
    if v <= 0:
        raise ValueError("speed must be positive")
    if r <= 0:
        raise ValueError("radius must be positive")
    return v**2 / (_GRAVITY * r)


def banked_curve_max_speed(
    *,
    radius: Quantity,
    superelevation_rate: float,
    side_friction_factor: float,
) -> Quantity:
    """The fastest a banked curve can be taken before sliding, v = √(g·R·(e + f)/(1 − e·f)).

    The maximum speed at which a vehicle holds a curve of ``radius`` R banked at ``superelevation_
    rate`` e (tan of the bank angle) with an available ``side_friction_factor`` f before the tires
    slide out: v = √(g·R·(e + f)/(1 − e·f)). The (1 − e·f) denominator is the small coupling between
    bank and friction; for the gentle slopes of real roads it is close to 1. Returns the maximum
    speed in m/s.
    """
    _check(radius, "[length]", "radius")
    r = radius.to("m").magnitude
    if r <= 0:
        raise ValueError("radius must be positive")
    if superelevation_rate < 0 or side_friction_factor < 0:
        raise ValueError("superelevation_rate and side_friction_factor must be non-negative")
    denominator = 1.0 - superelevation_rate * side_friction_factor
    if denominator <= 0:
        raise ValueError("superelevation_rate·side_friction_factor must be less than 1")
    numerator = superelevation_rate + side_friction_factor
    if numerator <= 0:
        raise ValueError("superelevation_rate + side_friction_factor must be positive")
    return Quantity(magnitude=sqrt(_GRAVITY * r * numerator / denominator), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
