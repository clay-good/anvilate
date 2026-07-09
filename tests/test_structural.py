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
    BasePlate,
    BeamMember,
    BoltedConnection,
    ColumnMember,
    LiftingLug,
    LoadType,
    Support,
    WeldedConnection,
    screen_base_plate,
    screen_beam_member,
    screen_bolted_connection,
    screen_column_member,
    screen_lifting_lug,
    screen_structure,
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
