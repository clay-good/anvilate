"""Worked example: the belt drive that couldn't be fixed with speed.

A machine needs 5.5 kW through a flat belt whose rated (allowable) tight-side
tension is 500 N, running on a 100 mm driver pulley with a 168-degree wrap and
mu = 0.30. At 3,000 rpm the drive comes up short -- 4.0 kW. The reflex fix is
to spin it faster: power is force times speed, so double the speed, double the
power. But a moving belt spends m'*v^2 of its tension just holding itself on
the pulley arc, and that centrifugal share grips nothing. At 6,000 rpm the
belt is 15% past its best speed and delivers 4.7 kW -- still short, and every
extra rpm from here delivers *less*.

The ceiling is set by v* = sqrt(T1/(3*m')): at ~25.8 m/s this belt peaks at
5.0 kW, so no pulley ratio or motor swap reaches 5.5 kW. The fix has to raise
the tension rating -- a wider (700 N) belt at its own best speed carries
8.4 kW with margin. The lesson: past v*, speed is spent carrying the belt, not
the load; when the power ceiling is below the demand, buy belt, not rpm.

The belt tension rating, mass per length, and friction are catalogue values,
declared inline like any allowable.

Run it directly (``python examples/high_speed_belt_drive.py``);
:func:`screen_belt_drive` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    belt_max_transmissible_force_at_speed,
    belt_speed_for_max_power,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

REQUIRED_POWER = Quantity.parse("5.5 kW")
DRIVER_DIAMETER = Quantity.parse("100 mm")
WRAP_ANGLE = 2.9413  # radians (~168.5 deg) on the small pulley, from the drive geometry
FRICTION = 0.30
RATED_TENSION = Quantity.parse("500 N")  # catalogue allowable tight-side tension
LINEAR_DENSITY = Quantity.parse("0.25 kg/m")  # catalogue belt mass per length
WIDER_TENSION = Quantity.parse("700 N")  # the next belt width up

SPEEDS_RPM = (3000.0, 6000.0)


def _belt_speed(rpm: float) -> Quantity:
    """The belt (pitch-line) speed of the driver pulley at ``rpm``."""
    d = DRIVER_DIAMETER.to("m").magnitude
    return Quantity(magnitude=pi * d * rpm / 60.0, unit="m/s")


def _power_watts(tight_tension: Quantity, belt_speed: Quantity) -> float:
    """The power the belt transmits at ``belt_speed``, P = F * v."""
    force = belt_max_transmissible_force_at_speed(
        tight_tension=tight_tension,
        linear_density=LINEAR_DENSITY,
        belt_speed=belt_speed,
        friction_coefficient=FRICTION,
        wrap_angle=WRAP_ANGLE,
    )
    return force.to("N").magnitude * belt_speed.to("m/s").magnitude


def screen_belt_drive() -> Scorecard:
    """Screen the 500 N belt at each running speed and at its power ceiling
    (the max-power speed v*), then the wider 700 N belt at its own v*."""
    required = REQUIRED_POWER.to("W").magnitude
    entries = []
    for rpm in SPEEDS_RPM:
        margin = _power_watts(RATED_TENSION, _belt_speed(rpm)) / required
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"5.5 kW at {rpm:.0f} rpm", computed=margin, required=1.0
            )
        )
    v_star = belt_speed_for_max_power(tight_tension=RATED_TENSION, linear_density=LINEAR_DENSITY)
    ceiling = _power_watts(RATED_TENSION, v_star) / required
    entries.append(
        ScorecardEntry.from_safety_factor("power ceiling at v*", computed=ceiling, required=1.0)
    )
    wider_v_star = belt_speed_for_max_power(
        tight_tension=WIDER_TENSION, linear_density=LINEAR_DENSITY
    )
    wider = _power_watts(WIDER_TENSION, wider_v_star) / required
    entries.append(
        ScorecardEntry.from_safety_factor(
            "wider (700 N) belt at its v*", computed=wider, required=1.0
        )
    )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    v_star = belt_speed_for_max_power(tight_tension=RATED_TENSION, linear_density=LINEAR_DENSITY)
    print(f"max-power belt speed v*: {v_star.to('m/s').magnitude:.1f} m/s")
    for rpm in SPEEDS_RPM:
        v = _belt_speed(rpm)
        print(
            f"{rpm:.0f} rpm -> {v.to('m/s').magnitude:.1f} m/s, "
            f"{_power_watts(RATED_TENSION, v) / 1000.0:.2f} kW"
        )
    print(screen_belt_drive())


if __name__ == "__main__":
    main()
