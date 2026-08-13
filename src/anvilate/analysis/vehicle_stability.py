"""T1 analytical vehicle rollover and lateral-stability checks (closed-form).

A vehicle cornering hard can fail two different ways: it can slide, when the tyres run out of grip,
or it can *tip*, when the weight swings far enough outboard that the inside wheels lift. The sliding
limit is the friction geometry of :mod:`anvilate.analysis.road_curve`; this module covers the
*tipping* limit, the one that governs tall, narrow vehicles — SUVs, vans, loaded trucks — that run
out of stability before they run out of grip.

The single number behind it is the static stability factor SSF = t/(2·h), the half-track over the
centre-of-gravity height. For a rigid vehicle it is exactly the steady lateral acceleration, in g,
at which the inside wheels lift, so a low, wide car (SSF ≈ 1.5) tips only past 1.5 g while a tall
SUV (SSF ≈ 1.0) tips at 1 g. On a flat curve of radius R that threshold is reached at the rollover
speed v = √(SSF·g·R), and in any turn of lateral acceleration a_y the outer wheels pick up a load
transfer ΔF = m·a_y·h/t off the inner ones — the shift that, once it equals the axle's static load,
lifts the inside wheels. Masses, speeds, and forces are dimension-checked
:class:`~anvilate.units.Quantity` values; the SSF is a plain float.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

_STANDARD_GRAVITY = 9.80665  # m/s**2

__all__ = [
    "static_stability_factor",
    "rollover_threshold_speed",
    "lateral_load_transfer",
]


def static_stability_factor(*, track_width: Quantity, center_of_gravity_height: Quantity) -> float:
    """The static stability factor, SSF = t/(2·h).

    The half-track ``track_width`` t over the ``center_of_gravity_height`` h: SSF = t/(2·h). For a
    rigid vehicle it is exactly the steady lateral acceleration, in g, at which the inside wheels
    lift — so it doubles as the rollover threshold. A wide, low vehicle scores high (harder to tip);
    a tall, narrow one scores near or below 1, and roof loads that raise h push it lower. Returns
    the dimensionless SSF (equivalently, the rollover threshold in g).
    """
    _check(track_width, "[length]", "track_width")
    _check(center_of_gravity_height, "[length]", "center_of_gravity_height")
    t = track_width.to("m").magnitude
    h = center_of_gravity_height.to("m").magnitude
    if t <= 0:
        raise ValueError("track_width must be positive")
    if h <= 0:
        raise ValueError("center_of_gravity_height must be positive")
    return t / (2.0 * h)


def rollover_threshold_speed(*, static_stability_factor: float, curve_radius: Quantity) -> Quantity:
    """The rollover threshold speed on a flat curve, v = √(SSF·g·R).

    The steady speed at which cornering on a flat (unbanked) curve of radius ``curve_radius`` R
    develops the lateral acceleration SSF·g that lifts the inside wheels: v = √(SSF·g·R), for a
    ``static_stability_factor`` SSF (from :func:`static_stability_factor`). Below it the vehicle
    corners; above it a tall vehicle tips before it slides. A wider curve or a more stable vehicle
    raises the speed. ``static_stability_factor`` must be positive. Returns the speed in m/s.
    """
    if static_stability_factor <= 0:
        raise ValueError("static_stability_factor must be positive")
    _check(curve_radius, "[length]", "curve_radius")
    r = curve_radius.to("m").magnitude
    if r <= 0:
        raise ValueError("curve_radius must be positive")
    return Quantity(magnitude=sqrt(static_stability_factor * _STANDARD_GRAVITY * r), unit="m/s")


def lateral_load_transfer(
    *,
    vehicle_mass: Quantity,
    lateral_acceleration: Quantity,
    center_of_gravity_height: Quantity,
    track_width: Quantity,
) -> Quantity:
    """The lateral load transfer in a turn, ΔF = m·a_y·h/t.

    Cornering swings weight outboard: the outer wheels gain, and the inner wheels lose, a vertical
    load ΔF = m·a_y·h/t — the ``vehicle_mass`` m times the ``lateral_acceleration`` a_y times the
    ``center_of_gravity_height`` h over the ``track_width`` t. It grows with cornering severity and
    with a tall, narrow stance; when it reaches the static per-side axle load the inside wheels lift
    and the vehicle is at its rollover threshold. Returns the transferred vertical load in N.
    """
    _check(vehicle_mass, "[mass]", "vehicle_mass")
    _check(lateral_acceleration, "[length]/[time]**2", "lateral_acceleration")
    _check(center_of_gravity_height, "[length]", "center_of_gravity_height")
    _check(track_width, "[length]", "track_width")
    m = vehicle_mass.to("kg").magnitude
    a_y = lateral_acceleration.to("m/s**2").magnitude
    h = center_of_gravity_height.to("m").magnitude
    t = track_width.to("m").magnitude
    if m <= 0:
        raise ValueError("vehicle_mass must be positive")
    if a_y < 0:
        raise ValueError("lateral_acceleration must be non-negative")
    if h <= 0:
        raise ValueError("center_of_gravity_height must be positive")
    if t <= 0:
        raise ValueError("track_width must be positive")
    return Quantity(magnitude=m * a_y * h / t, unit="N")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
