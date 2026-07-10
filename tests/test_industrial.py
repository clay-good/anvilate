"""Tests for the industrial pack: CoverPlate declaration and auto-dispatch."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.packs.industrial import CoverPlate, PlateEdge, screen_cover_plate
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _rect(edge: PlateEdge = PlateEdge.SIMPLY_SUPPORTED, **overrides) -> CoverPlate:
    fields = {
        "name": "cover",
        "pressure": _q("50 kPa"),
        "thickness": _q("6 mm"),
        "material": "ASTM-A36",
        "edge": edge,
        "length": _q("500 mm"),
        "width": _q("500 mm"),
    }
    fields.update(overrides)
    return CoverPlate(**fields)


def _round(edge: PlateEdge = PlateEdge.SIMPLY_SUPPORTED, **overrides) -> CoverPlate:
    fields = {
        "name": "blank",
        "pressure": _q("50 kPa"),
        "thickness": _q("6 mm"),
        "material": "ASTM-A36",
        "edge": edge,
        "diameter": _q("500 mm"),
    }
    fields.update(overrides)
    return CoverPlate(**fields)


def test_rectangular_covers_dispatch_by_edge_condition():
    # 500x500x6 A36 under 50 kPa: simply supported the Navier centre stress is
    # 99.8 MPa (SF 2.51); clamped the Roark edge stress is 106.9 MPa (SF 2.34)
    # — the clamped square's peak stress is HIGHER even as it deflects 3.2x
    # less, and each entry cites the theory it ran.
    ss = screen_cover_plate(_rect(), required_safety_factor=2.0)
    assert ss.entries[0].passed
    assert "safety factor 2.51" in ss.entries[0].detail
    assert ss.entries[0].reference == "Kirchhoff plate theory (Navier series)"
    clamped = screen_cover_plate(_rect(PlateEdge.CLAMPED), required_safety_factor=2.0)
    assert clamped.entries[0].passed
    assert "safety factor 2.34" in clamped.entries[0].detail
    assert clamped.entries[0].reference == "Roark's Formulas, Table 11.4"


def test_circular_covers_dispatch_by_edge_condition():
    # The O500 blank: simply supported 107.4 MPa (SF 2.33), clamped 65.1 MPa
    # (SF 3.84) at the rim.
    ss = screen_cover_plate(_round(), required_safety_factor=2.0)
    assert "safety factor 2.33" in ss.entries[0].detail
    clamped = screen_cover_plate(_round(PlateEdge.CLAMPED), required_safety_factor=2.0)
    assert "safety factor 3.84" in clamped.entries[0].detail
    assert clamped.entries[0].reference == "Timoshenko plate theory"


def test_deflection_limit_adds_the_flatness_screen():
    # Without a limit there is one entry; with a 2 mm limit the SS cover's
    # 3.21 mm centre deflection fails the flatness screen.
    bare = screen_cover_plate(_rect(), required_safety_factor=2.0)
    assert len(bare.entries) == 1
    limited = screen_cover_plate(_rect(deflection_limit=_q("2 mm")), required_safety_factor=2.0)
    flatness = next(e for e in limited.entries if "flatness" in e.name)
    assert flatness.status is CheckStatus.FAIL
    assert "deflection 3.209" in flatness.detail


def test_patch_footprint_dispatches_the_patch_check():
    # The 5 kN machine foot from the analysis worked example (0.5 MPa on a
    # centred 100x100 pad of a 500x500x6 panel): sigma 177.0 MPa -> the
    # bending screen FAILs at 2.0 where the same load smeared passed 6.26.
    card = screen_cover_plate(
        _rect(
            pressure=_q("0.5 MPa"),
            patch_length=_q("100 mm"),
            patch_width=_q("100 mm"),
        ),
        required_safety_factor=2.0,
    )
    assert card.entries[0].status is CheckStatus.FAIL
    assert "safety factor 1.41" in card.entries[0].detail


def test_patch_footprint_is_restricted_to_the_encoded_case():
    with pytest.raises(ValidationError, match="needs both patch_length and patch_width"):
        _rect(patch_length=_q("100 mm"))
    with pytest.raises(ValidationError, match="only encoded for a simply-supported"):
        _rect(
            edge=PlateEdge.CLAMPED,
            patch_length=_q("100 mm"),
            patch_width=_q("100 mm"),
        )
    with pytest.raises(ValidationError, match="only encoded for a simply-supported"):
        _round(patch_length=_q("100 mm"), patch_width=_q("100 mm"))


def test_cover_geometry_must_be_declared_exactly_one_way():
    with pytest.raises(ValidationError, match="length/width for a rectangle OR diameter"):
        _rect(diameter=_q("500 mm"))
    with pytest.raises(ValidationError, match="needs both length and width"):
        _rect(width=None)
    with pytest.raises(ValidationError, match="declare the plan geometry"):
        CoverPlate(
            name="cover",
            pressure=_q("50 kPa"),
            thickness=_q("6 mm"),
            material="ASTM-A36",
        )


def test_cover_rejects_a_force_pressure():
    with pytest.raises(ValidationError, match="pressure must be a"):
        _rect(pressure=_q("50 N"))
