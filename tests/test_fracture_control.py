"""Fracture-control candidates against NASA-STD-5019A w/Change 4's numeric conditions.

Each threshold is the standard's own: K_Ic/F_ty ≥ 1.66 √mm (0.33 √in, which agree:
0.33·√25.4 = 1.663), net-section stress strictly below 30% of ultimate, four lifetimes,
stored energy below 19,307 J (14,240 ft-lb: 14,240 × 1.35582 = 19,307), and the 152 and
304 kPa (22 and 44 psi) MDP bands. Each is tested on both sides of its edge.
"""

from __future__ import annotations

from datetime import date

import pytest

from anvilate.fracture_control import (
    ConditionState,
    LifeMethod,
    low_risk_metallic_candidate,
    sealed_container_candidate,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _mpa(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="MPa")


def _part(**overrides: object):
    fields: dict[str, object] = {
        "part": "bracket 12",
        "fracture_toughness": Quantity(magnitude=29.0, unit="MPa*m**0.5"),
        "yield_strength": _mpa(276.0),
        "ultimate_strength": _mpa(310.0),
        "net_section_stress": _mpa(80.0),
        "cracking_sensitive": False,
        "lifetimes_shown": 4.0,
        "life_method": LifeMethod.FATIGUE,
        "additively_manufactured": False,
        "weld_or_casting_without_inspection_data": False,
    } | overrides
    return low_risk_metallic_candidate(**fields)  # type: ignore[arg-type]


def _state(candidate, clause_fragment: str) -> ConditionState:
    (condition,) = [c for c in candidate.conditions if clause_fragment in c.condition]
    return condition.state


def test_the_metric_and_english_thresholds_agree():
    assert 0.33 * 25.4**0.5 == pytest.approx(1.66, abs=0.005)
    assert 14_240 * 1.3558179483 == pytest.approx(19_307, abs=0.5)


def test_a_bracket_meeting_every_condition_is_a_candidate_awaiting_acceptance():
    candidate = _part()
    # K_Ic/F_ty = 29 × √1000/276 = 3.32 √mm; 80/310 = 25.8%
    assert candidate.is_candidate and candidate.classification is None
    assert "candidate for the low-risk part route (§6.2.5.a), awaiting RFCB acceptance" in str(
        candidate
    )
    accepted = candidate.accept(accepted_by="J. Rivera, RFCB chair", accepted_on=date(2026, 10, 17),
                                record="FCSR rev B, item 14")  # fmt: skip
    assert accepted.classification == "non-fracture-critical"
    assert "accepted by J. Rivera, RFCB chair on 2026-10-17" in str(accepted)


@pytest.mark.parametrize(("stress", "state"), [(92.9, ConditionState.MET),
                                               (93.0, ConditionState.NOT_MET)])  # fmt: skip
def test_net_section_stress_must_be_strictly_below_30_percent(stress, state):
    # 30% of 310 MPa is 93.0 MPa, and "less than" excludes it
    assert _state(_part(net_section_stress=_mpa(stress)), "net-section") is state


@pytest.mark.parametrize(("k", "state"), [(14.6, ConditionState.MET),
                                          (14.4, ConditionState.NOT_MET)])  # fmt: skip
def test_the_toughness_ratio_edge(k, state):
    # 1.66 √mm × 276 MPa = 458.2 MPa√mm = 14.49 MPa√m
    candidate = _part(fracture_toughness=Quantity(magnitude=k, unit="MPa*m**0.5"))
    assert _state(candidate, "K_Ic/F_ty") is state


def test_fewer_than_four_lifetimes_is_not_a_candidate():
    candidate = _part(lifetimes_shown=3.9, life_method=LifeMethod.DAMAGE_TOLERANCE)
    assert not candidate.is_candidate
    assert "0.127 mm (0.005 in) crack" in str(candidate)


def test_additive_manufacture_closes_the_route():
    candidate = _part(additively_manufactured=True)
    assert _state(candidate, "additively") is ConditionState.NOT_MET
    assert "not a candidate" in str(candidate)


def test_an_undeclared_input_is_not_evaluated_and_not_a_candidate():
    candidate = _part(cracking_sensitive=None, lifetimes_shown=None)
    assert _state(candidate, "EAC") is ConditionState.NOT_EVALUATED
    assert _state(candidate, "lifetimes") is ConditionState.NOT_EVALUATED
    assert not candidate.is_candidate


def test_a_non_candidate_cannot_be_accepted():
    with pytest.raises(ValueError, match="no candidate classification to accept"):
        _part(additively_manufactured=True).accept(
            accepted_by="anyone", accepted_on=date(2026, 1, 1), record="none"
        )


def _container(**overrides: object):
    fields: dict[str, object] = {
        "part": "camera housing",
        "stored_energy": Quantity(magnitude=2_000.0, unit="J"),
        "maximum_design_pressure": Quantity(magnitude=101.0, unit="kPa"),
        "hazardous_contents": False,
        "leak_before_burst": True,
    } | overrides
    return sealed_container_candidate(**fields)  # type: ignore[arg-type]


def test_a_low_pressure_sealed_container_is_a_candidate():
    assert _container().is_candidate


@pytest.mark.parametrize(("energy", "ok"), [(19_306.0, True), (19_307.0, False)])
def test_stored_energy_must_be_below_19307_joules(energy, ok):
    candidate = _container(stored_energy=Quantity(magnitude=energy, unit="J"))
    assert candidate.is_candidate is ok


def test_the_middle_band_needs_burst_margin_or_proof():
    mid = Quantity(magnitude=250.0, unit="kPa")
    assert not _container(maximum_design_pressure=mid).is_candidate  # undeclared
    assert _container(maximum_design_pressure=mid, proof_test_factor=1.5).is_candidate
    assert not _container(maximum_design_pressure=mid, proof_test_factor=1.4).is_candidate
    assert _container(maximum_design_pressure=mid, burst_margin_at_2_5_mdp=True).is_candidate


def test_above_304_kpa_the_route_is_closed():
    high = Quantity(magnitude=44.5, unit="psi")  # 306.8 kPa
    candidate = _container(maximum_design_pressure=high, proof_test_factor=2.0)
    assert not candidate.is_candidate and "above the route" in str(candidate)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_a_stress_that_is_no_number_is_refused(value):
    with pytest.raises(ValueError, match="net_section_stress"):
        _part(net_section_stress=_mpa(value))


def test_a_wrong_dimension_is_refused():
    with pytest.raises(RefusalError, match="fracture_toughness"):
        _part(fracture_toughness=_mpa(30))


def test_the_hand_methods_page_says_no_mass_threshold_is_invented():
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "structural-hand-methods.md").read_text()
    assert "gives them no mass or energy threshold" in page
    assert "§6.2.5.a" in page and "§6.1.4" in page
