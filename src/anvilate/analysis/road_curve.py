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

The other half of curve design is being able to *see* far enough to stop. The stopping sight
distance is the reaction distance a vehicle covers while the driver perceives and reacts (d_r = v·t,
the speed times the perception-reaction time) plus the braking distance it then needs to halt
(d_b = v²/(2·(a + g·G)), the speed squared over twice the deceleration, with the road grade G
helping on an upgrade and hurting on a downgrade). Their sum, SSD = v·t + v²/(2·(a + g·G)), is the
sight line a horizontal or crest curve has to provide — the check that pairs with the cornering one.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "banked_curve_max_speed",
    "braking_distance",
    "ideal_superelevation_rate",
    "minimum_curve_radius",
    "perception_reaction_distance",
    "stopping_sight_distance",
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


def braking_distance(
    *,
    speed: Quantity,
    deceleration: Quantity,
    grade: float = 0.0,
) -> Quantity:
    """The distance to brake to a stop, d = v²/(2·(a + g·G)) (AASHTO).

    How far a vehicle travels braking from ``speed`` v to a stop at a ``deceleration`` a (AASHTO
    takes a ≈ 3.4 m/s² for design): d = v²/(2·(a + g·G)). The road ``grade`` G (a decimal, positive
    uphill) adds its gravity component g·G to the braking on an upgrade and subtracts it on a
    downgrade — which is why a steep downgrade lengthens the stop and governs sight-distance design.
    Feeds :func:`stopping_sight_distance`. Raises if a downgrade overwhelms the braking
    (a + g·G ≤ 0, no net deceleration). Returns the braking distance in metres.
    """
    _check(speed, "[length]/[time]", "speed")
    _check(deceleration, "[length]/[time]**2", "deceleration")
    v = speed.to("m/s").magnitude
    a = deceleration.to("m/s**2").magnitude
    if v < 0:
        raise ValueError("speed must be non-negative")
    if a <= 0:
        raise ValueError("deceleration must be positive")
    effective = a + _GRAVITY * grade
    if effective <= 0:
        raise ValueError("a + g·grade must be positive (the downgrade overwhelms the braking)")
    return Quantity(magnitude=v**2 / (2.0 * effective), unit="m")


def perception_reaction_distance(*, speed: Quantity, reaction_time: Quantity) -> Quantity:
    """The distance covered before braking begins, d = v·t.

    How far a vehicle travels at ``speed`` v during the ``reaction_time`` t the driver takes to
    perceive a hazard and move to the brake — before any deceleration starts: d = v·t. AASHTO uses
    t = 2.5 s for stopping sight distance. It is the first term of :func:`stopping_sight_distance`,
    and because it is linear in speed it dominates the sight requirement at low speeds where the
    braking term is small. Returns the reaction distance in metres.
    """
    _check(speed, "[length]/[time]", "speed")
    _check(reaction_time, "[time]", "reaction_time")
    v = speed.to("m/s").magnitude
    t = reaction_time.to("s").magnitude
    if v < 0:
        raise ValueError("speed must be non-negative")
    if t < 0:
        raise ValueError("reaction_time must be non-negative")
    return Quantity(magnitude=v * t, unit="m")


def stopping_sight_distance(
    *,
    speed: Quantity,
    deceleration: Quantity,
    reaction_time: Quantity,
    grade: float = 0.0,
) -> Quantity:
    """The stopping sight distance, SSD = v·t + v²/(2·(a + g·G)) (AASHTO).

    The sight line a road must give a driver to stop safely: the
    :func:`perception_reaction_distance` v·t covered while reacting plus the
    :func:`braking_distance` v²/(2·(a + g·G)) needed to halt, from the ``speed`` v, the
    ``deceleration`` a, the ``reaction_time`` t, and the road ``grade`` G (decimal, positive up).
    This is the distance a horizontal or crest vertical curve must keep clear of obstructions — the
    check that complements :func:`minimum_curve_radius`. Returns the sight distance in metres.
    """
    reaction = perception_reaction_distance(speed=speed, reaction_time=reaction_time)
    braking = braking_distance(speed=speed, deceleration=deceleration, grade=grade)
    return Quantity(magnitude=reaction.to("m").magnitude + braking.to("m").magnitude, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
