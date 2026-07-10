"""Tests for the CrossSection value object against hand-computed properties."""

from __future__ import annotations

import pytest

from anvilate.analysis import CrossSection, cantilever_end_load
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def test_rectangular_section_properties():
    # 20 x 10 mm: A = 200, I = b*h^3/12 = 1666.67, c = 5, Z = I/c = 333.33,
    #   r = sqrt(I/A) = 2.887; transverse I_t = h*b^3/12 = 6666.67, r_t = 5.774.
    s = CrossSection.rectangular(width=_q("20 mm"), height=_q("10 mm"))
    assert s.area.to("mm**2").magnitude == pytest.approx(200.0)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(1666.667, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(5.0)
    assert s.section_modulus.to("mm**3").magnitude == pytest.approx(333.333, rel=1e-4)
    assert s.radius_of_gyration.to("mm").magnitude == pytest.approx(2.88675, rel=1e-4)
    assert s.second_moment_transverse.to("mm**4").magnitude == pytest.approx(6666.667, rel=1e-4)
    assert s.radius_of_gyration_transverse.to("mm").magnitude == pytest.approx(5.7735, rel=1e-4)
    # This bar is flat side up, so the *bending* axis is the weaker of the two.
    assert s.least_radius_of_gyration.to("mm").magnitude == pytest.approx(2.88675, rel=1e-4)


def test_solid_circular_section_properties():
    # d = 20 mm: A = 314.16, I = pi*d^4/64 = 7854, c = 10, r = sqrt(I/A) = 5.
    s = CrossSection.solid_circular(diameter=_q("20 mm"))
    assert s.area.to("mm**2").magnitude == pytest.approx(314.159, rel=1e-4)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(7853.98, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(10.0)
    assert s.radius_of_gyration.to("mm").magnitude == pytest.approx(5.0, rel=1e-4)
    # A round bar has no weak axis: both second moments coincide.
    assert s.second_moment_transverse.to("mm**4").magnitude == pytest.approx(7853.98, rel=1e-4)
    assert s.least_radius_of_gyration.to("mm").magnitude == pytest.approx(5.0, rel=1e-4)


def test_hollow_circular_section_properties_and_validation():
    # D = 20, d = 10: A = pi*(400-100)/4 = 235.6, I = pi*(20^4-10^4)/64 = 7363.
    s = CrossSection.hollow_circular(outer_diameter=_q("20 mm"), inner_diameter=_q("10 mm"))
    assert s.area.to("mm**2").magnitude == pytest.approx(235.619, rel=1e-4)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(7363.1, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(10.0)
    assert s.second_moment_transverse.to("mm**4").magnitude == pytest.approx(7363.1, rel=1e-4)
    with pytest.raises(ValueError, match="must be non-negative and below"):
        CrossSection.hollow_circular(outer_diameter=_q("10 mm"), inner_diameter=_q("10 mm"))


def test_hollow_rectangular_section_properties_and_validation():
    # 80 x 120 box, t = 5: inner 70 x 110. A = 9600 - 7700 = 1900,
    #   I = (80*120^3 - 70*110^3)/12 = 3,755,833, c = 60, Z = 62,597,
    #   r = sqrt(I/A) = 44.46; I_t = (120*80^3 - 110*70^3)/12 = 1,975,833,
    #   r_t = sqrt(I_t/A) = 32.25 (governs).
    s = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    assert s.area.to("mm**2").magnitude == pytest.approx(1900.0)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(3755833.3, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(60.0)
    assert s.section_modulus.to("mm**3").magnitude == pytest.approx(62597.2, rel=1e-4)
    assert s.radius_of_gyration.to("mm").magnitude == pytest.approx(44.4617, rel=1e-4)
    assert s.second_moment_transverse.to("mm**4").magnitude == pytest.approx(1975833.3, rel=1e-4)
    assert s.least_radius_of_gyration.to("mm").magnitude == pytest.approx(32.2477, rel=1e-4)
    # Walls that meet (or cross) in the middle are not a tube.
    for t in ("40 mm", "50 mm", "0 mm"):
        with pytest.raises(ValueError, match="must be positive and below half"):
            CrossSection.hollow_rectangular(
                width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q(t)
            )


def test_i_section_properties_and_validation():
    # h = 200, bf = 100, tf = 10, tw = 6: A = 2*1000 + 180*6 = 3080,
    #   I = (100*200^3 - 94*180^3)/12 = 20,982,667, c = 100, Z = 209,827,
    #   r = sqrt(I/A) = 82.54; weak axis I_t = (2*10*100^3 + 180*6^3)/12
    #   = 1,669,907, r_t = sqrt(I_t/A) = 23.29 — the I-shape's classic Achilles heel.
    s = CrossSection.i_section(
        depth=_q("200 mm"),
        flange_width=_q("100 mm"),
        flange_thickness=_q("10 mm"),
        web_thickness=_q("6 mm"),
    )
    assert s.area.to("mm**2").magnitude == pytest.approx(3080.0)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(20982666.7, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(100.0)
    assert s.section_modulus.to("mm**3").magnitude == pytest.approx(209826.7, rel=1e-4)
    assert s.radius_of_gyration.to("mm").magnitude == pytest.approx(82.539, rel=1e-4)
    assert s.second_moment_transverse.to("mm**4").magnitude == pytest.approx(1669906.7, rel=1e-4)
    assert s.radius_of_gyration_transverse.to("mm").magnitude == pytest.approx(23.2848, rel=1e-4)
    assert s.least_radius_of_gyration.to("mm").magnitude == pytest.approx(23.2848, rel=1e-4)
    with pytest.raises(ValueError, match="below half the depth"):
        CrossSection.i_section(
            depth=_q("200 mm"),
            flange_width=_q("100 mm"),
            flange_thickness=_q("100 mm"),
            web_thickness=_q("6 mm"),
        )
    with pytest.raises(ValueError, match="at most the flange_width"):
        CrossSection.i_section(
            depth=_q("200 mm"),
            flange_width=_q("100 mm"),
            flange_thickness=_q("10 mm"),
            web_thickness=_q("120 mm"),
        )


def test_i_section_degenerates_to_the_solid_rectangle():
    # With tw = bf the "I" is just a solid bar, so I and A must match exactly.
    i = CrossSection.i_section(
        depth=_q("200 mm"),
        flange_width=_q("100 mm"),
        flange_thickness=_q("10 mm"),
        web_thickness=_q("100 mm"),
    )
    rect = CrossSection.rectangular(width=_q("100 mm"), height=_q("200 mm"))
    assert i.area.to("mm**2").magnitude == pytest.approx(rect.area.to("mm**2").magnitude)
    assert i.second_moment.to("mm**4").magnitude == pytest.approx(
        rect.second_moment.to("mm**4").magnitude
    )
    assert i.second_moment_transverse.to("mm**4").magnitude == pytest.approx(
        rect.second_moment_transverse.to("mm**4").magnitude
    )


def test_least_radius_falls_back_without_a_transverse_moment():
    # A hand-built section (no builder) carries only the bending-axis I, so the
    # least radius of gyration must fall back to it rather than guess.
    s = CrossSection(
        area=_q("200 mm**2"),
        second_moment=_q("1666.667 mm**4"),
        extreme_fibre=_q("5 mm"),
    )
    assert s.radius_of_gyration_transverse is None
    assert s.least_radius_of_gyration.to("mm").magnitude == pytest.approx(
        s.radius_of_gyration.to("mm").magnitude
    )


def test_cross_section_feeds_a_beam_check():
    # The section's I and c drive a bending check directly, matching the
    # standalone helpers: a 20x10 cantilever -> 150 MPa at the tip load.
    s = CrossSection.rectangular(width=_q("20 mm"), height=_q("10 mm"))
    result = cantilever_end_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=s.second_moment,
        extreme_fibre=s.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)
