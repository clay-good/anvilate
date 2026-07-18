"""Capstone: a V-belt drive, sized past its geometry to its grip.

A 7.5 kW motor at 1450 rpm drives a 2:1 V-belt reduction -- a 125 mm driver and a 250 mm
driven pulley, 600 mm apart. Four checks decide whether the drive works, and they pull from
the belt, the drive geometry, and the bearings:

1. **Belt grip** -- the force a single belt can transmit before it slips (Euler-Eytelwein
   with the V-groove wedge friction, at the running belt speed), against the *design* force
   the motor delivers with a 1.2 service factor for the load.
2. **Wrap angle** -- the arc the belt hugs the small pulley, against a 120° minimum.
3. **Belt speed** -- the linear belt speed, against a ~25 m/s ceiling for V-belts.
4. **Bearing life** -- the pulley-shaft bearing's L10 life under the belt pull (T1 + T2),
   against a service-life target.

Three of the four are comfortable: the belt wraps 168° of the small pulley (safety factor
1.40), runs at a sedate 9.5 m/s (2.63), and the bearings last ten times the target (10.6).
But the **single belt slips** -- its 785 N grip falls short of the 949 N design force, a
safety factor of 0.83. The drive is geometrically fine and mechanically fine; it just cannot
hold the torque on one belt.

The fix is not a bigger motor or a longer center distance -- those checks already pass. It is
simply *more belts*: splitting the load across two belts halves each one's share and lifts the
grip safety factor to 1.65. The lesson is that a belt drive is usually limited by traction, not
by geometry or the shaft, and the traction shortfall is answered by belt count, the one knob
the other three checks say nothing about.

Run it directly (``python examples/v_belt_drive.py``);
:func:`screen_drive` is also exercised in the test suite.
"""

from __future__ import annotations

from math import degrees, pi

from anvilate.analysis import (
    bearing_life_hours,
    belt_max_transmissible_force_at_speed,
    belt_slack_tension,
    belt_wrap_angle,
    vee_belt_effective_friction,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

POWER = Quantity.parse("7.5 kW")
SERVICE_FACTOR = 1.2
SPEED = Quantity.parse("1450 rpm")
DRIVER_DIAMETER = Quantity.parse("125 mm")
DRIVEN_DIAMETER = Quantity.parse("250 mm")
CENTER_DISTANCE = Quantity.parse("600 mm")
LINEAR_DENSITY = Quantity.parse("0.1 kg/m")
GROOVE_ANGLE = 38.0
FRICTION = 0.3
TIGHT_TENSION = Quantity.parse("850 N")  # installed per belt

MIN_WRAP_ANGLE_DEG = 120.0
MAX_BELT_SPEED = Quantity.parse("25 m/s")
BEARING_DYNAMIC_RATING = Quantity.parse("12 kN")
SERVICE_LIFE_TARGET = Quantity.parse("20000 hour")


def _belt_speed() -> Quantity:
    v = pi * DRIVER_DIAMETER.to("m").magnitude * SPEED.to("rpm").magnitude / 60.0
    return Quantity(magnitude=v, unit="m/s")


def _screen(number_of_belts: int) -> Scorecard:
    belt_speed = _belt_speed()
    effective_friction = vee_belt_effective_friction(
        friction_coefficient=FRICTION, groove_angle=GROOVE_ANGLE
    )
    wrap = belt_wrap_angle(
        large_pulley_diameter=DRIVEN_DIAMETER,
        small_pulley_diameter=DRIVER_DIAMETER,
        center_distance=CENTER_DISTANCE,
    )
    # Design force the motor delivers (with the service factor), shared across the belts.
    design_force = (
        SERVICE_FACTOR * POWER.to("W").magnitude / belt_speed.to("m/s").magnitude / number_of_belts
    )
    grip = belt_max_transmissible_force_at_speed(
        tight_tension=TIGHT_TENSION,
        linear_density=LINEAR_DENSITY,
        belt_speed=belt_speed,
        friction_coefficient=effective_friction,
        wrap_angle=wrap,
    )
    # Shaft (radial) pull: both strands pull the pulley the same way, T1 + T2, per belt.
    slack = belt_slack_tension(
        tight_tension=TIGHT_TENSION, friction_coefficient=effective_friction, wrap_angle=wrap
    )
    shaft_pull = number_of_belts * (TIGHT_TENSION.to("N").magnitude + slack.to("N").magnitude)
    life = bearing_life_hours(
        dynamic_load_rating=BEARING_DYNAMIC_RATING,
        equivalent_load=Quantity(magnitude=shaft_pull / 2.0, unit="N"),  # two bearings
        speed=SPEED,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "belt grip (slip)",
                computed=grip.to("N").magnitude / design_force,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "small-pulley wrap angle",
                computed=degrees(wrap) / MIN_WRAP_ANGLE_DEG,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "belt speed",
                computed=MAX_BELT_SPEED.to("m/s").magnitude / belt_speed.to("m/s").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "pulley bearing L10 life",
                computed=life.to("hour").magnitude / SERVICE_LIFE_TARGET.to("hour").magnitude,
                required=1.0,
            ),
        )
    )


def screen_drive() -> Scorecard:
    """Screen the single-belt drive: fine on geometry and bearings, but the belt slips."""
    return _screen(1)


def screen_two_belt_drive() -> Scorecard:
    """Screen the two-belt drive: sharing the load across two belts restores the grip."""
    return _screen(2)


def main() -> None:
    print("single belt:")
    print(screen_drive())
    print("\ntwo belts:")
    print(screen_two_belt_drive())


if __name__ == "__main__":
    main()
