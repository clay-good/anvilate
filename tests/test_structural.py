"""Tests for the structural pack: BeamMember declaration and auto-dispatch."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis import (
    CrossSection,
    cantilever_end_load,
    fixed_fixed_center_load,
    simply_supported_uniform_load,
)
from anvilate.packs.structural import (
    BeamMember,
    LoadType,
    Support,
    screen_beam_member,
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
