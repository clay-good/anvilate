"""T1 analytical servo drivetrain sizing (closed-form inertia reflection).

A motor turning a load through a gear ratio ``i`` (motor speed over load speed) sees
the load's inertia shrunk by the square of the ratio: J_L/i². That reflected inertia
is the heart of servo sizing. The torque the motor must produce to accelerate the
load at a load-side angular acceleration α is

    T_m = (J_m·i + J_L/i) · α,

its own inertia's share growing with the ratio while the load's share shrinks — so
the ratio has a sweet spot. Minimizing T_m gives the classic inertia-matching result

    i_opt = √(J_L / J_m),

the ratio at which the reflected load inertia exactly equals the motor's own
(and the minimum torque is 2·α·√(J_m·J_L)). Vendors express the same idea as the
inertia ratio (J_L/i²)/J_m, the number servo datasheets ask to be kept low (near 1
for aggressive motion, up to ~10 for gentle moves): too high and the motor cannot
control the load; far below 1 and the motor is mostly accelerating itself.

These are exact rigid-body results — friction, gearbox inertia, and load torque add
on top, and the gearbox's own inertia is best lumped into ``motor_inertia``. Inertias
are dimension-checked :class:`~anvilate.units.Quantity` values (kg·m²); the gear
ratio is a plain positive float.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "reflected_load_inertia",
    "reflected_inertia_ratio",
    "motor_acceleration_torque",
    "inertia_matching_gear_ratio",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _inertia_kgm2(value: Quantity, name: str) -> float:
    _require(value, "[mass] * [length]**2", name)
    magnitude = value.to("kg*m**2").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def _check_ratio(gear_ratio: float) -> float:
    if gear_ratio <= 0:
        raise ValueError(f"gear_ratio must be positive; got {gear_ratio}")
    return gear_ratio


def reflected_load_inertia(*, load_inertia: Quantity, gear_ratio: float) -> Quantity:
    """The load inertia J_L/i² the motor actually sees through a gear ratio.

    ``load_inertia`` J_L reflected through ``gear_ratio`` i (motor speed over load
    speed, > 0): a 10:1 reduction makes the load feel 100× lighter to the motor —
    the squared ratio is why even modest gearing tames a heavy load. Returns the
    reflected inertia in kg·m².
    """
    j_load = _inertia_kgm2(load_inertia, "load_inertia")
    i = _check_ratio(gear_ratio)
    return Quantity(magnitude=j_load / i**2, unit="kg*m**2")


def reflected_inertia_ratio(
    *,
    motor_inertia: Quantity,
    load_inertia: Quantity,
    gear_ratio: float,
) -> float:
    """The servo inertia ratio (J_L/i²)/J_m the motor datasheet screens against.

    The reflected load inertia over the motor's own ``motor_inertia`` — the
    dimensionless number servo vendors bound (near 1 for aggressive, dynamic moves;
    up to roughly 10 for gentle ones; the allowable is the drive datasheet's). At
    the inertia-matched ratio (:func:`inertia_matching_gear_ratio`) it is exactly 1.
    Returns the dimensionless ratio.
    """
    j_motor = _inertia_kgm2(motor_inertia, "motor_inertia")
    reflected = reflected_load_inertia(load_inertia=load_inertia, gear_ratio=gear_ratio)
    return reflected.to("kg*m**2").magnitude / j_motor


def motor_acceleration_torque(
    *,
    motor_inertia: Quantity,
    load_inertia: Quantity,
    gear_ratio: float,
    load_angular_acceleration: Quantity,
) -> Quantity:
    """The motor torque (J_m·i + J_L/i)·α to accelerate the load at α.

    The torque at the motor shaft that accelerates ``load_inertia`` J_L at the
    load-side ``load_angular_acceleration`` α through ``gear_ratio`` i, while also
    accelerating the motor's own ``motor_inertia`` J_m (which must spin i times
    faster). Gearing down shrinks the load's share but grows the motor's own — the
    trade the matching ratio optimizes. Friction and any static load torque add on
    top. Returns the motor torque in N·m.
    """
    j_motor = _inertia_kgm2(motor_inertia, "motor_inertia")
    j_load = _inertia_kgm2(load_inertia, "load_inertia")
    i = _check_ratio(gear_ratio)
    if not load_angular_acceleration.has_dimension("1 / [time]**2"):
        raise ValueError(
            "load_angular_acceleration must be an angular acceleration quantity; "
            f"got {load_angular_acceleration.dimensionality}"
        )
    alpha = load_angular_acceleration.to("rad/s**2").magnitude
    if alpha <= 0:
        raise ValueError(
            f"load_angular_acceleration must be positive; got {load_angular_acceleration}"
        )
    return Quantity(magnitude=(j_motor * i + j_load / i) * alpha, unit="N*m")


def inertia_matching_gear_ratio(
    *,
    motor_inertia: Quantity,
    load_inertia: Quantity,
) -> float:
    """The torque-minimizing gear ratio i_opt = √(J_L/J_m) — inertia matching.

    The ratio at which the reflected load inertia equals the motor's own, the
    inertia ratio is exactly 1, and the acceleration torque
    (:func:`motor_acceleration_torque`) is at its minimum 2·α·√(J_m·J_L). Gearing
    either side of it costs torque: below, the load dominates; above, the motor is
    mostly accelerating itself. Returns the dimensionless ratio (motor speed over
    load speed).
    """
    j_motor = _inertia_kgm2(motor_inertia, "motor_inertia")
    j_load = _inertia_kgm2(load_inertia, "load_inertia")
    return sqrt(j_load / j_motor)
