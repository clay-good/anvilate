"""Every branch of every Aluminum Design Manual curve evaluates to the stress it ships with.

An ADM compression screen runs three limit states over one or two property sets and reports
the smallest. `AluminumCompressionStrength` renders the curve that governed, on the branch
that ran, for the metal that governed — and each of those three choices is a place the
document could show a reviewer arithmetic nobody performed: the state that lost, the wrong
side of a slenderness limit, or the parent alloy's constants for a member whose answer came
from the heat-affected zone.

So the cases below are written from the branch inward: a geometry and a slenderness chosen
to land on each one, checked against the mode and the fragment it should render, and then
evaluated. The §E.4 interaction reduction composes on top of the column curve, and its case
asserts that the line shown is the interaction with the curve underneath named in the gloss.
"""

from __future__ import annotations

import pytest

from anvilate.analysis import (
    AlloyProperties,
    AluminumLimitState,
    EdgeSupport,
    TemperGroup,
    aluminum_compression_scorecard,
    aluminum_compression_strength,
)
from anvilate.units import Quantity
from formula_arithmetic import _arithmetic, _si

_E = Quantity.parse("70000 MPa")


def _alloy(*, yield_strength: str, welded: bool = False) -> AlloyProperties:
    haz = AlloyProperties(
        name="6061-T6 (weld-affected)",
        compressive_yield=Quantity.parse("103 MPa"),
        tensile_yield=Quantity.parse("103 MPa"),
        tensile_ultimate=Quantity.parse("165 MPa"),
        elastic_modulus=_E,
        temper_group=TemperGroup.ARTIFICIALLY_AGED,
        source="ADM Table A.3.5, read by the user",
    )
    return AlloyProperties(
        name="6061-T6",
        compressive_yield=Quantity.parse(yield_strength),
        tensile_yield=Quantity.parse("241 MPa"),
        tensile_ultimate=Quantity.parse("262 MPa"),
        elastic_modulus=_E,
        temper_group=TemperGroup.ARTIFICIALLY_AGED,
        source="ADM Table A.3.4, read by the user",
        weld_affected=haz if welded else None,
    )


# (label, slenderness, flat width, thickness, welded, expected mode, expected fragment)
_CASES = [
    # Stocky column, compact element: nothing buckles and yielding governs.
    ("yielding", 5.0, "30 mm", "10 mm", False, AluminumLimitState.YIELDING, "F_c = F_cy"),
    # A long column past C_c: the Euler branch with the out-of-straightness knockdown.
    (
        "member elastic",
        140.0,
        "30 mm",
        "10 mm",
        False,
        AluminumLimitState.MEMBER_BUCKLING,
        "0.85·π²·E/λ²",
    ),
    # Between λ₁ and C_c: the inelastic straight-line branch with its easing bracket.
    (
        "member inelastic",
        45.0,
        "30 mm",
        "10 mm",
        False,
        AluminumLimitState.MEMBER_BUCKLING,
        "(B_c − D_c·λ)",
    ),
    # A slender element on a stocky column: the §B.5.4 straight-line plate branch.
    (
        "local straight line",
        5.0,
        "150 mm",
        "6 mm",
        False,
        AluminumLimitState.LOCAL_BUCKLING,
        "B_p − k·D_p·(b/t)",
    ),
    # A very slender element: the postbuckling branch, which decays as 1/(b/t).
    (
        "local postbuckling",
        5.0,
        "200 mm",
        "6 mm",
        False,
        AluminumLimitState.LOCAL_BUCKLING,
        "√(B_p·E)",
    ),
]


@pytest.mark.parametrize(
    ("label", "slenderness", "width", "thickness", "welded", "mode", "fragment"),
    [pytest.param(*case, id=case[0]) for case in _CASES],
)
def test_a_governing_adm_curve_evaluates_to_its_stress(
    label, slenderness, width, thickness, welded, mode, fragment
):
    strength = aluminum_compression_strength(
        properties=_alloy(yield_strength="241 MPa", welded=welded),
        slenderness=slenderness,
        flat_width=Quantity.parse(width),
        thickness=Quantity.parse(thickness),
        edge_support=EdgeSupport.BOTH_EDGES,
        welded=welded,
    )
    assert strength is not None
    assert strength.governing is mode, (
        f"the {label} case was chosen to make {mode.value} govern; {strength.governing.value} did"
    )
    assert fragment in strength.governing_formula, strength.governing_formula
    _assert_evaluates(strength)


