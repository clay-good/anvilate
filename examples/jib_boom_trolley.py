"""Worked example: a hoist trolley on a jib-crane boom with a travel end stop.

Declares a 10 kN hoist on a 1 m A36 cantilever boom (50 x 80 mm rectangle) and
screens it twice: once the conservative way — pretending the trolley reaches
the free tip, the worst position — and once with the trolley's actual 750 mm
end stop declared as the ``load_position``. The instructive part: the at-tip
assumption fails the 1.5 requirement (M = P·L gives SF 1.33), but the end stop
caps the moment at 3/4 of that (M = P·a), so the boom actually passes at
SF 1.78. Declaring where the load can really travel recovers margin a
worst-case hand check would throw away — without touching the boom.

Run it directly (``python examples/jib_boom_trolley.py``);
:func:`screen_jib_boom` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

HOIST_LOAD = Quantity.parse("10 kN")
BOOM_LENGTH = Quantity.parse("1 m")
TROLLEY_END_STOP = Quantity.parse("750 mm")  # from the fixed end


def screen_jib_boom() -> Scorecard:
    """Screen the boom under both trolley-position assumptions, returning one card."""
    section = CrossSection.rectangular(
        width=Quantity.parse("50 mm"), height=Quantity.parse("80 mm")
    )
    common = {
        "section": section,
        "length": BOOM_LENGTH,
        "support": Support.CANTILEVER,
        "load": HOIST_LOAD,
        "load_type": LoadType.POINT,
        "material": "ASTM-A36",
    }
    assumed_at_tip = BeamMember(name="assumed at tip", **common)
    at_end_stop = BeamMember(name="at end stop", load_position=TROLLEY_END_STOP, **common)
    return screen_structure([assumed_at_tip, at_end_stop], required_safety_factor=1.5)


def main() -> None:
    card = screen_jib_boom()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
