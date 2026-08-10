"""T1 analytical steady level-turn (coordinated-turn) flight mechanics (closed-form).

When an aircraft banks and holds altitude, the lift vector tips: its vertical component still
carries the weight while its horizontal component pulls the aircraft around the turn. That single
geometric fact sets everything about a coordinated, constant-altitude turn, and it is all
closed-form. These are the turning-flight companions to the straight-flight lift and drag of
:mod:`anvilate.analysis.wing_aerodynamics` — that module sizes the wing in level flight, this one
tells you how hard it can turn.

Banking to angle φ multiplies the lift the wing must make: L·cos φ = W forces the load factor
n = L/W = 1/cos φ, the "g" the airframe and pilot feel. The horizontal component L·sin φ supplies
the centripetal force, giving the turn radius R = V²/(g·tan φ) and the turn rate ω = g·tan φ/V for
a true airspeed V. Because the wing now works n times harder, it stalls sooner: the accelerated
stall speed climbs to V_s·√n. Angles are plain floats in degrees, load factor is a dimensionless
float, and speeds and rates are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import acos, atan, cos, degrees, radians, sqrt, tan

from ..units import Quantity

_STANDARD_GRAVITY = 9.80665  # m/s**2

__all__ = [
    "load_factor_from_bank_angle",
    "bank_angle_for_load_factor",
    "turn_radius",
    "turn_rate",
    "accelerated_stall_speed",
    "bank_angle_for_turn_rate",
]


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def load_factor_from_bank_angle(*, bank_angle: float) -> float:
    """The load factor n = 1/cos(φ) a coordinated level turn imposes.

    To hold altitude in a bank the wing's vertical lift component must still equal the weight,
    L·cos φ = W, so the total lift — and the load factor n = L/W = 1/cos φ — grows as the bank
    steepens. This is the "g" the airframe, the wing spar, and the pilot feel: a 60° bank already
    doubles it (2 g). ``bank_angle`` φ is in degrees and must lie in [0, 90); a 90° bank would
    demand infinite lift and cannot hold altitude. Returns the dimensionless load factor (≥ 1).
    """
    if not 0 <= bank_angle < 90:
        raise ValueError(f"bank_angle (degrees) must lie in [0, 90); got {bank_angle}")
    return 1.0 / cos(radians(bank_angle))


def bank_angle_for_load_factor(*, load_factor: float) -> float:
    """The bank angle φ = arccos(1/n) a target level-turn load factor requires.

    The sizing inverse of :func:`load_factor_from_bank_angle`: given a load factor n the airframe is
    rated for (or the pilot will pull), the steepest coordinated bank that stays at or below it is
    φ = arccos(1/n). ``load_factor`` n is dimensionless and must be at least 1 (level flight is
    n = 1 at zero bank; n < 1 cannot hold altitude in a bank). Returns the bank angle in degrees,
    in [0, 90).
    """
    if load_factor < 1:
        raise ValueError(f"load_factor must be at least 1; got {load_factor}")
    return degrees(acos(1.0 / load_factor))


def turn_radius(*, speed: Quantity, bank_angle: float) -> Quantity:
    """The radius R = V²/(g·tan(φ)) of a coordinated level turn.

    The horizontal component of lift, L·sin φ, is the only force turning the aircraft, and balancing
    it against the centripetal demand m·V²/R (with L·cos φ = W) gives R = V²/(g·tan φ). A faster
    aircraft sweeps a wider circle (radius grows with the square of speed) and a steeper bank
    tightens it. ``speed`` V is the true airspeed and ``bank_angle`` φ is in degrees, in (0, 90) —
    a level turn needs some bank. Returns the turn radius in metres.
    """
    _check(speed, "[velocity]", "speed")
    if not 0 < bank_angle < 90:
        raise ValueError(f"bank_angle (degrees) must lie in (0, 90); got {bank_angle}")
    v = speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("speed must be positive")
    return Quantity(magnitude=v * v / (_STANDARD_GRAVITY * tan(radians(bank_angle))), unit="m")


def turn_rate(*, speed: Quantity, bank_angle: float) -> Quantity:
    """The turn rate ω = g·tan(φ)/V of a coordinated level turn.

    How fast the aircraft's heading sweeps around: ω = g·tan φ/V, the angular-velocity companion of
    :func:`turn_radius` (ω = V/R). Unlike the radius it *falls* with airspeed, so a slow, steeply
    banked aircraft turns fastest in degrees per second — the reason tight, quick turns are flown
    slow. ``speed`` V is the true airspeed and ``bank_angle`` φ is in degrees, in (0, 90). Returns
    the turn rate in degrees per second.
    """
    _check(speed, "[velocity]", "speed")
    if not 0 < bank_angle < 90:
        raise ValueError(f"bank_angle (degrees) must lie in (0, 90); got {bank_angle}")
    v = speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("speed must be positive")
    omega = _STANDARD_GRAVITY * tan(radians(bank_angle)) / v  # rad/s
    return Quantity(magnitude=degrees(omega), unit="deg/s")


def accelerated_stall_speed(*, level_stall_speed: Quantity, load_factor: float) -> Quantity:
    """The accelerated stall speed V_s·√n a level turn raises the stall to.

    Stall happens at the maximum lift coefficient, and in a turn the wing must make n times the
    weight in lift, so it reaches that limit at a higher speed: V_s(n) = V_s·√n, where V_s is the
    1-g (wings-level) stall speed. A 2-g (60° bank) turn lifts the stall speed by √2 ≈ 41 %, so
    a hard, low-speed turn can stall an aircraft that was flying comfortably straight.
    ``level_stall_speed`` V_s is the wings-level stall speed and ``load_factor`` n is dimensionless
    and at least 1. Returns the accelerated stall speed in metres per second.
    """
    _check(level_stall_speed, "[velocity]", "level_stall_speed")
    if load_factor < 1:
        raise ValueError(f"load_factor must be at least 1; got {load_factor}")
    vs = level_stall_speed.to("m/s").magnitude
    if vs <= 0:
        raise ValueError("level_stall_speed must be positive")
    return Quantity(magnitude=vs * sqrt(load_factor), unit="m/s")


def bank_angle_for_turn_rate(*, speed: Quantity, turn_rate: Quantity) -> float:
    """The bank angle φ = arctan(ω·V/g) that flies a target level-turn rate at a given speed.

    The inverse of :func:`turn_rate`: to sweep heading at rate ω while holding airspeed V, bank to
    φ = arctan(ω·V/g). This is the standard-rate-turn question — what bank gives 3°/s here —
    and it shows why the required bank grows with airspeed, so fast aircraft need steeper banks (or
    accept a slower standard turn) to keep the same rate. ``speed`` V is the true airspeed and
    ``turn_rate`` ω is the desired heading rate (an angular velocity, positive). Returns the bank
    angle in degrees, in [0, 90).
    """
    _check(speed, "[velocity]", "speed")
    _check(turn_rate, "1/[time]", "turn_rate")
    v = speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("speed must be positive")
    omega = turn_rate.to("rad/s").magnitude
    if omega <= 0:
        raise ValueError("turn_rate must be positive")
    return degrees(atan(omega * v / _STANDARD_GRAVITY))
