"""Worked example: a genset's two skid rails vs its lumped resultant.

Declares a 10 kN generator set crossing a 3 m simply-supported A36 floor beam
(a 60 x 110 x 4 mm box) and screens it both ways. Lumping the machine into one
10 kN resultant at mid-span gives M = P·L/4 = 7.5e6 N·mm — SF 1.25, FAIL at
1.5, with 13.677 mm of deflection past the L/240 = 12.5 mm platform limit. But
the genset actually stands on two skid rails 1 m apart, centered — 5 kN at
each third point — and four-point bending carries a constant M = F·a = 5e6
N·mm between the rails, exactly 2/3 of the lumped moment: SF 1.87 and
11.650 mm, PASS on both counts. Same machine, same total weight; declaring the
two rails (``simply_supported_symmetric_point_loads``) recovers the margin the
lumped screen throws away.

Run it directly (``python examples/genset_on_two_rails.py``);
:func:`screen_genset_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    deflection_scorecard,
    simply_supported_center_load,
    simply_supported_symmetric_point_loads,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

GENSET_WEIGHT = Quantity.parse("10 kN")
RAIL_LOAD = Quantity.parse("5 kN")  # half the genset on each rail
RAIL_OFFSET = Quantity.parse("1 m")  # rails 1 m apart, centered on the 3 m span
SPAN = Quantity.parse("3 m")
DEFLECTION_LIMIT = Quantity(magnitude=3000 / 240, unit="mm")  # L/240 platform limit
REQUIRED_SF = 1.5


def screen_genset_beam() -> Scorecard:
    """Screen the floor beam under both machine idealizations, as one card."""
    section = CrossSection.hollow_rectangular(
        width=Quantity.parse("60 mm"),
        height=Quantity.parse("110 mm"),
        wall_thickness=Quantity.parse("4 mm"),
    )
    yield_strength = default_materials_db().get("ASTM-A36").yield_strength.quantity
    common = {
        "length": SPAN,
        "second_moment": section.second_moment,
        "extreme_fibre": section.extreme_fibre,
        "elastic_modulus": Quantity.parse("200 GPa"),
    }
    lumped = simply_supported_center_load(force=GENSET_WEIGHT, **common)
    rails = simply_supported_symmetric_point_loads(
        force=RAIL_LOAD, load_offset=RAIL_OFFSET, **common
    )

    entries = []
    for label, result in (
        ("lumped mid-span resultant", lumped),
        ("declared skid rails", rails),
    ):
        entries.append(
            strength_scorecard(
                f"{label} bending",
                stress=result.max_bending_stress,
                allowable=yield_strength,
                required=REQUIRED_SF,
            )
        )
        entries.append(
            deflection_scorecard(
                f"{label} deflection",
                deflection=result.max_deflection,
                limit=DEFLECTION_LIMIT,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_genset_beam()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
