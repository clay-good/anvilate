"""Worked example: a rectangular HSS beam where a naive plastic moment overstates capacity.

A square HSS 300x300x9 (ASTM A992, F_y = 345 MPa) has a wide, relatively thin wall:
its flange slenderness b/t = 30.3 lands in the noncompact range (between AISC's
lambda_pf = 27.0 and lambda_rf = 33.7). A hand check that stops at the plastic moment
M_p = F_y*Z reads 394.5 kN*m — but the compression flange buckles locally before the
section fully plastifies, and AISC 360-16 §F7 knocks the flexural strength down to
367.6 kN*m, 7% lower. Section properties come from the verified tube helpers; the two
new AISC strengths (§F7 flexure, §G5 shear) then screen the same section, and shear is
shown to carry a large margin, as it does for nearly every compact-to-noncompact HSS.

Run it directly (``python examples/hss_beam_flexure_shear.py``);
:func:`hss_beam_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    aisc_rectangular_hss_flexural_strength,
    aisc_rectangular_hss_shear_strength,
    rectangular_tube_plastic_section_modulus,
    rectangular_tube_second_moment,
)
from anvilate.units import Quantity

OUTER = Quantity.parse("300 mm")  # square HSS outer dimension
WALL = Quantity.parse("9 mm")
YIELD = Quantity.parse("345 MPa")
MODULUS = Quantity.parse("200000 MPa")


def hss_beam_capacity() -> dict[str, Quantity]:
    """Return the naive plastic moment, the §F7 flexural strength, and the §G5 shear."""
    outer_mm = OUTER.to("mm").magnitude
    wall_mm = WALL.to("mm").magnitude
    flat = Quantity.parse(f"{outer_mm - 3 * wall_mm} mm")  # flat wall width, less corners

    second_moment = rectangular_tube_second_moment(width=OUTER, height=OUTER, wall_thickness=WALL)
    plastic_modulus = rectangular_tube_plastic_section_modulus(
        width=OUTER, height=OUTER, wall_thickness=WALL
    )
    elastic_modulus = Quantity(
        magnitude=2 * second_moment.to("mm**4").magnitude / outer_mm, unit="mm**3"
    )

    plastic_moment = Quantity(
        magnitude=YIELD.to("MPa").magnitude * plastic_modulus.to("mm**3").magnitude / 1.0e6,
        unit="kN*m",
    )
    flexural_strength = aisc_rectangular_hss_flexural_strength(
        flange_flat_width=flat,
        web_flat_height=flat,
        wall_thickness=WALL,
        yield_strength=YIELD,
        elastic_modulus=MODULUS,
        plastic_section_modulus=plastic_modulus,
        elastic_section_modulus=elastic_modulus,
    )
    shear_strength = aisc_rectangular_hss_shear_strength(
        web_height=flat,
        thickness=WALL,
        yield_strength=YIELD,
        elastic_modulus=MODULUS,
    )
    return {
        "plastic_moment": plastic_moment,
        "flexural_strength": flexural_strength,
        "shear_strength": shear_strength,
    }


def main() -> None:
    result = hss_beam_capacity()
    m_p = result["plastic_moment"].to("kN*m").magnitude
    m_n = result["flexural_strength"].to("kN*m").magnitude
    v_n = result["shear_strength"].to("kN").magnitude
    print(f"naive plastic moment F_y*Z: {m_p:.1f} kN*m")
    print(f"AISC F7 flexural strength : {m_n:.1f} kN*m  ({100 * (1 - m_n / m_p):.0f}% lower)")
    print(f"AISC G5 shear strength    : {v_n:.0f} kN")


if __name__ == "__main__":
    main()
