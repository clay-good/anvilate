"""Worked example: sizing an incline conveyor, and the power the lift alone asks for.


A belt conveyor is sized by two numbers the job hands you: how much material it must move, and how
far up it must carry it. The throughput fixes the belt — mass flow is bulk density times the load
cross-section times belt speed, so for a required tonnage you pick a belt width (which sets the
cross-section) and back out the speed. The lift then fixes a floor on the power: raising material
through a height costs a rate of potential energy that no amount of clever design can avoid.

This example carries crushed rock (1500 kg/m³) up out of a quarry at 540 tonnes per hour. On a belt
whose troughed load profile is about 0.05 m², that throughput needs a belt speed of about 2 m/s — a
sensible, unhurried speed. If the same tonnage rode a narrower 0.033 m² profile, the belt would
have to run half again as fast, near 3 m/s, where fines start to spill and the belt wears; the fix
is a wider belt, not a faster one. The conveyor lifts the rock 30 m up the incline, and that lift
draws about 44 kW — the irreducible core of the drive power, before a single kW is spent on belt and
idler friction. The example computes the belt speed the throughput needs and the lift power the rise
demands, so the two levers of conveyor sizing — belt width and drive power — are separated cleanly.

Run it directly (``python examples/incline_conveyor_sizing.py``);
:func:`conveyor_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import belt_speed_for_capacity, conveyor_lift_power, conveyor_mass_flow
from anvilate.units import Quantity

BULK_DENSITY = Quantity.parse("1500 kg/m**3")  # crushed rock
THROUGHPUT = Quantity.parse("150 kg/s")  # 540 tonnes/hour
LOAD_PROFILE = Quantity.parse("0.05 m**2")
NARROW_PROFILE = Quantity.parse("0.033 m**2")
LIFT_HEIGHT = Quantity.parse("30 m")


def conveyor_sizing() -> dict[str, float]:
    """Return the belt speed for the throughput (two belt widths) and the lift power."""
    belt_speed = belt_speed_for_capacity(
        mass_flow=THROUGHPUT, bulk_density=BULK_DENSITY, cross_section_area=LOAD_PROFILE
    )
    narrow_speed = belt_speed_for_capacity(
        mass_flow=THROUGHPUT, bulk_density=BULK_DENSITY, cross_section_area=NARROW_PROFILE
    )
    # Confirm the chosen belt speed reproduces the throughput.
    check_flow = conveyor_mass_flow(
        bulk_density=BULK_DENSITY, cross_section_area=LOAD_PROFILE, belt_speed=belt_speed
    )
    lift_power = conveyor_lift_power(mass_flow=THROUGHPUT, lift_height=LIFT_HEIGHT)
    return {
        "belt_speed_ms": belt_speed.to("m/s").magnitude,
        "narrow_belt_speed_ms": narrow_speed.to("m/s").magnitude,
        "throughput_tph": check_flow.to("kg/s").magnitude * 3.6,
        "lift_power_kw": lift_power.to("kW").magnitude,
    }


def main() -> None:
    c = conveyor_sizing()
    print(f"throughput      : {c['throughput_tph']:.0f} tonnes/hour of crushed rock")
    print(
        f"belt speed      : {c['belt_speed_ms']:.1f} m/s on a 0.05 m^2 profile "
        f"(vs {c['narrow_belt_speed_ms']:.1f} m/s on a narrow 0.033 m^2)"
    )
    print(f"lift power (30 m): {c['lift_power_kw']:.0f} kW -- irreducible, before any friction")
    print("  -> throughput picks the belt width; the lift sets the floor on drive power")


if __name__ == "__main__":
    main()
