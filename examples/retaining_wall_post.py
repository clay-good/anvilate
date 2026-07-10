"""Worked example: a cantilever soil load, and a shortcut that lies about stiffness.

Declares a soldier post for a low retaining wall — 2 m of retained soil, posts at
1 m centers, a 100 mm deep A992 I-section (80 x 6 mm flanges, 4 mm web) fixed at
the footing and free at the top. Active soil pressure grows linearly with depth
(Ka·γ·h = 12 kPa at the base), so the post carries a triangular load peaking at
w₀ = 12 N/mm at the wall. The classic hand shortcut replaces the triangle with
its resultant (w₀·L/2 = 12 kN at the centroid, L/3 up from the footing): that
reproduces the fixed-end moment — and so the 170 MPa peak stress — *exactly*,
but under-predicts the tip deflection by 26% (w₀·L⁴/40.5·E·I vs the true
w₀·L⁴/30·E·I), reporting 10.1 mm against an L/180 = 11.1 mm limit. Screening
the declared triangular member catches what the shortcut misses: the true tip
deflection is 13.6 mm, and the post FAILS serviceability while passing strength
(SF 2.03).

Run it directly (``python examples/retaining_wall_post.py``);
:func:`screen_retaining_post` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    cantilever_offset_load,
    deflection_scorecard,
    strength_scorecard,
)
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

# Ka·γ·h·s = (1/3) · 18 kN/m³ · 2 m · 1 m of tributary width at the base.
PEAK_LOAD = Quantity.parse("12 N/mm")
HEIGHT = Quantity.parse("2 m")
DEFLECTION_LIMIT = Quantity(magnitude=2000 / 180, unit="mm")  # L/180 for a cantilever
REQUIRED_SF = 1.5
MATERIAL = "ASTM-A992"


def screen_retaining_post() -> Scorecard:
    """Screen the post as declared and via the resultant shortcut, on one card."""
    section = CrossSection.i_section(
        depth=Quantity.parse("100 mm"),
        flange_width=Quantity.parse("80 mm"),
        flange_thickness=Quantity.parse("6 mm"),
        web_thickness=Quantity.parse("4 mm"),
    )
    post = BeamMember(
        name="soldier post",
        section=section,
        length=HEIGHT,
        support=Support.CANTILEVER,
        load=PEAK_LOAD,
        load_type=LoadType.TRIANGULAR,
        material=MATERIAL,
        deflection_limit=DEFLECTION_LIMIT,
    )
    card = screen_beam_member(post, required_safety_factor=REQUIRED_SF)

    # The hand shortcut: the triangle's resultant w0*L/2 placed at its centroid,
    # L/3 up from the footing — exact on moment, 26% light on tip deflection.
    record = default_materials_db().get(MATERIAL)
    resultant = cantilever_offset_load(
        force=Quantity(magnitude=12.0, unit="kN"),  # PEAK_LOAD * HEIGHT / 2
        load_position=Quantity(magnitude=2000 / 3, unit="mm"),
        length=HEIGHT,
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=record.elastic_modulus.quantity,
    )
    entries = list(card.entries)
    entries.append(
        strength_scorecard(
            "resultant-at-centroid bending",
            stress=resultant.max_bending_stress,
            allowable=record.yield_strength.quantity,
            required=REQUIRED_SF,
        )
    )
    entries.append(
        deflection_scorecard(
            "resultant-at-centroid deflection",
            deflection=resultant.max_deflection,
            limit=DEFLECTION_LIMIT,
        )
    )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_retaining_post()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
