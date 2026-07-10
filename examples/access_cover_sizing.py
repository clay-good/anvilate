"""Worked example: on flat covers, stiffness governs before strength.

A 600 x 400 mm simply-supported A36 access cover holds back 50 kPa (a 5 m
water column). Sized for strength alone, 6 mm plate looks right: the exact
Navier plate solution puts the surface stress at 108 MPa — SF 2.31 against
yield, PASS at 2.0. But the same 6 mm cover bows 2.5 mm at the centre, past a
b/250 = 1.6 mm flatness limit (and approaching the w ≈ t/2 edge of thin-plate
validity, where the screen stops being trustworthy). Going to 8 mm fixes it —
stress falls with t² (SF 4.11) but deflection with t³ (1.05 mm, PASS): the
cube-law lever is why plate sizing lands on stiffness, and why the
strength-sized cover is a whole gauge too thin.

Run it directly (``python examples/access_cover_sizing.py``);
:func:`screen_access_cover` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    deflection_scorecard,
    simply_supported_plate_uniform_load,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

PRESSURE = Quantity.parse("50 kPa")  # ~5 m of water on the cover
LENGTH = Quantity.parse("600 mm")
WIDTH = Quantity.parse("400 mm")
DEFLECTION_LIMIT = Quantity(magnitude=400 / 250, unit="mm")  # b/250 flatness
REQUIRED_SF = 2.0

_THICKNESSES = ("6 mm", "8 mm")


def screen_access_cover() -> Scorecard:
    """Screen the cover at both plate thicknesses, as one card."""
    record = default_materials_db().get("ASTM-A36")
    entries = []
    for thickness in _THICKNESSES:
        result = simply_supported_plate_uniform_load(
            pressure=PRESSURE,
            length=LENGTH,
            width=WIDTH,
            thickness=Quantity.parse(thickness),
            elastic_modulus=record.elastic_modulus.quantity,
        )
        entries.append(
            strength_scorecard(
                f"{thickness} cover bending",
                stress=result.max_bending_stress,
                allowable=record.yield_strength.quantity,
                required=REQUIRED_SF,
            )
        )
        entries.append(
            deflection_scorecard(
                f"{thickness} cover flatness",
                deflection=result.max_deflection,
                limit=DEFLECTION_LIMIT,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_access_cover()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
