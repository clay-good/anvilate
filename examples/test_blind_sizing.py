"""Worked example: sizing a hydro-test blind with the industrial pack.

A Ø400 mm gasketed blind flange blanks a nozzle for a 6 bar hydro test. On a
gasket the rim is honestly SIMPLY SUPPORTED, so the blind is declared that way
(:class:`CoverPlate` with a ``diameter``) and screened straight from the
materials DB. At 12 mm the A36 plate carries 206 MPa (SF 1.21, FAIL at 1.5)
and bows 1.93 mm — past the 1 mm the gasket can seal across. One size up at
16 mm the t² and t³ levers do their work: 116 MPa (SF 2.15) and 0.81 mm, both
PASS. Each entry cites the plate theory it ran; the pack keeps the
declaration honest (a clamped claim would need a weld, not a gasket).

Run it directly (``python examples/test_blind_sizing.py``);
:func:`screen_test_blind` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.industrial import CoverPlate, PlateEdge, screen_cover_plate
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

PRESSURE = Quantity.parse("0.6 MPa")  # 6 bar hydro test
DIAMETER = Quantity.parse("400 mm")
FLATNESS_LIMIT = Quantity.parse("1 mm")  # gasket sealing limit
REQUIRED_SF = 1.5

_THICKNESSES = ("12 mm", "16 mm")


def screen_test_blind() -> Scorecard:
    """Screen the blind at both plate thicknesses, as one card."""
    entries = []
    for thickness in _THICKNESSES:
        card = screen_cover_plate(
            CoverPlate(
                name=f"{thickness} blind",
                pressure=PRESSURE,
                thickness=Quantity.parse(thickness),
                material="ASTM-A36",
                edge=PlateEdge.SIMPLY_SUPPORTED,  # a gasketed rim cannot clamp
                diameter=DIAMETER,
                deflection_limit=FLATNESS_LIMIT,
            ),
            required_safety_factor=REQUIRED_SF,
        )
        entries.extend(card.entries)
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_test_blind()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
