"""Worked example: the cheap sprocket that shook the conveyor.

A packaging conveyor runs its chain at 2.5 m/s and cannot tolerate more than 2%
speed ripple -- above that the polygon action of the driving sprocket jostles the
line and rattles the product. The temptation is a small driver: fewer teeth, less
cost, smaller footprint.

Chordal action punishes it. A chain rides the flats of a polygon, so its speed
swings by 1 - cos(pi/N) every tooth -- and that swing is brutal at low tooth
counts. The 11-tooth driver ripples 4.1% (a 0.49 margin against the 2% spec); even
13 teeth ripple 2.9% and fail. Only at 17 teeth does the ripple fall to 1.7% and
clear the spec with room to spare. The chain doesn't care that the small sprocket
was cheaper; the product on the belt does.

The layout confirms the choice: a 17/34 drive of #80 chain (25.4 mm pitch) at
575 mm centres wants about 71 pitches (round up to 72 even links), and the
17-tooth driver at 347 rpm runs the chain at 2.5 m/s within its ripple budget.

Run it directly (``python examples/conveyor_chain_drive.py``);
:func:`screen_conveyor_chain` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    chain_length_in_pitches,
    chain_speed,
    chordal_speed_variation,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

MAX_SPEED_RIPPLE = 0.02  # 2% smoothness spec
CHAIN_PITCH = Quantity.parse("25.4 mm")  # ANSI #80
DRIVEN_TEETH = 34
CENTER_DISTANCE = Quantity.parse("575 mm")
DRIVER_SPEED = Quantity.parse("347 rpm")

CANDIDATE_DRIVERS = {
    "11-tooth driver": 11,
    "13-tooth driver": 13,
    "17-tooth driver": 17,
}


def screen_conveyor_chain() -> Scorecard:
    """Screen each candidate driving sprocket for chordal smoothness against the
    2% ripple spec (safety factor = spec / actual ripple)."""
    entries = [
        ScorecardEntry.from_safety_factor(
            name,
            computed=MAX_SPEED_RIPPLE / chordal_speed_variation(sprocket_teeth=teeth),
            required=1.0,
        )
        for name, teeth in CANDIDATE_DRIVERS.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    teeth = CANDIDATE_DRIVERS["17-tooth driver"]
    speed = chain_speed(
        sprocket_teeth=teeth, chain_pitch=CHAIN_PITCH, rotational_speed=DRIVER_SPEED
    )
    pitches = chain_length_in_pitches(
        small_sprocket_teeth=teeth,
        large_sprocket_teeth=DRIVEN_TEETH,
        center_distance=CENTER_DISTANCE,
        chain_pitch=CHAIN_PITCH,
    )
    print(f"17-tooth driver: {speed.to('m/s').magnitude:.2f} m/s, {pitches:.1f} pitches")
    print(screen_conveyor_chain())


if __name__ == "__main__":
    main()
