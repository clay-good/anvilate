"""Worked example: a sealed housing whose focus adjustment cannot be reached once it is closed.

A lens cell goes into a housing, and a cover seals it. The lens is focused last, after the
cover is on, because the seal changes the cell's seating. The focus screw is reached through
the housing's top opening, and the cover is what closes that opening, so in the one state
the adjustment is made in, nothing can reach it. The card fails, naming the adjustment, the
state, the cover and the opening it occupies.

The revision adds a side port with a sealed plug, removed for focusing and refitted after.
The same adjustment, in the same closed state, routed through the port, passes: nothing
installed by then occupies it.

Run it directly (``python examples/sealed_housing_adjustment.py``); :func:`card` and
:func:`repaired_card` are also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.assembly import (
    Adjustment,
    AssemblyState,
    InsertionDirection,
    Part,
    screen_adjustment_access,
)
from anvilate.scorecard import Scorecard

PARTS = (
    Part(name="housing", insertion=InsertionDirection.MINUS_Z, occupies=("housing bore",)),
    Part(
        name="lens cell",
        insertion=InsertionDirection.MINUS_Z,
        occupies=("cell seat",),
        sweeps=("housing bore",),
    ),
    Part(name="cover", insertion=InsertionDirection.MINUS_Z, occupies=("top opening",)),
)
STATES = (
    AssemblyState(name="open", installs=("housing", "lens cell")),
    AssemblyState(name="closed", installs=("cover",)),
)


def _card(route: str) -> Scorecard:
    focus = Adjustment(feature="focus screw", performed_in="closed", access=(route,))
    return Scorecard(entries=screen_adjustment_access(STATES, PARTS, [focus]))


def card() -> Scorecard:
    """As drawn: focused through the top opening, which the cover closes."""
    return _card("top opening")


def repaired_card() -> Scorecard:
    """Revised: focused through a sealed side port nothing installed occupies."""
    return _card("side port")


def main() -> None:
    for label, scorecard in (("as drawn", card()), ("revised", repaired_card())):
        print(f"{label}: {scorecard.status.value}")
        for entry in scorecard.entries:
            print(f"  {entry}")


if __name__ == "__main__":
    main()
