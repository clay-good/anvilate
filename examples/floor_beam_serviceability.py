"""Worked example: strong enough, still too bouncy.

An office floor beam spans 6 m and carries about 4.5 kN/m (a ~2.25 kPa live load
on a 2 m bay). As a 200 mm-deep I-section it is comfortably strong: the mid-span
bending stress is ~97 MPa against a 165 MPa allowable, a 1.7 safety factor. Yet
the beam still fails, because floors are governed by stiffness, not strength. At
L/360 — the classic limit that keeps plaster from cracking and floors from
feeling lively — the allowable mid-span sag is 6000/360 = 16.7 mm, and this beam
deflects about 18 mm. It would not break, but it would bounce, and the plaster
ceiling below it would craze. Sizing a floor beam on bending stress alone misses
the check that actually governs it; the fix is a deeper (stiffer) section, not a
stronger one.

Run it directly (``python examples/floor_beam_serviceability.py``);
:func:`screen_floor_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    deflection_scorecard,
    simply_supported_uniform_load,
    span_deflection_limit,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SPAN = Quantity.parse("6 m")
LOAD = Quantity.parse("4.5 kN/m")  # ~2.25 kPa live load on a 2 m bay
ELASTIC_MODULUS = Quantity.parse("200 GPa")
ALLOWABLE_STRESS = Quantity.parse("165 MPa")
REQUIRED_SF = 1.5
DEFLECTION_RATIO = 360  # L/360: brittle-finish / live-load serviceability limit

SECTION = CrossSection.i_section(
    depth=Quantity.parse("200 mm"),
    flange_width=Quantity.parse("100 mm"),
    flange_thickness=Quantity.parse("10 mm"),
    web_thickness=Quantity.parse("6 mm"),
)


def screen_floor_beam() -> Scorecard:
    """Screen the floor beam on both bending strength and the L/360 deflection
    limit; strength passes but serviceability governs."""
    result = simply_supported_uniform_load(
        distributed_load=LOAD,
        length=SPAN,
        second_moment=SECTION.second_moment,
        extreme_fibre=SECTION.extreme_fibre,
        elastic_modulus=ELASTIC_MODULUS,
    )
    return Scorecard(
        entries=(
            strength_scorecard(
                "mid-span bending",
                stress=result.max_bending_stress,
                allowable=ALLOWABLE_STRESS,
                required=REQUIRED_SF,
            ),
            deflection_scorecard(
                "mid-span deflection (L/360)",
                deflection=result.max_deflection,
                limit=span_deflection_limit(span=SPAN, ratio=DEFLECTION_RATIO),
            ),
        )
    )


def main() -> None:
    card = screen_floor_beam()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
