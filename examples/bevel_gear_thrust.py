"""Worked example: the bevel gear that pushed harder than its pinion.

A right-angle bevel pair reduces 2:1 — an 18-tooth pinion driving a 36-tooth gear
— carrying 4000 N of tangential tooth load. Both members feel the same separating
force, but a bevel tooth resolves it about its pitch cone, and the two members sit
on very different cones: the pinion's half-angle is 26.6 degrees, the gear's its
complement at 63.4 degrees. So the axial thrust W_t*tan(phi)*sin(gamma) they throw
along their shafts is nowhere near equal.

The pinion throws 651 N of thrust; the gear throws 1302 N — exactly twice as much,
because the thrust ratio between the two members is the gear ratio itself. A single
1200 N thrust bearing sized for the drive holds the pinion comfortably (1.84) but
is overrun by the gear (0.92). Sizing both shafts' thrust bearings to the pinion's
load, or to some average, leaves the gear shaft under-bearinged and creeping.

On a bevel pair the larger, slower member carries the larger thrust, in proportion
to the ratio. Each shaft needs a thrust bearing sized for its own member, and it is
the big gear — not the fast little pinion — that sets the heavier one. The bearing
rating is catalogue data, declared inline like any allowable.

Run it directly (``python examples/bevel_gear_thrust.py``);
:func:`screen_bevel_thrust` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import bevel_gear_axial_load, bevel_pitch_cone_angle
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TANGENTIAL_LOAD = Quantity.parse("4000 N")
PRESSURE_ANGLE = 20.0
PINION_TEETH = 18
GEAR_TEETH = 36
THRUST_BEARING_RATING = Quantity.parse("1200 N")

MEMBERS = {
    "pinion (18 teeth)": (PINION_TEETH, GEAR_TEETH),
    "gear (36 teeth)": (GEAR_TEETH, PINION_TEETH),
}


def member_thrust(member_teeth: int, mate_teeth: int) -> Quantity:
    """The axial thrust a bevel member throws, resolved about its own pitch cone."""
    cone_angle = bevel_pitch_cone_angle(pinion_teeth=member_teeth, gear_teeth=mate_teeth)
    return bevel_gear_axial_load(
        tangential_load=TANGENTIAL_LOAD,
        pressure_angle=PRESSURE_ANGLE,
        pitch_cone_angle=cone_angle,
    )


def screen_bevel_thrust() -> Scorecard:
    """Screen each member's shaft: the thrust bearing rating must exceed the
    member's axial thrust (safety factor = rating / thrust)."""
    rating = THRUST_BEARING_RATING.to("N").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            name,
            computed=rating / member_thrust(member_teeth, mate_teeth).to("N").magnitude,
            required=1.0,
        )
        for name, (member_teeth, mate_teeth) in MEMBERS.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, (member_teeth, mate_teeth) in MEMBERS.items():
        thrust = member_thrust(member_teeth, mate_teeth).to("N").magnitude
        print(f"{name}: axial thrust {thrust:.0f} N")
    print(screen_bevel_thrust())


if __name__ == "__main__":
    main()
