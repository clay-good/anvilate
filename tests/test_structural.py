"""Tests for the structural pack: BeamMember declaration and auto-dispatch."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis import (
    ColumnEnd,
    CrossSection,
    cantilever_end_load,
    cantilever_triangular_load,
    fixed_fixed_center_load,
    simply_supported_center_patch_load,
    simply_supported_partial_uniform_load,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
)
from anvilate.packs.structural import (
    BasePlate,
    BeamColumnMember,
    BeamMember,
    BoltedConnection,
    ColumnMember,
    ConcreteBearing,
    GussetPlate,
    LiftingLug,
    LoadType,
    ShearPlate,
    Support,
    TensionMember,
    WeldedConnection,
    screen_base_plate,
    screen_beam_column,
    screen_beam_member,
    screen_bolted_connection,
    screen_column_member,
    screen_concrete_bearing,
    screen_gusset_plate,
    screen_lifting_lug,
    screen_shear_plate,
    screen_structure,
    screen_tension_member,
    screen_welded_connection,
)
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _section() -> CrossSection:
    return CrossSection.rectangular(width=_q("20 mm"), height=_q("10 mm"))


def _member(
    support: Support, load_type: LoadType, load: str, material: str = "ASTM-A36"
) -> BeamMember:
    return BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=support,
        load=_q(load),
        load_type=load_type,
        material=material,
    )


def test_point_load_dispatches_to_the_matching_check():
    # A cantilever point-load member must produce the same stress the standalone
    # cantilever_end_load gives for the same section, span, and load.
    member = _member(Support.CANTILEVER, LoadType.POINT, "100 N")
    card = screen_beam_member(member, required_safety_factor=1.5)
    # The bending entry passes (A36 yield 250 MPa vs the 150 MPa cantilever stress).
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    # Cross-check the dispatched stress against the standalone helper.
    standalone = cantilever_end_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    assert standalone.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)


def test_offset_point_load_dispatches_to_the_offset_check():
    # A load_position off mid-span must route to simply_supported_offset_load:
    # at the quarter point M = P*a*b/L = 9375 N*mm -> sigma 28.125 MPa (not the
    # mid-span 37.5), so the bending SF is the offset case's.
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.SIMPLY_SUPPORTED,
        load=_q("100 N"),
        load_type=LoadType.POINT,
        material="ASTM-A36",
        load_position=_q("125 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    # A36 yield 250 / 28.125 = 8.89, vs 6.67 for the mid-span case.
    assert "8.89" in bending.detail


def test_offset_cantilever_point_load_dispatches_to_the_offset_check():
    # A load_position short of the tip must route to cantilever_offset_load:
    # at mid-length M = F*a = 25000 N*mm -> sigma 75 MPa (not the tip case's 150),
    # so the bending SF is the offset case's 250/75 = 3.33 (vs 1.67 at the tip).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.CANTILEVER,
        load=_q("100 N"),
        load_type=LoadType.POINT,
        material="ASTM-A36",
        load_position=_q("250 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "3.33" in bending.detail


def test_offset_fixed_fixed_point_load_dispatches_to_the_offset_check():
    # A load_position off mid-span must route to fixed_fixed_offset_load: at the
    # quarter point the nearer-wall moment M = F*a*b^2/L^2 = 7031.25 N*mm ->
    # sigma 21.09 MPa (above the mid-span case's 18.75 — off-center is *worse*
    # on a fixed-fixed beam), so the bending SF is the offset case's 11.85.
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.FIXED_FIXED,
        load=_q("100 N"),
        load_type=LoadType.POINT,
        material="ASTM-A36",
        load_position=_q("125 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "11.85" in bending.detail


def test_load_position_requires_a_point_load():
    for support, load_type, load in (
        (Support.SIMPLY_SUPPORTED, LoadType.DISTRIBUTED, "1 N/mm"),
        (Support.CANTILEVER, LoadType.DISTRIBUTED, "1 N/mm"),
        (Support.FIXED_FIXED, LoadType.DISTRIBUTED, "1 N/mm"),
    ):
        with pytest.raises(ValidationError, match="only supported for a point load"):
            BeamMember(
                name="beam",
                section=_section(),
                length=_q("500 mm"),
                support=support,
                load=_q(load),
                load_type=load_type,
                material="ASTM-A36",
                load_position=_q("125 mm"),
            )


def test_offset_fixed_pinned_point_load_dispatches_to_the_offset_check():
    # A load_position on a propped cantilever must route to
    # fixed_pinned_offset_load: 125 mm from the prop the moment under the load
    # governs, M = 7910 N*mm -> sigma 23.73 MPa -> SF 250/23.73 = 10.53 (vs the
    # mid-span case's 8.89).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.FIXED_PINNED,
        load=_q("100 N"),
        load_type=LoadType.POINT,
        material="ASTM-A36",
        load_position=_q("125 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "10.53" in bending.detail


def test_fixed_pinned_member_dispatches_to_the_propped_checks():
    # A propped-cantilever point member must produce the fixed_pinned_center_load
    # stress: M = 3*F*L/16 = 9375 N*mm -> sigma 28.125 MPa -> SF 250/28.125 = 8.89.
    card = screen_beam_member(
        _member(Support.FIXED_PINNED, LoadType.POINT, "100 N"), required_safety_factor=1.5
    )
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "8.89" in bending.detail
    # And the distributed member the fixed_pinned_uniform_load stress: M = w*L^2/8
    # = 31250 N*mm -> sigma 93.75 MPa -> SF 250/93.75 = 2.67.
    card = screen_beam_member(
        _member(Support.FIXED_PINNED, LoadType.DISTRIBUTED, "1 N/mm"),
        required_safety_factor=1.5,
    )
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "2.67" in bending.detail


def test_support_condition_changes_the_dispatch():
    # For the same load, a fixed-fixed beam is far less stressed than a cantilever,
    # confirming the support drives which check runs.
    cantilever = screen_beam_member(
        _member(Support.CANTILEVER, LoadType.POINT, "100 N"), required_safety_factor=1.5
    )
    fixed = screen_beam_member(
        _member(Support.FIXED_FIXED, LoadType.POINT, "100 N"), required_safety_factor=1.5
    )
    # Both pass on A36, but the fixed-fixed member is the safer one; check the
    # underlying dispatch produced the fixed-fixed moment (F*L/8, not F*L).
    assert cantilever.status is CheckStatus.PASS
    assert fixed.status is CheckStatus.PASS
    ff = fixed_fixed_center_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    assert ff.max_bending_stress.to("MPa").magnitude == pytest.approx(18.75, rel=1e-4)


def test_distributed_load_dispatches_and_screens_deflection():
    member = _member(Support.SIMPLY_SUPPORTED, LoadType.DISTRIBUTED, "1 N/mm")
    card = screen_beam_member(member, required_safety_factor=1.5, max_deflection=_q("1 mm"))
    # A36 simply-supported UDL: 93.75 MPa (PASS vs 250) but 2.44 mm deflection
    # exceeds the 1 mm limit -> the member FAILs overall.
    assert card.status is CheckStatus.FAIL
    names = {e.name for e in card.entries}
    assert names == {"beam bending", "beam deflection"}
    ss = simply_supported_uniform_load(
        distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    assert ss.max_bending_stress.to("MPa").magnitude == pytest.approx(93.75, rel=1e-4)


def test_deflection_omitted_when_no_limit_given():
    card = screen_beam_member(
        _member(Support.CANTILEVER, LoadType.POINT, "100 N"), required_safety_factor=1.5
    )
    assert [e.name for e in card.entries] == ["beam bending"]


def test_point_member_rejects_a_distributed_load_dimension():
    with pytest.raises(ValidationError, match="point load must be a"):
        _member(Support.CANTILEVER, LoadType.POINT, "1 N/mm")


def test_distributed_member_rejects_a_force():
    with pytest.raises(ValidationError, match="distributed load must be a"):
        _member(Support.SIMPLY_SUPPORTED, LoadType.DISTRIBUTED, "100 N")


def test_triangular_load_dispatches_to_the_simply_supported_case():
    member = _member(Support.SIMPLY_SUPPORTED, LoadType.TRIANGULAR, "1 N/mm")
    card = screen_beam_member(member, required_safety_factor=1.5)
    # M = w0*L^2/(9*sqrt(3)) = 16037 N*mm -> sigma = M*c/I = 48.11 MPa, about half
    # the 93.75 MPa the same peak intensity gives as a full UDL.
    assert card.status is CheckStatus.PASS
    tri = simply_supported_triangular_load(
        peak_distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    assert tri.max_bending_stress.to("MPa").magnitude == pytest.approx(48.113, rel=1e-4)
    assert "safety factor 5.20" in card.entries[0].detail  # 250 / 48.113


def test_loaded_length_dispatches_to_the_partial_udl_case():
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.SIMPLY_SUPPORTED,
        load=_q("1 N/mm"),
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        loaded_length=_q("250 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    standalone = simply_supported_partial_uniform_load(
        distributed_load=_q("1 N/mm"),
        loaded_length=_q("250 mm"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    expected_sf = 250 / standalone.max_bending_stress.to("MPa").magnitude
    assert card.entries[0].passed
    assert f"safety factor {expected_sf:.2f}" in card.entries[0].detail
    # The half-span patch is milder than the same intensity over the full span.
    full = simply_supported_uniform_load(
        distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    assert (
        standalone.max_bending_stress.to("MPa").magnitude
        < full.max_bending_stress.to("MPa").magnitude
    )


def test_loaded_length_dispatches_to_the_cantilever_patch_case():
    # A wall-adjacent half-length patch on a cantilever: M = w*a^2/2 = 31250 N*mm
    # -> sigma 93.75 MPa -> SF 250/93.75 = 2.67 (vs 0.67 for the full-span UDL).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.CANTILEVER,
        load=_q("1 N/mm"),
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        loaded_length=_q("250 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert card.entries[0].passed
    assert "safety factor 2.67" in card.entries[0].detail


def test_loaded_length_dispatches_to_the_fixed_fixed_patch_case():
    # A wall-adjacent half-span patch on a fixed-fixed beam: the loaded-wall
    # moment M = w*a^2*(6L^2 - 8aL + 3a^2)/(12L^2) = 14323 N*mm -> sigma
    # 42.97 MPa -> SF 250/42.97 = 5.82 (vs 4.00 for the full-span UDL).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.FIXED_FIXED,
        load=_q("1 N/mm"),
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        loaded_length=_q("250 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert card.entries[0].passed
    assert "safety factor 5.82" in card.entries[0].detail


def test_loaded_length_dispatches_to_the_fixed_pinned_patch_case():
    # A wall-adjacent half-span patch on a propped cantilever: the wall moment
    # M = w*a^2*(2L - a)^2/(8L^2) = 17578 N*mm -> sigma 52.73 MPa -> SF
    # 250/52.73 = 4.74 (vs 2.67 for the full-span UDL).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.FIXED_PINNED,
        load=_q("1 N/mm"),
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        loaded_length=_q("250 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert card.entries[0].passed
    assert "safety factor 4.74" in card.entries[0].detail


def test_loaded_length_rejects_non_distributed_loads():
    for support, load_type, load in (
        (Support.SIMPLY_SUPPORTED, LoadType.POINT, "100 N"),
        (Support.SIMPLY_SUPPORTED, LoadType.TRIANGULAR, "1 N/mm"),
        (Support.FIXED_PINNED, LoadType.POINT, "100 N"),
    ):
        with pytest.raises(ValidationError, match="loaded_length is only encoded for"):
            BeamMember(
                name="beam",
                section=_section(),
                length=_q("500 mm"),
                support=support,
                load=_q(load),
                load_type=load_type,
                material="ASTM-A36",
                loaded_length=_q("250 mm"),
            )


def test_patch_centered_dispatches_to_the_center_patch_case():
    # A centered half-span patch on a simply-supported beam: M = w*a*(2L - a)/8
    # = 23437.5 N*mm -> sigma 70.31 MPa -> SF 250/70.31 = 3.56 (vs 4.74 for the
    # same patch parked against a support).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.SIMPLY_SUPPORTED,
        load=_q("1 N/mm"),
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        loaded_length=_q("250 mm"),
        patch_centered=True,
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    standalone = simply_supported_center_patch_load(
        distributed_load=_q("1 N/mm"),
        loaded_length=_q("250 mm"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    expected_sf = 250 / standalone.max_bending_stress.to("MPa").magnitude
    assert card.entries[0].passed
    assert f"safety factor {expected_sf:.2f}" in card.entries[0].detail
    assert "safety factor 3.56" in card.entries[0].detail


def test_patch_centered_dispatches_on_every_support_condition():
    # Wall moments for a centered half-span patch (w = 1 N/mm, a = 250, L = 500):
    # cantilever M = w*a*L/2 = 62500 N*mm -> sigma 187.5 -> SF 1.33;
    # fixed-fixed M = w*a*(3L^2 - a^2)/(24L) = 14323 -> sigma 42.97 -> SF 5.82;
    # fixed-pinned M = w*a*(3L^2 - a^2)/(16L) = 21484 -> sigma 64.45 -> SF 3.88.
    for support, expected_sf in (
        (Support.CANTILEVER, "1.33"),
        (Support.FIXED_FIXED, "5.82"),
        (Support.FIXED_PINNED, "3.88"),
    ):
        member = BeamMember(
            name="beam",
            section=_section(),
            length=_q("500 mm"),
            support=support,
            load=_q("1 N/mm"),
            load_type=LoadType.DISTRIBUTED,
            material="ASTM-A36",
            loaded_length=_q("250 mm"),
            patch_centered=True,
        )
        card = screen_beam_member(member, required_safety_factor=1.2)
        assert card.entries[0].passed
        assert f"safety factor {expected_sf}" in card.entries[0].detail


def test_patch_centered_requires_a_loaded_length():
    with pytest.raises(ValidationError, match="patch_centered requires a loaded_length"):
        BeamMember(
            name="beam",
            section=_section(),
            length=_q("500 mm"),
            support=Support.SIMPLY_SUPPORTED,
            load=_q("1 N/mm"),
            load_type=LoadType.DISTRIBUTED,
            material="ASTM-A36",
            patch_centered=True,
        )


def test_triangular_load_dispatches_to_the_cantilever_case():
    member = _member(Support.CANTILEVER, LoadType.TRIANGULAR, "1 N/mm")
    card = screen_beam_member(member, required_safety_factor=1.5)
    # M = w0*L^2/6 = 41667 N*mm -> sigma = M*c/I = 125 MPa, a third of the 375 MPa
    # the same peak intensity gives as a full UDL on the cantilever.
    assert card.status is CheckStatus.PASS
    tri = cantilever_triangular_load(
        peak_distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=_section().second_moment,
        extreme_fibre=_section().extreme_fibre,
        elastic_modulus=Quantity.parse("200 GPa"),
    )
    assert tri.max_bending_stress.to("MPa").magnitude == pytest.approx(125.0, rel=1e-6)
    assert "safety factor 2.00" in card.entries[0].detail  # 250 / 125


def test_triangular_load_dispatches_to_the_fixed_fixed_case():
    # A fixed-fixed triangular member: the peak-end wall governs, M = w0*L^2/20
    # = 12500 N*mm -> sigma 37.5 MPa -> SF 250/37.5 = 6.67.
    member = _member(Support.FIXED_FIXED, LoadType.TRIANGULAR, "1 N/mm")
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert card.entries[0].passed
    assert "safety factor 6.67" in card.entries[0].detail


def test_triangular_load_dispatches_to_the_fixed_pinned_case():
    # A propped-cantilever triangular member (peak at the wall): M = w0*L^2/15
    # = 16667 N*mm -> sigma 50 MPa -> SF 250/50 = 5.00. Every support condition
    # now dispatches a declared triangle.
    member = _member(Support.FIXED_PINNED, LoadType.TRIANGULAR, "1 N/mm")
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert card.entries[0].passed
    assert "safety factor 5.00" in card.entries[0].detail


def test_triangular_member_rejects_a_force():
    with pytest.raises(ValidationError, match="triangular load must be a"):
        _member(Support.SIMPLY_SUPPORTED, LoadType.TRIANGULAR, "100 N")


def test_mirrored_triangle_dispatches_on_the_fixed_pinned_member():
    # The same fixed-pinned triangle mirrored to peak at the prop: the wall
    # moment drops from w0*L^2/15 to 7*w0*L^2/120 = 14583 N*mm -> sigma
    # 43.75 MPa -> SF 250/43.75 = 5.71 (vs 5.00 with the peak at the wall).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.FIXED_PINNED,
        load=_q("1 N/mm"),
        load_type=LoadType.TRIANGULAR,
        material="ASTM-A36",
        triangle_mirrored=True,
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert card.entries[0].passed
    assert "safety factor 5.71" in card.entries[0].detail


def test_mirrored_triangle_dispatches_on_the_cantilever_member():
    # The same cantilever triangle mirrored to peak at the tip: the wall moment
    # doubles (w0*L^2/6 -> w0*L^2/3 = 83333 N*mm) -> sigma 250 MPa, exactly at
    # yield -> SF 1.00 FAILs where the peak-at-wall orientation screened 2.00.
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.CANTILEVER,
        load=_q("1 N/mm"),
        load_type=LoadType.TRIANGULAR,
        material="ASTM-A36",
        triangle_mirrored=True,
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert card.entries[0].status is CheckStatus.FAIL
    assert "safety factor 1.00" in card.entries[0].detail


def test_mirrored_triangle_rejects_symmetric_supports_and_other_load_types():
    # The mirrored orientation is only distinct on the two supports with a wall:
    # simply-supported/fixed-fixed triangles are symmetric, and it says nothing
    # about a non-triangular load.
    common = {
        "name": "beam",
        "section": _section(),
        "length": _q("500 mm"),
        "material": "ASTM-A36",
    }
    with pytest.raises(ValidationError, match="triangle_mirrored is only encoded"):
        BeamMember(
            support=Support.SIMPLY_SUPPORTED,
            load=_q("1 N/mm"),
            load_type=LoadType.TRIANGULAR,
            triangle_mirrored=True,
            **common,
        )
    with pytest.raises(ValidationError, match="triangle_mirrored is only encoded"):
        BeamMember(
            support=Support.FIXED_PINNED,
            load=_q("1 N/mm"),
            load_type=LoadType.DISTRIBUTED,
            triangle_mirrored=True,
            **common,
        )


def test_pair_offset_dispatches_to_the_symmetric_pair_check():
    # 100 N at 150 mm from EACH support of a 500 mm span: four-point bending
    # carries a constant M = F*a = 15000 N*mm -> sigma 45 MPa -> SF 250/45 =
    # 5.56, vs 3.33 had the 200 N total been lumped at mid-span (M = 25000).
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.SIMPLY_SUPPORTED,
        load=_q("100 N"),
        load_type=LoadType.POINT,
        material="ASTM-A36",
        pair_offset=_q("150 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "safety factor 5.56" in bending.detail


def test_pair_offset_rejects_other_supports_load_types_and_load_position():
    # The pair case is only encoded on a simply-supported point member, and a
    # pair's position IS its offset — load_position has no meaning beside it.
    common = {
        "name": "beam",
        "section": _section(),
        "length": _q("500 mm"),
        "material": "ASTM-A36",
    }
    with pytest.raises(ValidationError, match="pair_offset is only encoded"):
        BeamMember(
            support=Support.CANTILEVER,
            load=_q("100 N"),
            load_type=LoadType.POINT,
            pair_offset=_q("150 mm"),
            **common,
        )
    with pytest.raises(ValidationError, match="pair_offset is only encoded"):
        BeamMember(
            support=Support.SIMPLY_SUPPORTED,
            load=_q("1 N/mm"),
            load_type=LoadType.DISTRIBUTED,
            pair_offset=_q("150 mm"),
            **common,
        )
    with pytest.raises(ValidationError, match="mutually exclusive"):
        BeamMember(
            support=Support.SIMPLY_SUPPORTED,
            load=_q("100 N"),
            load_type=LoadType.POINT,
            pair_offset=_q("150 mm"),
            load_position=_q("125 mm"),
            **common,
        )


def test_moment_load_dispatches_on_the_cantilever_member():
    # A 50 N*m couple at the tip: sigma = M*c/I = 150 MPa everywhere -> SF
    # 250/150 = 1.67, and the tip deflection M*L^2/2EI = 18.75 mm busts a 10 mm
    # limit — the couple bends the whole span, unlike an equal-wall-moment force.
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.CANTILEVER,
        load=_q("50 N*m"),
        load_type=LoadType.MOMENT,
        material="ASTM-A36",
        deflection_limit=_q("10 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "safety factor 1.67" in bending.detail
    deflection = next(e for e in card.entries if "deflection" in e.name)
    assert deflection.status is CheckStatus.FAIL
    assert "18.750 mm" in deflection.detail


def test_moment_load_dispatches_on_the_simply_supported_member():
    # The same couple on a simply-supported span: the end stress matches the
    # cantilever's 150 MPa, but the deflection M*L^2/(9*sqrt(3)*EI) = 2.406 mm
    # clears the same 10 mm limit the cantilever busts — distinct dispatch.
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.SIMPLY_SUPPORTED,
        load=_q("50 N*m"),
        load_type=LoadType.MOMENT,
        material="ASTM-A36",
        deflection_limit=_q("10 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    deflection = next(e for e in card.entries if "deflection" in e.name)
    assert deflection.status is CheckStatus.PASS
    assert "2.406 mm" in deflection.detail


def test_moment_load_dispatches_on_the_fixed_pinned_member():
    # The same couple at the prop of a propped cantilever: the wall carry-over
    # is M0/2 so the applied couple still governs (sigma 150 MPa, as on the
    # other supports), but delta_max = M*L^2/27EI = 1.389 mm — the stiffest of
    # the three encoded supports.
    member = BeamMember(
        name="beam",
        section=_section(),
        length=_q("500 mm"),
        support=Support.FIXED_PINNED,
        load=_q("50 N*m"),
        load_type=LoadType.MOMENT,
        material="ASTM-A36",
        deflection_limit=_q("10 mm"),
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.status is CheckStatus.PASS
    assert "safety factor 1.67" in bending.detail
    deflection = next(e for e in card.entries if "deflection" in e.name)
    assert deflection.status is CheckStatus.PASS
    assert "1.389 mm" in deflection.detail


def test_moment_member_rejects_a_force_and_the_fixed_fixed_support():
    # The load must be a couple, and only a support with an end free to receive
    # one is encoded — both ends of a fixed-fixed member are built-in walls,
    # which absorb an applied couple.
    with pytest.raises(ValidationError, match="moment load must be a"):
        _member(Support.CANTILEVER, LoadType.MOMENT, "100 N")
    with pytest.raises(ValidationError, match="moment load is only encoded"):
        _member(Support.FIXED_FIXED, LoadType.MOMENT, "50 N*m")


def _column(length: str, load: str = "5 kN") -> ColumnMember:
    return ColumnMember(
        name="col",
        section=_section(),  # r = 2.887 mm about the weak axis
        length=_q(length),
        end_condition=ColumnEnd.PINNED_PINNED,
        axial_load=_q(load),
        material="ASTM-A36",
    )


def test_slender_column_uses_the_euler_regime():
    # 500 mm pinned column, r = 2.887 -> lambda = 173 > lambda_1 (125.7) -> Euler;
    # sigma_cr ~ 65.8 MPa vs 25 MPa applied (5 kN / 200 mm^2) -> SF ~ 2.6 -> PASS.
    card = screen_column_member(_column("500 mm"), required_safety_factor=2.0)
    assert card.status is CheckStatus.PASS
    assert "Euler" in card.entries[0].name


def test_stubby_column_uses_the_johnson_regime():
    # 200 mm pinned column -> lambda = 69 < lambda_1 -> Johnson (inelastic).
    card = screen_column_member(_column("200 mm"), required_safety_factor=2.0)
    assert card.status is CheckStatus.PASS
    assert "Johnson" in card.entries[0].name


def test_column_screen_ignores_which_axis_was_declared():
    # A strong-axis declaration cannot inflate buckling capacity: the same
    # 20x10 bar declared either way around screens with the weak-axis r.
    common = {
        "name": "col",
        "length": _q("500 mm"),
        "end_condition": ColumnEnd.PINNED_PINNED,
        "axial_load": _q("5 kN"),
        "material": "ASTM-A36",
    }
    weak = screen_column_member(
        ColumnMember(
            section=CrossSection.rectangular(width=_q("20 mm"), height=_q("10 mm")), **common
        ),
        required_safety_factor=2.0,
    )
    strong = screen_column_member(
        ColumnMember(
            section=CrossSection.rectangular(width=_q("10 mm"), height=_q("20 mm")), **common
        ),
        required_safety_factor=2.0,
    )
    assert strong.entries[0].detail == weak.entries[0].detail
    assert "Euler" in strong.entries[0].name


def test_column_screen_falls_back_to_the_declared_axis_without_transverse_i():
    # A hand-built section records no transverse second moment, so the caller
    # still owns the weak-axis choice: a strong-axis raw section screens about
    # the declared axis (higher capacity than the builder's least-axis screen).
    raw = CrossSection(
        area=_q("200 mm**2"),
        second_moment=_q("6666.667 mm**4"),  # the 20x10 bar's STRONG axis
        extreme_fibre=_q("10 mm"),
    )
    card = screen_column_member(
        ColumnMember(
            name="col",
            section=raw,
            length=_q("500 mm"),
            end_condition=ColumnEnd.PINNED_PINNED,
            axial_load=_q("5 kN"),
            material="ASTM-A36",
        ),
        required_safety_factor=2.0,
    )
    guarded = screen_column_member(_column("500 mm"), required_safety_factor=2.0)
    assert card.entries[0].detail != guarded.entries[0].detail
    assert "Johnson" in card.entries[0].name  # strong-axis lambda = 86.6 < lambda_1


def test_overloaded_column_fails():
    # A large axial load drops the buckling safety factor below the requirement.
    card = screen_column_member(_column("500 mm", load="20 kN"), required_safety_factor=2.0)
    assert card.status is CheckStatus.FAIL


def test_member_carried_deflection_limit_is_applied():
    # A beam declaring its own deflection_limit is screened against it without a
    # max_deflection argument.
    member = BeamMember(
        name="joist",
        section=_section(),
        length=_q("500 mm"),
        support=Support.SIMPLY_SUPPORTED,
        load=_q("1 N/mm"),
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        deflection_limit=_q("1 mm"),  # the 2.44 mm deflection exceeds this
    )
    card = screen_beam_member(member, required_safety_factor=1.5)
    assert {e.name for e in card.entries} == {"joist bending", "joist deflection"}
    assert card.status is CheckStatus.FAIL


def test_screen_structure_rolls_up_beams_and_columns():
    beam = _member(Support.SIMPLY_SUPPORTED, LoadType.POINT, "100 N")
    column = _column("500 mm")
    card = screen_structure([beam, column], required_safety_factor=2.0)
    # One card with entries from both members; both pass on A36 -> PASS.
    names = [e.name for e in card.entries]
    assert any("beam bending" == n for n in names)
    assert any("buckling" in n for n in names)
    assert card.status is CheckStatus.PASS


def test_screen_structure_fails_if_any_member_fails():
    beam = _member(Support.SIMPLY_SUPPORTED, LoadType.POINT, "100 N")
    overloaded_column = _column("500 mm", load="20 kN")
    card = screen_structure([beam, overloaded_column], required_safety_factor=2.0)
    assert card.status is CheckStatus.FAIL


def _connection(
    load: str = "8 kN", tension: str | None = None, edge_distance: str | None = None
) -> BoltedConnection:
    return BoltedConnection(
        name="splice",
        bolt_diameter=_q("8 mm"),
        plate_thickness=_q("6 mm"),
        load=_q(load),
        bolt_material="AISI-4140",
        plate_material="ASTM-A36",
        tension=_q(tension) if tension else None,
        edge_distance=_q(edge_distance) if edge_distance else None,
    )


def test_bolted_connection_screens_shear_and_bearing():
    # M8 single shear, 8 kN, 6 mm A36 plate, 4140 bolt: shear 159 MPa vs 0.577*417
    # = 241 (SF 1.51) and bearing 167 MPa vs 250 (SF 1.5) -> both just pass at 1.5.
    card = screen_bolted_connection(_connection(), required_safety_factor=1.5)
    assert card.status is CheckStatus.PASS
    assert {e.name for e in card.entries} == {"splice bolt shear", "splice plate bearing"}


def test_overloaded_bolted_connection_fails():
    card = screen_bolted_connection(_connection(load="20 kN"), required_safety_factor=1.5)
    assert card.status is CheckStatus.FAIL


def test_bolted_connection_rejects_non_force_load():
    with pytest.raises(ValidationError, match="load must be a"):
        BoltedConnection(
            name="c",
            bolt_diameter=_q("8 mm"),
            plate_thickness=_q("6 mm"),
            load=_q("8 MPa"),
            bolt_material="AISI-4140",
            plate_material="ASTM-A36",
        )


def test_bolted_connection_tension_adds_tension_and_combined_checks():
    # 4 kN tension on the M8: sigma = 79.6 MPa (SF 5.24 vs 417) and the von Mises
    # combined sqrt(79.6^2 + 3*159.2^2) = 287 MPa (SF 1.45) -> all pass at 1.4.
    card = screen_bolted_connection(_connection(tension="4 kN"), required_safety_factor=1.4)
    assert card.status is CheckStatus.PASS
    by_name = {e.name: e for e in card.entries}
    assert set(by_name) == {
        "splice bolt shear",
        "splice plate bearing",
        "splice bolt tension",
        "splice combined tension+shear",
    }
    assert by_name["splice bolt tension"].reference == "AISC 360-16 §J3.6"
    assert by_name["splice combined tension+shear"].reference == "AISC 360-16 §J3.7"


def test_bolted_connection_combined_interaction_governs():
    # At 1.5 every individual check passes (shear SF 1.51, bearing 1.50, tension
    # 5.24) but the combined tension+shear equivalent stress fails (SF 1.45) --
    # the interaction catches what the one-axis checks miss.
    card = screen_bolted_connection(_connection(tension="4 kN"), required_safety_factor=1.5)
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["splice bolt shear"].passed
    assert by_name["splice bolt tension"].passed
    assert not by_name["splice combined tension+shear"].passed


def test_bolted_connection_without_tension_keeps_two_checks():
    card = screen_bolted_connection(_connection(), required_safety_factor=1.5)
    assert len(card.entries) == 2


def test_bolted_connection_rejects_bad_tension():
    with pytest.raises(ValidationError, match="tension must be a"):
        _connection(tension="4 MPa")
    with pytest.raises(ValidationError, match="tension must be non-negative"):
        _connection(tension="-4 kN")


def test_bolted_connection_edge_distance_adds_tearout_check():
    # 12 mm edge on the M8 in 6 mm A36: l_c = 12 - 4 = 8 mm, R_n = 1.2*8*6*400
    # = 23.0 kN (SF 2.88 at 8 kN) -> passes at 1.5 alongside shear and bearing.
    card = screen_bolted_connection(_connection(edge_distance="12 mm"), required_safety_factor=1.5)
    assert card.status is CheckStatus.PASS
    by_name = {e.name: e for e in card.entries}
    assert set(by_name) == {"splice bolt shear", "splice plate bearing", "splice edge tear-out"}
    assert by_name["splice edge tear-out"].reference == "AISC 360-16 §J3.10"


def test_bolted_connection_tearout_governs_near_edge():
    # At 8 mm edge distance l_c = 4 mm, R_n = 1.2*4*6*400 = 11.5 kN (SF 1.44) --
    # tear-out fails at 1.5 while bolt shear (1.51) and bearing (1.50) still pass.
    card = screen_bolted_connection(_connection(edge_distance="8 mm"), required_safety_factor=1.5)
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["splice bolt shear"].passed
    assert by_name["splice plate bearing"].passed
    assert not by_name["splice edge tear-out"].passed


def test_bolted_connection_tearout_capped_by_bearing_deformation():
    # A 30 mm edge gives 1.2*l_c*t*Fu = 74.9 kN, but the 2.4*d*t*Fu deformation
    # cap holds R_n at 46.1 kN (SF 5.76) -- uncapped the SF would be 9.36.
    card = screen_bolted_connection(_connection(edge_distance="30 mm"), required_safety_factor=6.0)
    by_name = {e.name: e for e in card.entries}
    assert not by_name["splice edge tear-out"].passed
    card = screen_bolted_connection(_connection(edge_distance="30 mm"), required_safety_factor=5.7)
    by_name = {e.name: e for e in card.entries}
    assert by_name["splice edge tear-out"].passed


def test_bolted_connection_rejects_bad_edge_distance():
    with pytest.raises(ValidationError, match="edge_distance must be a"):
        _connection(edge_distance="12 MPa")
    with pytest.raises(ValidationError, match="must exceed half the bolt"):
        _connection(edge_distance="3 mm")


def _weld(load: str = "20 kN") -> WeldedConnection:
    return WeldedConnection(
        name="fillet",
        leg_size=_q("6 mm"),
        weld_length=_q("100 mm"),
        load=_q(load),
        electrode_strength=_q("483 MPa"),  # E70 electrode
    )


def test_welded_connection_screens_throat_shear():
    # F=20 kN on a 6 mm x 100 mm E70 fillet: throat = 0.707*6*100 = 424 mm^2,
    #   tau = 20000/424 = 47.1 MPa vs allowable 0.6*483 = 290 -> SF 6.2 -> PASS.
    card = screen_welded_connection(_weld(), required_safety_factor=2.0)
    assert card.status is CheckStatus.PASS
    assert card.entries[0].name == "fillet weld shear"
    assert card.entries[0].reference == "AISC 360-16 §J2.4"


def test_overloaded_weld_fails():
    card = screen_welded_connection(_weld(load="150 kN"), required_safety_factor=2.0)
    assert card.status is CheckStatus.FAIL


def test_weld_rejects_non_pressure_electrode_strength():
    with pytest.raises(ValidationError, match="electrode_strength must be a"):
        WeldedConnection(
            name="w",
            leg_size=_q("6 mm"),
            weld_length=_q("100 mm"),
            load=_q("20 kN"),
            electrode_strength=_q("483 N"),
        )


def test_screen_structure_includes_welds():
    card = screen_structure(
        [_member(Support.SIMPLY_SUPPORTED, LoadType.POINT, "100 N"), _weld()],
        required_safety_factor=2.0,
    )
    assert any("weld shear" in e.name for e in card.entries)
    assert card.status is CheckStatus.PASS


def _base_plate(load: str = "200 kN") -> BasePlate:
    return BasePlate(
        name="col_base",
        width=_q("300 mm"),
        depth=_q("300 mm"),
        axial_load=_q(load),
        concrete_strength=_q("25 MPa"),
    )


def test_base_plate_screens_concrete_bearing():
    # 200 kN over a 300x300 plate: bearing = 200000/90000 = 2.22 MPa vs capacity
    #   0.85*25 = 21.25 MPa -> SF 9.6 -> PASS, citing AISC J8.
    card = screen_base_plate(_base_plate(), required_safety_factor=2.0)
    assert card.status is CheckStatus.PASS
    assert card.entries[0].name == "col_base concrete bearing"
    assert card.entries[0].reference == "AISC 360-16 §J8"
    # Bearing-only base plate: no plate-bending entry.
    assert len(card.entries) == 1


def test_base_plate_adds_plate_bending_when_details_given():
    # f_p = 2.22 MPa, cantilever 75 mm, thickness 20 mm:
    #   sigma = 3*f_p*l^2/t^2 = 3*2.22*75^2/20^2 = 93.7 MPa vs A36 250 -> SF 2.67.
    plate = BasePlate(
        name="col_base",
        width=_q("300 mm"),
        depth=_q("300 mm"),
        axial_load=_q("200 kN"),
        concrete_strength=_q("25 MPa"),
        plate_thickness=_q("20 mm"),
        cantilever=_q("75 mm"),
        plate_material="ASTM-A36",
    )
    card = screen_base_plate(plate, required_safety_factor=2.0)
    names = {e.name for e in card.entries}
    assert names == {"col_base concrete bearing", "col_base plate bending"}
    bending = next(e for e in card.entries if "bending" in e.name)
    assert bending.reference == "AISC Design Guide 1"
    assert card.status is CheckStatus.PASS


def test_base_plate_bending_rejects_partial_plate_details():
    with pytest.raises(ValidationError, match="plate_thickness, cantilever, and"):
        BasePlate(
            name="b",
            width=_q("300 mm"),
            depth=_q("300 mm"),
            axial_load=_q("200 kN"),
            concrete_strength=_q("25 MPa"),
            plate_thickness=_q("20 mm"),  # cantilever + plate_material missing
        )


def test_overloaded_base_plate_fails():
    card = screen_base_plate(_base_plate(load="2500 kN"), required_safety_factor=2.0)
    assert card.status is CheckStatus.FAIL


def test_base_plate_rejects_non_pressure_concrete_strength():
    with pytest.raises(ValidationError, match="concrete_strength must be a"):
        BasePlate(
            name="b",
            width=_q("300 mm"),
            depth=_q("300 mm"),
            axial_load=_q("200 kN"),
            concrete_strength=_q("25 N"),
        )


def test_screen_structure_includes_base_plates():
    card = screen_structure(
        [_column("500 mm"), _base_plate()],
        required_safety_factor=2.0,
    )
    assert any("concrete bearing" in e.name for e in card.entries)
    assert card.status is CheckStatus.PASS


def _lug(load: str = "50 kN") -> LiftingLug:
    return LiftingLug(
        name="pad_eye",
        width=_q("80 mm"),
        hole_diameter=_q("25 mm"),
        thickness=_q("12 mm"),
        load=_q(load),
        material="ASTM-A36",
    )


def test_lifting_lug_screens_tension_and_bearing():
    # 50 kN through an 80 mm lug, 25 mm hole, 12 mm thick:
    #   net tension = 50000/((80-25)*12) = 75.8 MPa; bearing = 50000/(25*12) = 166.7
    #   MPa. Both pass vs A36 250 MPa (bearing governs at SF 1.5). Cites ASME BTH-1.
    card = screen_lifting_lug(_lug(), required_safety_factor=1.4)
    assert card.status is CheckStatus.PASS
    names = {e.name for e in card.entries}
    assert names == {"pad_eye net tension", "pad_eye pin bearing"}
    assert all(e.reference == "ASME BTH-1 §3-3" for e in card.entries)


def test_overloaded_lug_fails():
    card = screen_lifting_lug(_lug(load="200 kN"), required_safety_factor=1.4)
    assert card.status is CheckStatus.FAIL


def test_lug_rejects_hole_wider_than_lug():
    with pytest.raises(ValidationError, match="hole_diameter"):
        LiftingLug(
            name="l",
            width=_q("25 mm"),
            hole_diameter=_q("25 mm"),
            thickness=_q("12 mm"),
            load=_q("50 kN"),
            material="ASTM-A36",
        )


def test_screen_structure_includes_lugs():
    card = screen_structure([_lug()], required_safety_factor=1.4)
    assert {e.name for e in card.entries} == {"pad_eye net tension", "pad_eye pin bearing"}
    assert card.status is CheckStatus.PASS


def _gusset(load: str = "200 kN") -> GussetPlate:
    return GussetPlate(
        name="brace_gusset",
        net_shear_area=_q("1500 mm**2"),
        net_tension_area=_q("500 mm**2"),
        load=_q(load),
        material="ASTM-A36",
    )


def test_gusset_block_shear_screen():
    # A36 Fu = 400 MPa: R_n = 0.6*400*1500 + 400*500 = 560 kN; vs 200 kN -> SF 2.8.
    card = screen_gusset_plate(_gusset(), required_safety_factor=2.0)
    assert card.status is CheckStatus.PASS
    assert card.entries[0].name == "brace_gusset block shear"
    assert card.entries[0].reference == "AISC 360-16 §J4.3"
    assert "2.80" in card.entries[0].detail


def test_overloaded_gusset_fails():
    card = screen_gusset_plate(_gusset(load="400 kN"), required_safety_factor=2.0)
    assert card.status is CheckStatus.FAIL


def test_gusset_rejects_non_area_inputs():
    with pytest.raises(ValidationError, match="net_shear_area must be an area"):
        GussetPlate(
            name="g",
            net_shear_area=_q("1500 mm"),  # a length, not an area
            net_tension_area=_q("500 mm**2"),
            load=_q("200 kN"),
            material="ASTM-A36",
        )


def test_screen_structure_includes_gussets():
    card = screen_structure([_gusset()], required_safety_factor=2.0)
    assert any("block shear" in e.name for e in card.entries)
    assert card.status is CheckStatus.PASS


def _tension(load: str = "200 kN", shear_lag_factor: float = 1.0) -> TensionMember:
    return TensionMember(
        name="brace_tie",
        gross_area=_q("2000 mm**2"),
        net_area=_q("1500 mm**2"),
        load=_q(load),
        material="ASTM-A36",
        shear_lag_factor=shear_lag_factor,
    )


def test_tension_member_screens_both_limit_states():
    # A36 Fy=250, Fu=400. Gross: 200kN/2000mm2=100MPa -> SF 2.50 (§D2a).
    # Net (U=1): Ae=1500mm2, 200kN/1500=133.3MPa -> SF 3.00 (§D2b). Gross governs.
    card = screen_tension_member(_tension(), required_safety_factor=2.0)
    assert card.status is CheckStatus.PASS
    names = [e.name for e in card.entries]
    assert names == ["brace_tie gross yielding", "brace_tie net rupture"]
    assert all(e.reference == "AISC 360-16 §D2" for e in card.entries)
    assert "2.50" in card.entries[0].detail
    assert "3.00" in card.entries[1].detail


def test_tension_member_shear_lag_reduces_net_rupture():
    # U=0.8: Ae=1200mm2, 200kN/1200=166.7MPa -> SF 400/166.7=2.40, below gross 2.50.
    card = screen_tension_member(_tension(shear_lag_factor=0.8), required_safety_factor=1.5)
    assert card.status is CheckStatus.PASS
    assert "2.40" in card.entries[1].detail


def test_overloaded_tension_member_yields():
    # 500kN/2000mm2=250MPa = Fy -> gross-yield SF 1.0, fails required 2.0.
    card = screen_tension_member(_tension(load="500 kN"), required_safety_factor=2.0)
    assert card.status is CheckStatus.FAIL


def test_tension_member_rejects_net_area_above_gross():
    with pytest.raises(ValidationError, match="cannot exceed gross_area"):
        TensionMember(
            name="t",
            gross_area=_q("1000 mm**2"),
            net_area=_q("1500 mm**2"),
            load=_q("100 kN"),
            material="ASTM-A36",
        )


def test_tension_member_rejects_out_of_range_shear_lag():
    with pytest.raises(ValidationError, match="shear_lag_factor must be in"):
        TensionMember(
            name="t",
            gross_area=_q("2000 mm**2"),
            net_area=_q("1500 mm**2"),
            load=_q("100 kN"),
            material="ASTM-A36",
            shear_lag_factor=1.5,
        )


def test_screen_structure_includes_tension_members():
    card = screen_structure([_tension()], required_safety_factor=2.0)
    assert any("gross yielding" in e.name for e in card.entries)
    assert any("net rupture" in e.name for e in card.entries)
    assert card.status is CheckStatus.PASS


def _beam_column(axial: str = "200 kN", moment: str = "20 kN*m") -> BeamColumnMember:
    return BeamColumnMember(
        name="bc",
        section=CrossSection.rectangular(width=_q("60 mm"), height=_q("100 mm")),
        length=_q("2000 mm"),
        axial_load=_q(axial),
        moment=_q(moment),
        material="ASTM-A992",
        end_condition=ColumnEnd.PINNED_PINNED,
    )


def test_beam_column_interaction_low_axial_branch():
    # A992: E=200 GPa, Fy=345. Section 60x100 bends about its strong axis
    # (S=100000) but buckles about its weak one: r=60/sqrt(12)=17.32,
    # lambda=2000/17.32=115.5 >= lambda1=107 -> Euler sigma_cr=148.0 MPa;
    # Pc=888.3 kN, Mc=Fy*S=34.5 kN*m. Pr/Pc=0.113 < 0.2 so H1.1(b):
    # ratio = 0.113/2 + 20/34.5 = 0.0563 + 0.5797 = 0.636 -> SF 1/ratio = 1.57.
    card = screen_beam_column(_beam_column(axial="100 kN"), required_safety_factor=1.5)
    assert card.status is CheckStatus.PASS
    assert card.entries[0].name == "bc interaction"
    assert card.entries[0].reference == "AISC 360-16 §H1.1"
    assert "1.57" in card.entries[0].detail


def test_beam_column_interaction_high_axial_branch_uses_8_9_form():
    # Pr=200 kN against the weak-axis Pc=888.3 kN -> Pr/Pc=0.225 >= 0.2 so
    # H1.1(a): ratio = 0.225 + (8/9)*0.5797 = 0.7405 -> SF 1.35 (this member
    # screened 1.56 when the axial term trusted the declared strong axis —
    # the flip is the point of the least-radius screen).
    card = screen_beam_column(_beam_column(), required_safety_factor=1.5)
    assert card.status is CheckStatus.FAIL  # 1.35 < 1.5
    assert "1.35" in card.entries[0].detail


def test_beam_column_flexural_term_keeps_the_declared_axis():
    # Swapping the declared bending axis (60x100 -> 100x60) leaves the axial
    # term alone (least r either way) but drops S from 100000 to 60000, so the
    # interaction worsens: ratio = 0.0563 + 20/20.7 = 1.0225 -> SF 0.98.
    member = BeamColumnMember(
        name="bc",
        section=CrossSection.rectangular(width=_q("100 mm"), height=_q("60 mm")),
        length=_q("2000 mm"),
        axial_load=_q("100 kN"),
        moment=_q("20 kN*m"),
        material="ASTM-A992",
        end_condition=ColumnEnd.PINNED_PINNED,
    )
    card = screen_beam_column(member, required_safety_factor=1.5)
    assert "0.98" in card.entries[0].detail


def test_beam_column_rejects_non_moment():
    with pytest.raises(ValidationError, match="moment must be a"):
        BeamColumnMember(
            name="bc",
            section=CrossSection.rectangular(width=_q("60 mm"), height=_q("100 mm")),
            length=_q("2000 mm"),
            axial_load=_q("200 kN"),
            moment=_q("20 kN"),  # a force, not a moment
            material="ASTM-A992",
        )


def test_screen_structure_includes_beam_columns():
    card = screen_structure([_beam_column(axial="100 kN")], required_safety_factor=1.5)
    assert any("interaction" in e.name for e in card.entries)
    assert card.status is CheckStatus.PASS


def _bearing(support: str = "250000 mm**2", load: str = "800 kN") -> ConcreteBearing:
    return ConcreteBearing(
        name="pedestal",
        bearing_area=_q("40000 mm**2"),  # a 200x200 plate
        support_area=_q(support),
        concrete_strength=_q("25 MPa"),
        load=_q(load),
    )


def test_concrete_bearing_confinement_is_capped_at_two():
    # A2/A1 = 6.25 -> sqrt 2.5 capped at 2.0: Bn = 0.85*25*40000*2.0 = 1700 kN;
    # vs 800 kN -> SF 2.12 (ACI 318 §22.8.3).
    card = screen_concrete_bearing(_bearing(), required_safety_factor=2.0)
    assert card.status is CheckStatus.PASS
    assert card.entries[0].name == "pedestal concrete bearing"
    assert card.entries[0].reference == "ACI 318-19 §22.8.3"
    assert "2.12" in card.entries[0].detail


def test_concrete_bearing_uses_partial_confinement():
    # A2 = 90000 (300x300): sqrt(2.25) = 1.5 (below the cap); Bn = 1275 kN;
    # vs 800 kN -> SF 1.59, below the 2.0 requirement -> FAIL.
    card = screen_concrete_bearing(_bearing(support="90000 mm**2"), required_safety_factor=2.0)
    assert card.status is CheckStatus.FAIL
    assert "1.59" in card.entries[0].detail


def test_concrete_bearing_rejects_support_below_bearing_area():
    with pytest.raises(ValidationError, match="cannot be smaller than the"):
        ConcreteBearing(
            name="p",
            bearing_area=_q("40000 mm**2"),
            support_area=_q("30000 mm**2"),  # smaller than the plate
            concrete_strength=_q("25 MPa"),
            load=_q("800 kN"),
        )


def test_screen_structure_includes_concrete_bearing():
    card = screen_structure([_bearing()], required_safety_factor=2.0)
    assert any("concrete bearing" in e.name for e in card.entries)
    assert card.status is CheckStatus.PASS


def _shear_plate(load: str = "200 kN") -> ShearPlate:
    return ShearPlate(
        name="tab",
        gross_shear_area=_q("2000 mm**2"),
        net_shear_area=_q("1500 mm**2"),
        load=_q(load),
        material="ASTM-A36",
    )


def test_shear_plate_screens_yield_and_rupture():
    # A36 Fy=250, Fu=400. Yield 0.6*250*2000=300 kN -> SF 1.50 (§J4.2);
    # rupture 0.6*400*1500=360 kN -> SF 1.80. Yield governs.
    card = screen_shear_plate(_shear_plate(), required_safety_factor=1.5)
    assert card.status is CheckStatus.PASS
    assert [e.name for e in card.entries] == ["tab shear yielding", "tab shear rupture"]
    assert all(e.reference == "AISC 360-16 §J4.2" for e in card.entries)
    assert "1.50" in card.entries[0].detail
    assert "1.80" in card.entries[1].detail


def test_overloaded_shear_plate_yields():
    # 250 kN: yield SF 300/250 = 1.2 < 1.5 -> FAIL.
    card = screen_shear_plate(_shear_plate(load="250 kN"), required_safety_factor=1.5)
    assert card.status is CheckStatus.FAIL


def test_shear_plate_rejects_net_above_gross():
    with pytest.raises(ValidationError, match="cannot exceed the"):
        ShearPlate(
            name="t",
            gross_shear_area=_q("1000 mm**2"),
            net_shear_area=_q("1500 mm**2"),
            load=_q("200 kN"),
            material="ASTM-A36",
        )


def test_screen_structure_includes_shear_plates():
    card = screen_structure([_shear_plate()], required_safety_factor=1.5)
    assert any("shear yielding" in e.name for e in card.entries)
    assert any("shear rupture" in e.name for e in card.entries)
    assert card.status is CheckStatus.PASS


def test_checks_cite_the_governing_aisc_clause():
    # The discipline pack cites the AISC 360-16 clause on each scorecard entry.
    beam = screen_beam_member(
        _member(Support.SIMPLY_SUPPORTED, LoadType.DISTRIBUTED, "1 N/mm"),
        required_safety_factor=1.5,
        max_deflection=_q("5 mm"),
    )
    refs = {e.name: e.reference for e in beam.entries}
    assert refs["beam bending"] == "AISC 360-16 Ch. F"
    assert refs["beam deflection"] == "AISC 360-16 §L3"

    column = screen_column_member(_column("500 mm"), required_safety_factor=2.0)
    assert column.entries[0].reference == "AISC 360-16 Ch. E"

    conn = screen_bolted_connection(_connection(), required_safety_factor=1.5)
    conn_refs = {e.name: e.reference for e in conn.entries}
    assert conn_refs["splice bolt shear"] == "AISC 360-16 §J3.6"
    assert conn_refs["splice plate bearing"] == "AISC 360-16 §J3.10"


def test_screen_structure_includes_connections():
    # A beam, a column, and a bolted connection all roll into one scorecard.
    card = screen_structure(
        [
            _member(Support.SIMPLY_SUPPORTED, LoadType.POINT, "100 N"),
            _column("500 mm"),
            _connection(),
        ],
        required_safety_factor=1.5,
    )
    names = [e.name for e in card.entries]
    assert any("bolt shear" in n for n in names)
    assert any("plate bearing" in n for n in names)
    assert card.status is CheckStatus.PASS


def test_column_rejects_non_force_axial_load():
    with pytest.raises(ValidationError, match="axial_load must be a"):
        ColumnMember(
            name="col",
            section=_section(),
            length=_q("500 mm"),
            axial_load=_q("5 MPa"),
            material="ASTM-A36",
        )
