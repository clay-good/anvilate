"""Tests for the CrossSection value object against hand-computed properties."""

from __future__ import annotations

import pytest

from anvilate.analysis import CrossSection, cantilever_end_load
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def test_rectangular_section_properties():
    # 20 x 10 mm: A = 200, I = b*h^3/12 = 1666.67, c = 5, Z = I/c = 333.33,
    #   r = sqrt(I/A) = 2.887.
    s = CrossSection.rectangular(width=_q("20 mm"), height=_q("10 mm"))
    assert s.area.to("mm**2").magnitude == pytest.approx(200.0)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(1666.667, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(5.0)
    assert s.section_modulus.to("mm**3").magnitude == pytest.approx(333.333, rel=1e-4)
    assert s.radius_of_gyration.to("mm").magnitude == pytest.approx(2.88675, rel=1e-4)


def test_solid_circular_section_properties():
    # d = 20 mm: A = 314.16, I = pi*d^4/64 = 7854, c = 10, r = sqrt(I/A) = 5.
    s = CrossSection.solid_circular(diameter=_q("20 mm"))
    assert s.area.to("mm**2").magnitude == pytest.approx(314.159, rel=1e-4)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(7853.98, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(10.0)
    assert s.radius_of_gyration.to("mm").magnitude == pytest.approx(5.0, rel=1e-4)


def test_hollow_circular_section_properties_and_validation():
    # D = 20, d = 10: A = pi*(400-100)/4 = 235.6, I = pi*(20^4-10^4)/64 = 7363.
    s = CrossSection.hollow_circular(outer_diameter=_q("20 mm"), inner_diameter=_q("10 mm"))
    assert s.area.to("mm**2").magnitude == pytest.approx(235.619, rel=1e-4)
    assert s.second_moment.to("mm**4").magnitude == pytest.approx(7363.1, rel=1e-4)
    assert s.extreme_fibre.to("mm").magnitude == pytest.approx(10.0)
    with pytest.raises(ValueError, match="must be non-negative and below"):
        CrossSection.hollow_circular(outer_diameter=_q("10 mm"), inner_diameter=_q("10 mm"))


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
