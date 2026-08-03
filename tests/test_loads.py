"""Load combinations: ASCE 7-22 generation, envelope, and governing combination."""

from __future__ import annotations

import pytest

from anvilate.loads import (
    CombinationSet,
    LoadCombination,
    LoadNature,
    asce7_asd_basic,
    asce7_lrfd_basic,
    combination_scorecard,
)
from anvilate.scorecard import CheckStatus

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
