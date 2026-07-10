"""Worked example: the static scorecard can't hear the blower.

A 600 x 400 x 5 mm A36 access panel sits in the wall of a supply-air plenum
holding 5 kPa of static pressure, one duct run from a blower whose blade-pass
sits at 100 Hz (a 1.2 margin puts the panel's floor at 120 Hz). Statically the
panel is not even close to working hard: clipped in place (simply supported)
it carries the pressure at SF 16.0 and bows 0.43 mm against a 1.6 mm (b/250)
flatness limit. But one :class:`CoverPlate` declaration with a
``min_frequency`` adds the screen the statics can't see — the clipped panel
rings at 108.3 Hz, inside the blade-pass band, and FAILs. Welding the rim
raises the fundamental 1.9x to 205.5 Hz (the clamped-square-family eigenvalue
jump) and the same panel passes everything. The mass came from the material's
density; the fix costs a weld bead, not a thicker plate.

Run it directly (``python examples/plenum_access_panel.py``);
:func:`screen_plenum_panel` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.industrial import CoverPlate, PlateEdge, screen_cover_plate
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

PRESSURE = Quantity.parse("5 kPa")  # plenum static pressure
LENGTH = Quantity.parse("600 mm")
WIDTH = Quantity.parse("400 mm")
THICKNESS = Quantity.parse("5 mm")
FLATNESS_LIMIT = Quantity.parse("1.6 mm")  # b/250
MIN_FREQUENCY = Quantity.parse("120 Hz")  # 100 Hz blade-pass x 1.2 margin
REQUIRED_SF = 2.0

_EDGES = (
    ("clipped rim (simply supported)", PlateEdge.SIMPLY_SUPPORTED),
    ("welded rim (clamped)", PlateEdge.CLAMPED),
)


def screen_plenum_panel() -> Scorecard:
    """Screen the panel under both rim conditions, as one card."""
    entries = []
    for name, edge in _EDGES:
        card = screen_cover_plate(
            CoverPlate(
                name=name,
                pressure=PRESSURE,
                thickness=THICKNESS,
                material="ASTM-A36",
                edge=edge,
                length=LENGTH,
                width=WIDTH,
                deflection_limit=FLATNESS_LIMIT,
                min_frequency=MIN_FREQUENCY,
            ),
            required_safety_factor=REQUIRED_SF,
        )
        entries.extend(card.entries)
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_plenum_panel()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
