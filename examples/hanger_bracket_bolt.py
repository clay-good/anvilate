"""Worked example: a hanger-bracket bolt under combined tension and shear.

Declares a single M12 bolt (annealed 4140) holding an equipment bracket to a
column flange through an 8 mm A36 plate. Gravity puts 10 kN of direct shear on
the bolt; the bracket's moment arm and prying add an 18 kN axial tension. The
instructive part: every one-axis check clears the required factor of 2.0 —
bolt shear (SF 2.7), plate bearing (SF 2.4), bolt tension (SF 2.6) — yet the
AISC §J3.7 combined tension-plus-shear interaction (von Mises) fails at SF 1.9.
A one-axis-at-a-time hand check would have shipped an under-sized bolt.

Run it directly (``python examples/hanger_bracket_bolt.py``);
:func:`screen_hanger_bolt` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.structural import BoltedConnection, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SHEAR_LOAD = Quantity.parse("10 kN")  # gravity, carried in single shear
TENSION_LOAD = Quantity.parse("18 kN")  # bracket moment arm + prying


def screen_hanger_bolt() -> Scorecard:
    """Declare and screen the bracket bolt, returning the scorecard."""
    bolt = BoltedConnection(
        name="bracket",
        bolt_diameter=Quantity.parse("12 mm"),
        plate_thickness=Quantity.parse("8 mm"),
        load=SHEAR_LOAD,
        bolt_material="AISI-4140",
        plate_material="ASTM-A36",
        tension=TENSION_LOAD,
    )
    return screen_structure([bolt], required_safety_factor=2.0)


def main() -> None:
    card = screen_hanger_bolt()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
