"""Worked example: the indexing table that ran out of dwell.

A Geneva-driven rotary assembly table advances one station every 3 seconds and
must hold each station still long enough — 1.9 seconds — for a robot to place a
part. The temptation is to pack in more stations: more stations means more
operations per revolution, more throughput. But a Geneva wheel spends a fixed
share of each step *moving*, and every slot you add steals from the dwell.

The dwell fraction of an external Geneva is (n + 2)/(2n), so it shrinks as the
slot count climbs. A 6-station table dwells 66.7% of the 3 s step — 2.0 s, just
enough for the 1.9 s placement (1.05). An 8-station table dwells only 62.5%,
1.875 s, and the robot no longer finishes before the table lurches on (0.99). A
12-station table is worse still at 1.75 s (0.92): the part is placed into a moving
fixture.

Station count and dwell time pull against each other on a fixed cycle. You cannot
have both a fine index and a long dwell from the same Geneva at the same speed —
past 6 stations here the operation no longer fits, and the fix is fewer stations,
a slower cycle, or a faster robot, not more slots. The cycle time and operation
time are process data, declared inline like any allowable.

Run it directly (``python examples/indexing_table_stations.py``);
:func:`screen_indexing_table` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import geneva_dwell_fraction
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

CYCLE_TIME = Quantity.parse("3 s")
OPERATION_TIME = Quantity.parse("1.9 s")

STATION_COUNTS = {
    "6 stations": 6,
    "8 stations": 8,
    "12 stations": 12,
}


def dwell_time(slots: int) -> float:
    """The seconds a station is held still per index step for a given slot count."""
    return geneva_dwell_fraction(slots=slots) * CYCLE_TIME.to("s").magnitude


def screen_indexing_table() -> Scorecard:
    """Screen each station count: the dwell must cover the operation time
    (safety factor = dwell time / operation time)."""
    operation = OPERATION_TIME.to("s").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            name, computed=dwell_time(slots) / operation, required=1.0
        )
        for name, slots in STATION_COUNTS.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, slots in STATION_COUNTS.items():
        print(f"{name}: dwell {dwell_time(slots):.3f} s per station")
    print(screen_indexing_table())


if __name__ == "__main__":
    main()
