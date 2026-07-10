"""Worked example: a load parked at one end, and two shortcuts that both miss.

Declares a 4 m A36 floor beam (80 x 120 x 5 mm box) carrying palletized stock
over only the first 2 m of its span — 6 N/mm on the loaded half, nothing beyond
— and screens it three ways. Smearing the patch *intensity* over the whole span
(the conservative habit) triples the true moment (w·L²/8 = 12 kN·m vs the
patch's R₁²/2w = 6.75 kN·m) and FAILS the beam at SF 1.30. Spreading the patch
*total* over the span (w/2 everywhere) looks more reasonable but errs the other
way: it reports SF 2.61 where the true patch gives 2.32 — an 11% margin that
isn't there, because half the span carries the full intensity. Declaring the
actual ``loaded_length`` on the member gets the AISC Table 3-23 case 24 answer:
the beam PASSES at SF 2.32, with no borrowed margin.

Run it directly (``python examples/pallet_bay_floor_beam.py``);
:func:`screen_pallet_bay` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    simply_supported_uniform_load,
    strength_scorecard,
)
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

PATCH_LOAD = Quantity.parse("6 N/mm")  # pallet stock over the loaded bay
PATCH_LENGTH = Quantity.parse("2 m")  # parked against the left support
SPAN = Quantity.parse("4 m")
REQUIRED_SF = 1.67
MATERIAL = "ASTM-A36"


def screen_pallet_bay() -> Scorecard:
    """Screen the beam as declared and under both lazy idealizations."""
    section = CrossSection.hollow_rectangular(
        width=Quantity.parse("80 mm"),
        height=Quantity.parse("120 mm"),
        wall_thickness=Quantity.parse("5 mm"),
    )
    beam = BeamMember(
        name="declared half-span patch",
        section=section,
        length=SPAN,
        support=Support.SIMPLY_SUPPORTED,
        load=PATCH_LOAD,
        load_type=LoadType.DISTRIBUTED,
        material=MATERIAL,
        loaded_length=PATCH_LENGTH,
    )
    card = screen_beam_member(beam, required_safety_factor=REQUIRED_SF)

    record = default_materials_db().get(MATERIAL)
    common = {
        "length": SPAN,
        "second_moment": section.second_moment,
        "extreme_fibre": section.extreme_fibre,
        "elastic_modulus": record.elastic_modulus.quantity,
    }
    # Shortcut 1: the patch intensity smeared over the whole span (conservative).
    smeared = simply_supported_uniform_load(distributed_load=PATCH_LOAD, **common)
    # Shortcut 2: the patch total spread over the whole span (unconservative).
    spread = simply_supported_uniform_load(
        distributed_load=Quantity.parse("3 N/mm"),  # PATCH_LOAD * 2 m / 4 m
        **common,
    )
    entries = list(card.entries)
    for label, result in (
        ("intensity smeared over the span", smeared),
        ("total spread over the span", spread),
    ):
        entries.append(
            strength_scorecard(
                f"{label} bending",
                stress=result.max_bending_stress,
                allowable=record.yield_strength.quantity,
                required=REQUIRED_SF,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_pallet_bay()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
