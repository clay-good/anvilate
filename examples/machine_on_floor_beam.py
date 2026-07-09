"""Worked example: a machine sitting off mid-span of a simply-supported floor beam.

Declares a 15 kN machine at the quarter point of a 3 m A36 floor beam (50 x 80 mm
rectangle) and screens it twice: once the conservative way — pretending the load
sits at mid-span, the worst position — and once with the actual ``load_position``
declared. The instructive part: the mid-span assumption fails the 1.5 requirement
(M = P·L/4 gives SF 1.19), but the real quarter-point moment is only 3/4 of that
(M = P·a·b/L), so the beam actually passes at SF 1.58. Declaring where the load
really sits recovers margin a worst-case hand check would throw away — without
touching the beam.

Run it directly (``python examples/machine_on_floor_beam.py``);
:func:`screen_floor_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

MACHINE_WEIGHT = Quantity.parse("15 kN")
SPAN = Quantity.parse("3 m")
MACHINE_POSITION = Quantity.parse("750 mm")  # quarter point


def screen_floor_beam() -> Scorecard:
    """Screen the beam under both load-position assumptions, returning one card."""
    section = CrossSection.rectangular(
        width=Quantity.parse("50 mm"), height=Quantity.parse("80 mm")
    )
    common = {
        "section": section,
        "length": SPAN,
        "support": Support.SIMPLY_SUPPORTED,
        "load": MACHINE_WEIGHT,
        "load_type": LoadType.POINT,
        "material": "ASTM-A36",
    }
    assumed_mid_span = BeamMember(name="assumed mid-span", **common)
    actual_position = BeamMember(name="actual position", load_position=MACHINE_POSITION, **common)
    return screen_structure([assumed_mid_span, actual_position], required_safety_factor=1.5)


def main() -> None:
    card = screen_floor_beam()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
