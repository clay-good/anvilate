"""Worked example: the sheave overhang a tip-point screen silently drops.

A davit boom — a 1.2 m cantilevered 60 x 100 x 5 mm A36 box — hoists 4 kN
through a sheave bracket that sticks out 300 mm past the boom tip. The lazy
screen puts the hoist load at the tip: SF 2.04 against yield and a 5.87 mm tip
deflection inside L/180 = 6.67 mm, both PASS at the rigging factor of 2.0. But
the bracket hands the boom the load AND the couple F·e its overhang creates
(``cantilever_end_moment``): the wall moment grows by e/L = 25% (F·(L+e), SF
1.64) and the couple adds M·L²/2EI = 2.20 mm of tip deflection (8.07 mm total)
— both screens flip to FAIL. Because a tip force and a tip couple both peak
their stress at the wall and their deflection at the tip, superposing the two
closed forms is exact, not an estimate.

Run it directly (``python examples/davit_sheave_overhang.py``);
:func:`screen_davit_boom` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    cantilever_end_load,
    cantilever_end_moment,
    deflection_scorecard,
    strength_scorecard,
)
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

HOIST_LOAD = Quantity.parse("4 kN")
BOOM_LENGTH = Quantity.parse("1.2 m")
SHEAVE_OVERHANG = Quantity.parse("300 mm")  # the bracket carries the sheave past the tip
DEFLECTION_LIMIT = Quantity(magnitude=1200 / 180, unit="mm")  # L/180 for a cantilever tip
REQUIRED_SF = 2.0  # rigging service
MATERIAL = "ASTM-A36"


def _section() -> CrossSection:
    return CrossSection.hollow_rectangular(
        width=Quantity.parse("60 mm"),
        height=Quantity.parse("100 mm"),
        wall_thickness=Quantity.parse("5 mm"),
    )


def screen_davit_boom() -> Scorecard:
    """Screen the boom with the hoist load at the tip, then with the true overhang."""
    naive = screen_beam_member(
        BeamMember(
            name="boom (load at tip)",
            section=_section(),
            length=BOOM_LENGTH,
            support=Support.CANTILEVER,
            load=HOIST_LOAD,
            load_type=LoadType.POINT,
            material=MATERIAL,
            deflection_limit=DEFLECTION_LIMIT,
        ),
        required_safety_factor=REQUIRED_SF,
    )

    record = default_materials_db().get(MATERIAL)
    common = {
        "length": BOOM_LENGTH,
        "second_moment": _section().second_moment,
        "extreme_fibre": _section().extreme_fibre,
        "elastic_modulus": record.elastic_modulus.quantity,
    }
    tip = cantilever_end_load(force=HOIST_LOAD, **common)
    overhang_couple = Quantity(
        magnitude=HOIST_LOAD.to("N").magnitude * SHEAVE_OVERHANG.to("mm").magnitude,
        unit="N*mm",
    )
    couple = cantilever_end_moment(moment=overhang_couple, **common)
    # A tip force and a tip couple both peak their stress at the wall and their
    # deflection at the tip, so superposing the two maxima is exact.
    stress = Quantity(
        magnitude=tip.max_bending_stress.to("MPa").magnitude
        + couple.max_bending_stress.to("MPa").magnitude,
        unit="MPa",
    )
    deflection = Quantity(
        magnitude=tip.max_deflection.to("mm").magnitude + couple.max_deflection.to("mm").magnitude,
        unit="mm",
    )
    true_entries = (
        strength_scorecard(
            "boom (sheave overhang) bending",
            stress=stress,
            allowable=record.yield_strength.quantity,
            required=REQUIRED_SF,
        ),
        deflection_scorecard(
            "boom (sheave overhang) deflection",
            deflection=deflection,
            limit=DEFLECTION_LIMIT,
        ),
    )
    return Scorecard(entries=naive.entries + true_entries)


def main() -> None:
    card = screen_davit_boom()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
