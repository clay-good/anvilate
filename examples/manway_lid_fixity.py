"""Worked example: the edge-fixity assumption IS the lid design.

A Ø500 x 6 mm A36 manway blank holds 50 kPa. Modeled with its rim CLAMPED —
what a drawing note like "welded all around" delivers — the exact circular-
plate solution is comfortable: peak stress 65 MPa at the rim (SF 3.84) and
0.77 mm of bow, inside a 1.5 mm gasket-flatness limit. But a lid sitting on a
gasket under widely-spaced bolts cannot hold its edge slope: it behaves
SIMPLY SUPPORTED, and the same blank deflects (5+ν)/(1+ν) = 4.08× more
(3.15 mm, gasket FAIL — and past the w ≈ t/2 thin-plate validity edge) at
(3+ν)/2 = 1.65× the stress (107 MPa, SF 2.33, still passing). Nothing about
the plate changed — only how honestly the edge was modeled. If the bolting
can't clamp the rim, the flatness screen, not strength, sends this lid to
8 mm.

Run it directly (``python examples/manway_lid_fixity.py``);
:func:`screen_manway_lid` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    clamped_circular_plate_uniform_load,
    deflection_scorecard,
    simply_supported_circular_plate_uniform_load,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

PRESSURE = Quantity.parse("50 kPa")
DIAMETER = Quantity.parse("500 mm")
THICKNESS = Quantity.parse("6 mm")
FLATNESS_LIMIT = Quantity.parse("1.5 mm")  # gasket sealing limit
REQUIRED_SF = 2.0

_EDGES = (
    ("welded rim (clamped)", clamped_circular_plate_uniform_load),
    ("gasketed rim (simply supported)", simply_supported_circular_plate_uniform_load),
)


def screen_manway_lid() -> Scorecard:
    """Screen the lid under both honest edge models, as one card."""
    record = default_materials_db().get("ASTM-A36")
    entries = []
    for name, check in _EDGES:
        result = check(
            pressure=PRESSURE,
            diameter=DIAMETER,
            thickness=THICKNESS,
            elastic_modulus=record.elastic_modulus.quantity,
        )
        entries.append(
            strength_scorecard(
                f"{name} bending",
                stress=result.max_bending_stress,
                allowable=record.yield_strength.quantity,
                required=REQUIRED_SF,
            )
        )
        entries.append(
            deflection_scorecard(
                f"{name} flatness",
                deflection=result.max_deflection,
                limit=FLATNESS_LIMIT,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_manway_lid()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
