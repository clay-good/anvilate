"""Worked example: a hole is not a relief — declare it.

The Ø400 gasketed hydro-test blind from ``test_blind_sizing.py`` passed at
16 mm (SF 2.15, 0.82 mm of bow against the 1 mm gasket limit). Then someone
adds a Ø80 sight port on centre. Intuition says the port sheds its share of
the 6 bar pressure; the annular closed form says the free hole edge
concentrates hoop bending instead — the governing stress grows 1.77× and the
"passing" blind FAILs strength at SF 1.22, with the bow at 0.95 mm eating the
flatness margin too. One `CoverPlate` field (``hole_diameter``) is the
difference between screening the plate that was drawn and the one that gets
drilled. At 20 mm the ported blind clears both screens again (SF 1.90,
0.49 mm). The concentration does not fade with hole size: shrinking the port
toward zero still leaves 2× the solid plate's stress at its edge.

Run it directly (``python examples/sight_port_blind.py``);
:func:`screen_sight_port_blind` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.industrial import CoverPlate, screen_cover_plate
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

PRESSURE = Quantity.parse("0.6 MPa")  # 6 bar hydro test
DIAMETER = Quantity.parse("400 mm")
PORT = Quantity.parse("80 mm")
FLATNESS_LIMIT = Quantity.parse("1 mm")  # gasket sealing limit
REQUIRED_SF = 1.5

_CASES = (
    ("16 mm solid blind", "16 mm", None),
    ("16 mm blind with port", "16 mm", PORT),
    ("20 mm blind with port", "20 mm", PORT),
)


def screen_sight_port_blind() -> Scorecard:
    """Screen the blind solid and ported, as one card."""
    entries = []
    for name, thickness, hole in _CASES:
        card = screen_cover_plate(
            CoverPlate(
                name=name,
                pressure=PRESSURE,
                thickness=Quantity.parse(thickness),
                material="ASTM-A36",
                diameter=DIAMETER,  # gasketed rim -> simply supported default
                hole_diameter=hole,
                deflection_limit=FLATNESS_LIMIT,
            ),
            required_safety_factor=REQUIRED_SF,
        )
        entries.extend(card.entries)
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_sight_port_blind()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