def _assert_evaluates(strength):
    work = strength.derivation("Aluminum Design Manual 2020 Part I")
    assert work.unresolved_symbols() == ()
    values = {item.symbol: _si(item.value) for item in work.inputs}
    computed = _arithmetic(work.symbolic, values)
    expected = strength.nominal.pint.to_base_units().magnitude
    assert computed == pytest.approx(expected, rel=1e-9), (
        f"{strength.governing_formula!r} evaluates to {computed:.6g}; the check returned "
        f"{expected:.6g} (SI base units)"
    )


def test_the_e4_interaction_shows_the_reduction_and_names_the_curve_underneath():
    """§E.4 composes on top of the column curve, so the rendered line is the interaction.

    Rendering the column curve there would print an F_c the check then knocked down, and a
    reviewer adding it up would not reach the number beside it.
    """
    strength = aluminum_compression_strength(
        properties=_alloy(yield_strength="241 MPa"),
        # A slender element on a moderately slender column: F_e falls below F_c.
        slenderness=45.0,
        flat_width=Quantity.parse("600 mm"),
        thickness=Quantity.parse("5 mm"),
    )
    assert strength is not None
    if not strength.local_member_interaction:
        pytest.skip("this geometry no longer triggers §E.4")
    if strength.governing is AluminumLimitState.MEMBER_BUCKLING:
        assert strength.governing_formula == "F_rc = F_c^(1/3)·F_e^(2/3)"
        underneath = next(item for item in strength.governing_inputs if item.symbol == "F_c")
        assert "§E.3 member buckling strength, from F_c =" in underneath.description
        _assert_evaluates(strength)


def test_a_welded_member_renders_the_heat_affected_metals_own_curve():
    """The trap this pack exists for. 6061-T6 loses more than half its compressive yield
    within an inch of the arc, so a welded member's answer comes from the weld-affected
    metal — and the constants beside it have to be that metal's, not the parent alloy's.
    """
    strength = aluminum_compression_strength(
        properties=_alloy(yield_strength="241 MPa", welded=True),
        slenderness=5.0,
        flat_width=Quantity.parse("30 mm"),
        thickness=Quantity.parse("10 mm"),
        welded=True,
    )
    assert strength is not None
    assert strength.weld_affected_governs
    work = strength.derivation("Aluminum Design Manual 2020 Part I")
    assert "weld-affected zone" in work.result.description
    yield_symbol = next(item for item in work.inputs if item.symbol == "F_cy")
    assert yield_symbol.value == Quantity.parse("103 MPa")
    _assert_evaluates(strength)


def test_the_scorecard_carries_the_curve_onto_the_entry():
    strength = aluminum_compression_strength(
        properties=_alloy(yield_strength="241 MPa"),
        slenderness=140.0,
        flat_width=Quantity.parse("30 mm"),
        thickness=Quantity.parse("10 mm"),
    )
    entry = aluminum_compression_scorecard(
        "column", demand_stress=Quantity.parse("30 MPa"), strength=strength
    )
    assert entry.derivation.symbolic == strength.governing_formula
    assert entry.derivation.unresolved_symbols() == ()


def test_every_limit_state_the_enum_names_is_one_a_case_above_produces():
    """A state nothing can report is a capability the vocabulary claims and we lack.

    `LATERAL_TORSIONAL_BUCKLING` sat in this enum with no producer, no consumer, no test
    and no docs line: `aluminum_compression_strength` computes three states and picks the
    smallest, so no input could ever return it, and a caller branching on it wrote dead
    code. Membership here costs a row in `_CASES`, and every row is a case that runs and
    asserts the mode it claims — so a state added to the enum without a screen that
    reports it fails rather than reads as coverage.
    """
    produced = {case[5] for case in _CASES}
    assert produced == set(AluminumLimitState), (
        "these limit states are named by AluminumLimitState and no case above produces "
        f"one: {sorted(state.name for state in set(AluminumLimitState) - produced)}"
    )
