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
    "understeer_gradient",
    "vehicle_characteristic_speed",
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


def understeer_gradient(
    *,
    front_axle_load: Quantity,
    rear_axle_load: Quantity,
    front_cornering_stiffness: Quantity,
    rear_cornering_stiffness: Quantity,
) -> float:
    """The understeer gradient, K = W_f/C_f − W_r/C_r (rad per g).

    This module covered rollover — the vehicle tipping over — and nothing covered the other half
    of stability: whether the car goes where it is pointed. :func:`anvilate.analysis.vehicle.
    ackermann_steer_angle` gives the neutral-steer bicycle model with no correction for how hard
    each axle's tyres are actually working.

    K compares the two axles' slip demands. Each axle needs slip angle proportional to its share
    of the lateral load over its cornering stiffness, and the *difference* decides the behaviour:

    - **K > 0, understeer.** The front slips more, so the car runs wide and needs more steering as
      it goes faster. Stable — this is what every production car is tuned for.
    - **K = 0, neutral steer.** Steering angle is independent of speed.
    - **K < 0, oversteer.** The rear slips more and the car turns in tighter than commanded. It is
      stable only below a critical speed; above it the response diverges.

    A 12 kN car with 7 kN on the front, C_f = 60 kN/rad and C_r = 55 kN/rad gives K = 0.02576
    rad/g — mildly understeering. Nothing in the library previously distinguished that from a
    rear-biased setup with K < 0, which goes unstable above its critical speed while passing every
    existing stability check. Pair with :func:`vehicle_characteristic_speed`.

    Axle loads are forces (they must sum to the vehicle weight); cornering stiffnesses are force
    per radian of slip. Returns K as a plain float in radians per g.
    """
    _check(front_axle_load, "[force]", "front_axle_load")
    _check(rear_axle_load, "[force]", "rear_axle_load")
    _check(front_cornering_stiffness, "[force]", "front_cornering_stiffness")
    _check(rear_cornering_stiffness, "[force]", "rear_cornering_stiffness")
    w_f = front_axle_load.to("N").magnitude
    w_r = rear_axle_load.to("N").magnitude
    c_f = front_cornering_stiffness.to("N").magnitude
    c_r = rear_cornering_stiffness.to("N").magnitude
    if w_f <= 0 or w_r <= 0:
        raise ValueError("front_axle_load and rear_axle_load must be positive")
    if c_f <= 0 or c_r <= 0:
        raise ValueError("cornering stiffnesses must be positive")
    return w_f / c_f - w_r / c_r


def vehicle_characteristic_speed(*, understeer_gradient: float, wheelbase: Quantity) -> Quantity:
    """The characteristic speed of an understeering car, V = √(L·g/K).

    The speed that gives the understeer gradient from :func:`understeer_gradient` its physical
    meaning: an understeering vehicle needs *twice* its low-speed Ackermann steering angle to hold
    the same radius at V_char. It is the natural yardstick for how strongly a car understeers —
    a low characteristic speed means a lot of extra steering is needed early.

    With K = 0.02576 rad/g and a 2.7 m wheelbase, V_char is 32.1 m/s (115 km/h).

    The same expression evaluated with |K| for an **oversteering** car (K < 0) gives the *critical*
    speed instead, and that number means something far more serious: above it the yaw response
    diverges and the vehicle is open-loop unstable. This function refuses K ≤ 0 rather than
    quietly returning a speed that looks reassuring but is the boundary of a spin — an
    oversteering setup needs the critical-speed interpretation, stated explicitly, not a value
    that reads like a characteristic speed.

    Returns the characteristic speed in m/s.
    """
    _check(wheelbase, "[length]", "wheelbase")
    length = wheelbase.to("m").magnitude
    if length <= 0:
        raise ValueError(f"wheelbase must be positive; got {wheelbase}")
    if understeer_gradient <= 0:
        raise ValueError(
            f"understeer_gradient must be positive for a characteristic speed; got "
            f"{understeer_gradient}. A neutral car (K = 0) has none, and for an oversteering car "
            f"(K < 0) the same expression with |K| is the CRITICAL speed above which the yaw "
            f"response diverges -- a different quantity with a different meaning."
        )
    return Quantity(magnitude=sqrt(length * 9.80665 / understeer_gradient), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
