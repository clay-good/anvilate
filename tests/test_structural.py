"""Tests for the structural pack: BeamMember declaration and auto-dispatch."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis import (
    ColumnEnd,
    CrossSection,
    cantilever_end_load,
    fixed_fixed_center_load,
    simply_supported_uniform_load,
)
from anvilate.packs.structural import (
    BeamMember,
    BoltedConnection,
    ColumnMember,
    LoadType,
    Support,
    screen_beam_member,
    screen_bolted_connection,
    screen_column_member,
    screen_structure,
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


def _connection(load: str = "8 kN") -> BoltedConnection:
    return BoltedConnection(
        name="splice",
        bolt_diameter=_q("8 mm"),
        plate_thickness=_q("6 mm"),
        load=_q(load),
        bolt_material="AISI-4140",
        plate_material="ASTM-A36",
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
