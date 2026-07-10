"""Worked example: a hydrostatic load screened as the triangle it actually is.

Declares a vertical stiffener on a 2.5 m flood barrier — water to the top,
stiffeners at 600 mm centers, an 80 x 120 x 5 mm A36 box tube pinned at the sill
and the top waler — and screens it twice. Water pressure grows linearly with
depth, peaking at ρ·g·h = 24.5 kPa at the sill, so the stiffener's true load is
a triangle (zero at the waterline, w₀ = 14.7 N/mm at the bottom). The lazy
conservative screen smears that peak over the whole span as a uniform load and
nearly doubles the demand: M = w₀·L²/8 gives 183 MPa (SF 1.36, FAIL at 1.5) and
9.95 mm of deflection (FAIL against L/360 = 6.94 mm). Declaring the actual
hydrostatic triangle — M = w₀·L²/(9·√3) — drops the peak stress to 94 MPa
(SF 2.66) and the deflection to 4.99 mm: the same stiffener passes everything.

Run it directly (``python examples/flood_barrier_stiffener.py``);
:func:`screen_flood_barrier_stiffener` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    deflection_scorecard,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

# 2.5 m of water head at 600 mm stiffener spacing: 24.5 kPa * 0.6 m.
PEAK_LOAD = Quantity.parse("14.7 N/mm")
SPAN = Quantity.parse("2.5 m")
DEFLECTION_LIMIT = Quantity(magnitude=2500 / 360, unit="mm")  # L/360
REQUIRED_SF = 1.5


def screen_flood_barrier_stiffener() -> Scorecard:
    """Screen the stiffener under both load idealizations, returning one card."""
    section = CrossSection.hollow_rectangular(
        width=Quantity.parse("80 mm"),
        height=Quantity.parse("120 mm"),
        wall_thickness=Quantity.parse("5 mm"),
    )
    yield_strength = default_materials_db().get("ASTM-A36").yield_strength.quantity
    common = {
        "length": SPAN,
        "second_moment": section.second_moment,
        "extreme_fibre": section.extreme_fibre,
        "elastic_modulus": Quantity.parse("200 GPa"),
    }
    smeared = simply_supported_uniform_load(distributed_load=PEAK_LOAD, **common)
    actual = simply_supported_triangular_load(peak_distributed_load=PEAK_LOAD, **common)

    entries = []
    for label, result in (
        ("peak smeared as UDL", smeared),
        ("actual hydrostatic triangle", actual),
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
    card = screen_flood_barrier_stiffener()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
