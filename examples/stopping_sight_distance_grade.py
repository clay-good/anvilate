"""Worked example: why a downhill highway curve has to be built to see farther.

Designing a curve is not only about cornering — a driver also has to see far enough ahead to stop
for a hazard, and that stopping sight distance is what a crest curve or a roadside obstruction on a
horizontal curve must keep clear. It has two parts. First the driver reacts: at highway speed a car
covers a surprising distance in the couple of seconds it takes to perceive a hazard and hit the
brakes, all before slowing at all. Then it brakes to a stop, over a distance that grows with the
square of speed — and that braking distance depends on the grade, because on a downgrade gravity is
pulling the car along while the brakes try to stop it.

This example takes a 110 km/h freeway with AASHTO's design assumptions: a 2.5 s perception-reaction
time and a 3.4 m/s² deceleration. On the level, the driver covers about 76 m reacting and about
137 m braking, for a stopping sight distance near 214 m. Put the same curve on a 4% downgrade and
the reaction distance is unchanged, but the braking distance stretches to about 155 m as gravity
fights the brakes — pushing the required sight distance to about 232 m, roughly 18 m more. That
extra sight distance is real geometry: a longer crest curve, a wider clearing on the inside of a
bend. The lesson every alignment turns on is that the downgrade, not the level case, governs —
sizing sight distance on flat-road numbers under-builds the very curves where stopping is hardest.

Run it directly (``python examples/stopping_sight_distance_grade.py``);
:func:`sight_distance_by_grade` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import stopping_sight_distance
from anvilate.units import Quantity

DESIGN_SPEED = Quantity.parse("30.5556 m/s")  # 110 km/h
DECELERATION = Quantity.parse("3.4 m/s**2")  # AASHTO design deceleration
REACTION_TIME = Quantity.parse("2.5 s")  # AASHTO perception-reaction time
DOWNGRADE = -0.04  # 4% downhill


def sight_distance_by_grade() -> dict[str, float]:
    """Return the stopping sight distance on the level and on a 4% downgrade."""
    level = stopping_sight_distance(
        speed=DESIGN_SPEED,
        deceleration=DECELERATION,
        reaction_time=REACTION_TIME,
    )
    downgrade = stopping_sight_distance(
        speed=DESIGN_SPEED,
        deceleration=DECELERATION,
        reaction_time=REACTION_TIME,
        grade=DOWNGRADE,
    )
    return {
        "level_m": level.to("m").magnitude,
        "downgrade_m": downgrade.to("m").magnitude,
        "extra_m": downgrade.to("m").magnitude - level.to("m").magnitude,
    }


def main() -> None:
    s = sight_distance_by_grade()
    print(f"level road   : {s['level_m']:.0f} m stopping sight distance")
    print(
        f"4% downgrade : {s['downgrade_m']:.0f} m  (+{s['extra_m']:.0f} m: gravity fights brakes)"
    )
    print("  -> the downgrade governs; sizing sight distance on the level under-builds the curve")


if __name__ == "__main__":
    main()
