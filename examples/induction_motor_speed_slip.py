"""Worked example: what sets an induction motor's speed, and why it never quite hits it.

An AC motor's speed is not a free parameter — it is nailed down by the supply frequency and the
number of poles wound into the stator, Ns = 120·f/p. Doubling the poles halves the speed; that is
the only lever, short of a variable-frequency drive. This example reads off the synchronous speed
for a 60 Hz motor at two pole counts and shows why the nameplate speed is always a bit under it.

A 2-pole motor synchronizes at 3600 rpm and a 4-pole at 1800 rpm — the classic high- and
medium-speed choices. But an induction motor can never reach synchronous speed: if the rotor
turned exactly with the field it would see no changing flux, induce no current, and make no torque.
So it settles a little behind, and that lag is the slip. This 4-pole motor's nameplate says 1,750
rpm, a slip of 2.8% — small, but it is the whole reason the motor produces torque at all, and it is
what the rotor bars feel as a low 1.7 Hz. The lesson is that synchronous speed is a fixed grid of
values you pick from with the pole count, and slip is the small, necessary gap that turns a spinning
field into shaft torque.

Run it directly (``python examples/induction_motor_speed_slip.py``);
:func:`motor_speeds` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import motor_slip, motor_synchronous_speed
from anvilate.units import Quantity

LINE_FREQUENCY = Quantity.parse("60 Hz")
NAMEPLATE_SPEED = Quantity.parse("1750 rpm")  # a 4-pole motor at full load


def motor_speeds() -> dict[str, float]:
    """Return the 2- and 4-pole synchronous speeds and the 4-pole full-load slip."""
    two_pole = motor_synchronous_speed(line_frequency=LINE_FREQUENCY, poles=2)
    four_pole = motor_synchronous_speed(line_frequency=LINE_FREQUENCY, poles=4)
    slip = motor_slip(synchronous_speed=four_pole, rotor_speed=NAMEPLATE_SPEED)
    return {
        "two_pole_rpm": two_pole.to("rpm").magnitude,
        "four_pole_rpm": four_pole.to("rpm").magnitude,
        "full_load_slip": slip,
    }


def main() -> None:
    s = motor_speeds()
    print(f"2-pole synchronous speed : {s['two_pole_rpm']:.0f} rpm")
    print(f"4-pole synchronous speed : {s['four_pole_rpm']:.0f} rpm")
    print(f"4-pole nameplate 1750 rpm -> slip {s['full_load_slip'] * 100:.1f}%")
    print("  -> the pole count picks the speed off a fixed grid; slip is the gap that makes torque")


if __name__ == "__main__":
    main()
