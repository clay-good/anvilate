"""Load combinations: ASCE 7-22 generation, envelope, and governing combination."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.loads import (
    CombinationEvidence,
    CombinationSet,
    LoadCombination,
    LoadNature,
    asce7_asd_basic,
    asce7_asd_seismic,
    asce7_lrfd_basic,
    asce7_lrfd_seismic,
    combination_evidence,
    combination_scorecard,
)
from anvilate.scorecard import CheckStatus

E = LoadNature.SEISMIC

D = LoadNature.DEAD
L = LoadNature.LIVE
Lr = LoadNature.ROOF_LIVE
S = LoadNature.SNOW
R = LoadNature.RAIN
W = LoadNature.WIND


def _by_name(cs: CombinationSet) -> dict[str, LoadCombination]:
    return {c.name: c for c in cs.combinations}


# -- generated sets match the published equations ------------------------------


def test_lrfd_set_has_every_basic_combination_expanded_over_the_roof_companion():
    cs = asce7_lrfd_basic()
    # 1 + 3 (combo 2) + 3 + 3 (combo 3's two forms) + 3 (combo 4) + 1 (combo 5) = 14.
    assert len(cs.combinations) == 14
    by_name = _by_name(cs)
    # Combination 1: 1.4D.
    assert dict(by_name["LRFD 1"].factors) == {D: 1.4}
    # Combination 2 with snow companion: 1.2D + 1.6L + 0.5S.
    assert dict(by_name["LRFD 2 [S]"].factors) == {D: 1.2, L: 1.6, S: 0.5}
    # Combination 5, the counteracting case: 0.9D + 1.0W.
    assert dict(by_name["LRFD 5"].factors) == {D: 0.9, W: 1.0}
    # Every combination cites the clause.
    assert all(c.citation == "ASCE 7-22 §2.3.1" for c in cs.combinations)


def test_asd_set_matches_the_published_basic_combinations():
    cs = asce7_asd_basic()
    # 1 + 1 + 3 + 3 + 1 + 3 + 1 = 13.
    assert len(cs.combinations) == 13
    by_name = _by_name(cs)
    assert dict(by_name["ASD 1"].factors) == {D: 1.0}
    assert dict(by_name["ASD 2"].factors) == {D: 1.0, L: 1.0}
    # Combination 6 carries the 0.75 × 0.6W = 0.45W wind term.
    assert dict(by_name["ASD 6 [R]"].factors) == {D: 1.0, L: 0.75, W: 0.45, R: 0.75}
    # Combination 7, the counteracting case: 0.6D + 0.6W.
    assert dict(by_name["ASD 7"].factors) == {D: 0.6, W: 0.6}
    assert all(c.citation == "ASCE 7-22 §2.4.1" for c in cs.combinations)


# -- evaluation, envelope, governing -------------------------------------------


def test_envelope_and_governing_pick_the_largest_factored_demand():
    # D=20, L=50, Lr=15, W=10: the live-load combination 2 [Lr] governs.
    #   LRFD 2 [Lr] = 1.2*20 + 1.6*50 + 0.5*15 = 111.5, the maximum.
    loads = {D: 20.0, L: 50.0, Lr: 15.0, W: 10.0}
    cs = asce7_lrfd_basic()
    governing, demand = cs.governing(loads)
    assert governing.name == "LRFD 2 [Lr]"
    assert demand == pytest.approx(111.5)
    assert cs.envelope(loads) == pytest.approx(111.5)


def test_evaluate_treats_an_unsupplied_nature_as_zero():
    # No wind supplied: the wind combinations still evaluate, wind contributing 0.
    loads = {D: 20.0, L: 50.0}
    lrfd5 = _by_name(asce7_lrfd_basic())["LRFD 5"]  # 0.9D + 1.0W
    assert lrfd5.evaluate(loads) == pytest.approx(0.9 * 20.0)


def test_counteracting_wind_governs_an_uplift_check():
    # Wind supplied as a net uplift (negative): the 0.9D + 1.0W combination nets the
    # most upward, so the minimizing governing combination is the uplift case — the
    # one a gravity-only check would miss.
    loads = {D: 100.0, W: -150.0}
    cs = asce7_lrfd_basic()
    governing, demand = cs.governing(loads, minimize=True)
    assert governing.name == "LRFD 5"
    assert demand == pytest.approx(0.9 * 100.0 - 150.0)  # -60: net uplift
    # The strength (maximizing) envelope is a different, downward combination.
    assert cs.governing(loads)[1] > 0


def test_custom_combination_set_and_rendering():
    custom = CombinationSet(
        basis="custom",
        combinations=(
            LoadCombination(name="C1", factors={D: 1.25, L: 1.5}, citation="project spec §4.2"),
        ),
    )
    assert custom.envelope({D: 10.0, L: 20.0}) == pytest.approx(1.25 * 10 + 1.5 * 20)
    assert str(custom.combinations[0]) == "C1: 1.25D + 1.5L"


def test_empty_set_has_no_governing_combination():
    with pytest.raises(ValueError, match="empty combination set"):
        CombinationSet(basis="none", combinations=()).governing({D: 1.0})


# -- seismic combinations ------------------------------------------------------


def test_lrfd_seismic_folds_ev_into_the_dead_factor_and_carries_eh():
    # S_DS = 1.0, rho = 1.3: Ev = 0.2*S_DS folds into D, Eh = rho on E.
    cs = asce7_lrfd_seismic(s_ds=1.0, redundancy=1.3)
    by_name = _by_name(cs)
    # 2 signs x (combo 6 + combo 7) = 4 combinations.
    assert len(cs.combinations) == 4
    six = by_name["LRFD 6 (+E)"].factors
    assert six[D] == pytest.approx(1.4)  # 1.2 + 0.2*1.0
    assert six[E] == pytest.approx(1.3)
    assert six[L] == pytest.approx(1.0)
    assert six[S] == pytest.approx(0.2)
    seven = by_name["LRFD 7 (-E)"].factors
    assert seven[D] == pytest.approx(0.7)  # 0.9 - 0.2*1.0
    assert seven[E] == pytest.approx(-1.3)
    assert all(c.citation == "ASCE 7-22 §2.3.6" for c in cs.combinations)


def test_asd_seismic_coefficients_and_count():
    cs = asce7_asd_seismic(s_ds=1.0, redundancy=1.0)
    # 2 signs x (combo 8 + 3 roof variants of combo 9 + combo 10) = 10.
    assert len(cs.combinations) == 10
    by_name = _by_name(cs)
    assert by_name["ASD 8 (+E)"].factors[D] == pytest.approx(1.14)  # 1.0 + 0.14
    assert by_name["ASD 8 (+E)"].factors[E] == pytest.approx(0.7)
    assert by_name["ASD 9 (+E) [S]"].factors[D] == pytest.approx(1.105)  # 1.0 + 0.105
    assert by_name["ASD 9 (+E) [S]"].factors[E] == pytest.approx(0.525)
    assert by_name["ASD 10 (+E)"].factors[D] == pytest.approx(0.46)  # 0.6 - 0.14
    assert all(c.citation == "ASCE 7-22 §2.4.5" for c in cs.combinations)


def test_seismic_reversal_puts_a_gravity_column_into_net_tension():
    # A braced-frame column: 50 gravity compression, 200 seismic axial. Under the
    # reduced-dead combination with reversed horizontal seismic it goes into net
    # tension — the load reversal a gravity-only check never sees.
    loads = {D: 50.0, E: 200.0}
    cs = asce7_lrfd_seismic(s_ds=1.0, redundancy=1.3)
    governing, demand = cs.governing(loads, minimize=True)
    assert governing.name == "LRFD 7 (-E)"
    assert demand == pytest.approx(0.7 * 50.0 - 1.3 * 200.0)  # 35 - 260 = -225
    # The compression envelope is a different, positive combination.
    assert cs.governing(loads)[1] > 0


# -- scorecard surfacing -------------------------------------------------------


def test_combination_scorecard_screens_capacity_and_names_the_combination():
    # Envelope demand 111.5 (LRFD 2 [Lr]); a 130 capacity clears it at SF 1.166.
    loads = {D: 20.0, L: 50.0, Lr: 15.0, W: 10.0}
    entry = combination_scorecard(
        "beam bending",
        combinations=asce7_lrfd_basic(),
        loads=loads,
        capacity=130.0,
        required=1.5,
    )
    assert entry.status is CheckStatus.FAIL  # 1.166 < 1.5
    assert entry.safety_factor == pytest.approx(130.0 / 111.5, rel=1e-9)
    # The controlling combination and its citation are on the entry, not hidden.
    assert "LRFD 2 [Lr]" in entry.detail
    assert entry.reference == "ASCE 7-22 §2.3.1"


def test_combination_scorecard_uplift_uses_the_counteracting_combination():
    # Net uplift: capacity is the hold-down resistance vs the minimizing combination.
    loads = {D: 100.0, W: -150.0}
    entry = combination_scorecard(
        "hold-down uplift",
        combinations=asce7_lrfd_basic(),
        loads=loads,
        capacity=80.0,
        required=1.5,
        minimize=True,
    )
    # |demand| = |0.9*100 - 150| = 60; SF = 80/60 = 1.33 -> FAIL against 1.5.
    assert entry.safety_factor == pytest.approx(80.0 / 60.0, rel=1e-9)
    assert entry.status is CheckStatus.FAIL
    assert "LRFD 5" in entry.detail


def test_combination_scorecard_governs_by_magnitude_not_by_sign() -> None:
    """Selection was signed while the safety factor was magnitude, and they disagreed.

    A set holding gravity and a larger uplift picked the small positive demand and
    reported PASS, never looking at the uplift. Pure uplift was worse: every gravity
    combination evaluated to exactly 0, the signed maximum picked one, and a zero demand
    short-circuited to an INFINITE safety factor -- a PASS produced without the criterion
    being evaluated at all.
    """
    combinations = asce7_asd_basic()

    # 100 kN of dead against 800 kN of wind uplift. ASD 7 (0.6D + 0.6W) reaches -420 kN
    # against a 200 kN capacity; the old signed-max path reported the 100 kN and passed.
    entry = combination_scorecard(
        "holddown",
        combinations=combinations,
        loads={LoadNature.DEAD: 100_000.0, LoadNature.WIND: -800_000.0},
        capacity=200_000.0,
        required=1.5,
    )
    assert entry.status is CheckStatus.FAIL
    assert entry.safety_factor == pytest.approx(200_000.0 / 420_000.0, rel=1e-9)
    assert "ASD 7" in entry.detail
    # The demand is still reported signed, so the direction that governs stays visible.
    assert "-420000" in entry.detail

    # Pure uplift, no dead load: the degenerate infinite-safety-factor pass.
    anchor = combination_scorecard(
        "anchor tension",
        combinations=combinations,
        loads={LoadNature.WIND: -500_000.0},
        capacity=50_000.0,
        required=2.0,
    )
    assert anchor.status is CheckStatus.FAIL
    assert anchor.safety_factor == pytest.approx(50_000.0 / 300_000.0, rel=1e-9)

    # Ordinary gravity is unchanged -- the magnitude and the signed maximum agree there.
    gravity = combination_scorecard(
        "beam",
        combinations=combinations,
        loads={LoadNature.DEAD: 100_000.0, LoadNature.LIVE: 200_000.0},
        capacity=600_000.0,
        required=1.5,
    )
    assert gravity.status is CheckStatus.PASS
    assert gravity.safety_factor == pytest.approx(2.0, rel=1e-9)

    # by_magnitude is opt-in on the set itself; the plain envelope keeps signed semantics.
    uplift_loads = {LoadNature.DEAD: 100_000.0, LoadNature.WIND: -800_000.0}
    assert combinations.governing(uplift_loads)[1] == pytest.approx(100_000.0, rel=1e-9)
    assert combinations.governing(uplift_loads, by_magnitude=True)[1] == pytest.approx(
        -420_000.0, rel=1e-9
    )


def test_a_zero_demand_is_not_evaluated_rather_than_an_infinite_pass() -> None:
    """A demand of zero used to short-circuit to an INFINITE safety factor, i.e. PASS.

    ``LoadNature`` is optional on a load case, so a spec that declares a real load and
    forgets to classify it arrives here with an empty mapping; every combination then
    sums to zero and the division returned inf. That is not a criterion that was
    evaluated and passed -- it is one with nothing to evaluate.
    """
    combos = asce7_lrfd_basic()
    for loads in ({}, {D: 0.0}, {D: 0.0, L: 0.0}):
        entry = combination_scorecard(
            "lug", combinations=combos, loads=loads, capacity=1000.0, required=2.0
        )
        assert entry.status is CheckStatus.NOT_EVALUATED
        assert not entry.passed
        assert entry.safety_factor is None
        assert "nature" in entry.detail
    # A real classified load still screens normally, in both directions.
    fails = combination_scorecard(
        "lug", combinations=combos, loads={D: 50_000.0}, capacity=1000.0, required=2.0
    )
    assert fails.status is CheckStatus.FAIL
    assert fails.safety_factor == pytest.approx(1000.0 / (1.4 * 50_000.0))
    passes = combination_scorecard(
        "lug", combinations=combos, loads={D: 100.0}, capacity=1000.0, required=2.0
    )
    assert passes.status is CheckStatus.PASS
    assert passes.safety_factor == pytest.approx(1000.0 / (1.4 * 100.0))


# --- a demand summed from part of the declared loads ----------------------------------
#
# `combination_loads()` skips a load case that carries a force and no nature, and every
# combination treats a nature nobody supplied as zero. Those two together turn a forgotten
# classification into a smaller demand and a comfortable PASS, with nothing in the entry
# saying a load was left out.


def test_an_unclassified_load_case_stops_the_check_before_a_number_is_computed():
    combos = asce7_lrfd_basic()
    # 10 kN classified, 200 kN not. The subset demand is 14 kN against a 40 kN capacity.
    subset = combination_scorecard(
        "tie", combinations=combos, loads={D: 10_000.0}, capacity=40_000.0, required=2.0
    )
    assert subset.status is CheckStatus.PASS, "this is the silent green, shown before it is shut"

    guarded = combination_scorecard(
        "tie",
        combinations=combos,
        loads={D: 10_000.0},
        capacity=40_000.0,
        required=2.0,
        unclassified=("lateral thrust",),
    )
    assert guarded.status is CheckStatus.NOT_EVALUATED
    assert guarded.safety_factor is None
    assert "lateral thrust" in guarded.detail


def test_the_guard_fires_even_when_the_subset_demand_would_have_failed():
    """The number is not this part's demand either way, so it is not reported as a verdict.

    Reporting FAIL here would be right by accident, and would go on being reported after
    the missing case turned it into a pass.
    """
    entry = combination_scorecard(
        "tie",
        combinations=asce7_lrfd_basic(),
        loads={D: 100_000.0},
        capacity=1_000.0,
        required=2.0,
        unclassified=("lateral thrust",),
    )
    assert entry.status is CheckStatus.NOT_EVALUATED


def test_a_fully_classified_check_is_unaffected():
    entry = combination_scorecard(
        "tie",
        combinations=asce7_lrfd_basic(),
        loads={D: 10_000.0},
        capacity=40_000.0,
        required=2.0,
        unclassified=(),
    )
    assert entry.status is CheckStatus.PASS
    assert entry.safety_factor == pytest.approx(40_000.0 / (1.4 * 10_000.0))


# --- the evidence names the combination the check screened against --------------------


@pytest.mark.parametrize(
    "loads",
    [
        {D: 10_000.0},
        {D: 10_000.0, W: -60_000.0},  # uplift governs by magnitude, not by sign
        {D: 10_000.0, L: 5_000.0, S: 2_000.0},
        {D: 1.0, W: -1.0},
    ],
)
@pytest.mark.parametrize("minimize", [False, True])
def test_the_evidence_cannot_name_a_different_combination_from_the_one_screened(loads, minimize):
    """Two copies of the selection rule would be two places for it to drift.

    The scorecard picks by magnitude and the bundle would be free to pick by sign; on the
    uplift case those are different combinations, and the bundle would then cite a clause
    the check never used.
    """
    combos = asce7_lrfd_basic()
    entry = combination_scorecard(
        "tie",
        combinations=combos,
        loads=loads,
        capacity=1e9,
        required=2.0,
        minimize=minimize,
    )
    evidence = combination_evidence(combos, loads, minimize=minimize)
    assert evidence.governing in entry.detail
    assert entry.reference == evidence.citation


def test_the_drift_test_is_looking_at_a_case_where_sign_and_magnitude_disagree():
    """Otherwise the parametrisation above would agree for a reason that is not the rule."""
    combos = asce7_lrfd_basic()
    loads = {D: 10_000.0, W: -60_000.0}
    by_sign, _ = combos.governing(loads)
    by_magnitude, _ = combos.governing(loads, by_magnitude=True)
    assert by_sign.name != by_magnitude.name


# --- the evidence record --------------------------------------------------------------


def test_evidence_status_is_a_verdict_about_whether_a_combination_can_be_named():
    combos = asce7_lrfd_basic()
    named = combination_evidence(combos, {D: 10_000.0})
    assert named.status is CheckStatus.PASS
    assert named.governing in named.detail()

    partial = combination_evidence(combos, {D: 10_000.0}, unclassified=("lateral thrust",))
    assert partial.status is CheckStatus.NOT_EVALUATED
    assert "lateral thrust" in partial.detail()

    nothing = combination_evidence(combos, {})
    assert nothing.status is CheckStatus.NOT_EVALUATED
    assert "zero demand" in nothing.detail()


def test_evidence_refuses_a_non_finite_demand():
    with pytest.raises(ValidationError, match="not a finite"):
        CombinationEvidence(
            basis="ASCE 7-22 LRFD (strength)",
            governing="LRFD 1",
            citation="ASCE 7-22 §2.3.1",
            demand_newtons=float("nan"),
        )


@pytest.mark.parametrize("field", ["basis", "governing", "citation"])
def test_evidence_refuses_a_blank_identifier(field):
    kwargs = {
        "basis": "ASCE 7-22 LRFD (strength)",
        "governing": "LRFD 1",
        "citation": "ASCE 7-22 §2.3.1",
        "demand_newtons": 14_000.0,
    }
    with pytest.raises(ValidationError, match=f"must state its {field}"):
        CombinationEvidence(**{**kwargs, field: "  "})
