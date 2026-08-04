"""Worked example: a deep welded plate girder — the two things a slender web does.

A plate girder is a beam built up so deep and thin-webbed that it behaves unlike any
rolled shape, and AISC 360 §F5 / §G2.2 capture the two effects that define it. This
girder is a 1500x8 mm web with 300x20 mm flanges (A992, F_y = 345 MPa):

  * In bending, the slender web cannot hold its share of stress and sheds it to the
    flanges, so §F5 debits the moment by R_pg = 0.944 — a 5.6% penalty a rolled-shape
    calc never applies (M_n = R_pg*F_cr*S_x = 3884 kN*m vs 4114 without it).
  * In shear, once transverse stiffeners are added the buckled web carries diagonal
    tension like a truss, and §G2.2 tension-field action nearly doubles the shear
    capacity over the same web unstiffened (1468 kN vs 832 kN).

The example composes the three plate-girder closed-forms — the bending reduction
factor, the compression-flange local-buckling stress, and the tension-field shear —
with the verified I-section second moment.

Run it directly (``python examples/plate_girder_design.py``);
:func:`girder_capacities` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    aisc_plate_girder_bending_factor,
    aisc_plate_girder_flange_stress,
    aisc_tension_field_shear_strength,
    aisc_web_shear_strength,
    i_section_second_moment,
)
from anvilate.units import Quantity

WEB_DEPTH = Quantity.parse("1500 mm")
WEB_THICKNESS = Quantity.parse("8 mm")
FLANGE_WIDTH = Quantity.parse("300 mm")
FLANGE_THICKNESS = Quantity.parse("20 mm")
TOTAL_HEIGHT = Quantity.parse("1540 mm")  # web + two flanges
STIFFENER_SPACING = Quantity.parse("2250 mm")
YIELD = Quantity.parse("345 MPa")
MODULUS = Quantity.parse("200000 MPa")


def girder_capacities() -> dict[str, Quantity]:
    """Return the girder's bending strength and its stiffened / unstiffened shear."""
    second_moment = i_section_second_moment(
        flange_width=FLANGE_WIDTH,
        total_height=TOTAL_HEIGHT,
        flange_thickness=FLANGE_THICKNESS,
        web_thickness=WEB_THICKNESS,
    )
    section_modulus = 2 * second_moment.to("mm**4").magnitude / TOTAL_HEIGHT.to("mm").magnitude

    r_pg = aisc_plate_girder_bending_factor(
        web_clear_depth=WEB_DEPTH,
        web_thickness=WEB_THICKNESS,
        compression_flange_width=FLANGE_WIDTH,
        compression_flange_thickness=FLANGE_THICKNESS,
        yield_strength=YIELD,
        elastic_modulus=MODULUS,
    )
    f_cr = aisc_plate_girder_flange_stress(
        flange_width=FLANGE_WIDTH,
        flange_thickness=FLANGE_THICKNESS,
        web_depth=WEB_DEPTH,
        web_thickness=WEB_THICKNESS,
        yield_strength=YIELD,
        elastic_modulus=MODULUS,
    )
    moment = Quantity(
        magnitude=r_pg * f_cr.to("MPa").magnitude * section_modulus / 1.0e6, unit="kN*m"
    )

    web_area = Quantity(
        magnitude=TOTAL_HEIGHT.to("mm").magnitude * WEB_THICKNESS.to("mm").magnitude,
        unit="mm**2",
    )
    stiffened_shear = aisc_tension_field_shear_strength(
        web_area=web_area,
        web_depth=WEB_DEPTH,
        web_thickness=WEB_THICKNESS,
        stiffener_spacing=STIFFENER_SPACING,
        yield_strength=YIELD,
        elastic_modulus=MODULUS,
    )
    unstiffened_shear = aisc_web_shear_strength(
        overall_depth=TOTAL_HEIGHT,
        web_thickness=WEB_THICKNESS,
        clear_web_depth=WEB_DEPTH,
        web_yield=YIELD,
        elastic_modulus=MODULUS,
    )
    return {
        "bending_reduction": Quantity(magnitude=r_pg, unit="dimensionless"),
        "moment": moment,
        "stiffened_shear": stiffened_shear,
        "unstiffened_shear": unstiffened_shear,
    }


def main() -> None:
    caps = girder_capacities()
    r_pg = caps["bending_reduction"].magnitude
    print(f"R_pg bending reduction   : {r_pg:.3f}  ({100 * (1 - r_pg):.1f}% penalty)")
    print(f"M_n flexural strength    : {caps['moment'].to('kN*m').magnitude:.0f} kN*m")
    vs = caps["stiffened_shear"].to("kN").magnitude
    vu = caps["unstiffened_shear"].to("kN").magnitude
    print(f"V_n shear, stiffened     : {vs:.0f} kN  (tension-field action)")
    print(f"V_n shear, unstiffened   : {vu:.0f} kN  ({vs / vu:.1f}x from stiffening)")


if __name__ == "__main__":
    main()
