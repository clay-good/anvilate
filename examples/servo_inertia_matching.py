"""Worked example: the servo that direct drive stalls and inertia matching fixes.

A rotary index table (0.05 kg·m²) must accelerate at 200 rad/s², driven by a compact
servo with 3 N·m of peak torque and a 0.0002 kg·m² rotor. Coupled direct, the motor
faces the whole table: 10.0 N·m of acceleration torque against its 3 N·m peak
(SF 0.30), and an inertia ratio of 250 against the drive's allowable of 10 -- the
motor cannot even control the load, let alone move it. Direct drive fails twice.

The instinct is "add a big gearbox," but the gear ratio is not monotonic: the motor
torque is (J_m·i + J_L/i)·α, the load's share shrinking with i while the motor's own
share grows. At 50:1 the table feels light but the rotor -- spinning fifty times
faster -- costs 2.2 N·m by itself. The sweet spot is the inertia-matching ratio
i = √(J_L/J_m) = 15.8, where the reflected table inertia exactly equals the rotor's
own: the torque bottoms out at its closed-form minimum 2·α·√(J_m·J_L) = 1.26 N·m
(SF 2.37) and the inertia ratio is exactly 1.00 -- textbook servo tuning territory.

The lesson is that a servo gear ratio is a design variable with an *optimum*, not a
knob to crank: gear too little and the load dominates, gear too much and the motor
mostly accelerates itself, and the minimum-torque point is always where the two
inertias meet. Size the ratio by matching first, then check the torque and the
vendor's inertia-ratio bound -- both fall out of the same square root.

Run it directly (``python examples/servo_inertia_matching.py``);
:func:`screen_direct_drive` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    inertia_matching_gear_ratio,
    motor_acceleration_torque,
    reflected_inertia_ratio,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TABLE_INERTIA = Quantity.parse("0.05 kg*m**2")
MOTOR_INERTIA = Quantity.parse("0.0002 kg*m**2")
LOAD_ACCELERATION = Quantity.parse("200 rad/s**2")
MOTOR_PEAK_TORQUE = Quantity.parse("3 N*m")
ALLOWABLE_INERTIA_RATIO = 10.0  # the servo drive's datasheet bound


def _screen(gear_ratio: float) -> Scorecard:
    torque = motor_acceleration_torque(
        motor_inertia=MOTOR_INERTIA,
        load_inertia=TABLE_INERTIA,
        gear_ratio=gear_ratio,
        load_angular_acceleration=LOAD_ACCELERATION,
    )
    ratio = reflected_inertia_ratio(
        motor_inertia=MOTOR_INERTIA,
        load_inertia=TABLE_INERTIA,
        gear_ratio=gear_ratio,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "motor peak torque vs acceleration demand",
                computed=MOTOR_PEAK_TORQUE.to("N*m").magnitude / torque.to("N*m").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "drive inertia-ratio bound vs reflected load",
                computed=ALLOWABLE_INERTIA_RATIO / ratio,
                required=1.0,
            ),
        )
    )


def matched_ratio() -> float:
    """The inertia-matching gear ratio for this motor and table."""
    return inertia_matching_gear_ratio(motor_inertia=MOTOR_INERTIA, load_inertia=TABLE_INERTIA)


def screen_direct_drive() -> Scorecard:
    """Screen the table coupled direct (1:1): the motor fails twice."""
    return _screen(1.0)


def screen_matched_drive() -> Scorecard:
    """Screen the inertia-matched ratio: minimum torque, unity inertia ratio."""
    return _screen(matched_ratio())


def main() -> None:
    i_opt = matched_ratio()
    print(f"inertia-matching ratio: {i_opt:.1f}:1")
    for label, i in (("direct 1:1", 1.0), ("over-geared 50:1", 50.0), ("matched", i_opt)):
        torque = motor_acceleration_torque(
            motor_inertia=MOTOR_INERTIA,
            load_inertia=TABLE_INERTIA,
            gear_ratio=i,
            load_angular_acceleration=LOAD_ACCELERATION,
        )
        print(f"  {label}: {torque.to('N*m').magnitude:.2f} N*m at the motor")
    print("\ndirect drive:")
    print(screen_direct_drive().report())
    print("\ninertia-matched drive:")
    print(screen_matched_drive().report())


if __name__ == "__main__":
    main()
