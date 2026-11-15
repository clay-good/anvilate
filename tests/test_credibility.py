"""Model credibility: the test read back against the prediction, and what it may claim.

Every test here is on one of three rules the change was written around. A correlation
never moves a verdict. A score is proposed only from evidence actually held, and names
it. And the eight factors are ordinal — the module offers no way to average them, because
an average of eight ordinal scales is the one number a reader would compare.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from anvilate.credibility import (
    EVIDENCE_CEILINGS,
    FACTOR_LABELS,
    NASA_7009A_CITATION,
    AcceptanceBand,
    Correlation,
    CorrelationVerdict,
    CredibilityFactor,
    CredibilityFactorSet,
    Disposition,
    DispositionKind,
    DomainKind,
    EscapedDefectCandidate,
    FactorScore,
    HeldEvidence,
    PredictionSense,
    ValidationDomain,
    ValidationRange,
    annotate,
    candidates,
    correlate,
    label_checks,
    label_use,
    propose_factor_set,
    unattributed_conservatisms,
)
from anvilate.derivation import DerivationAbsence, Underived
from anvilate.refusal import RefusalError
from anvilate.scorecard import (
    CheckStatus,
    Comparison,
    LimitSense,
    Scorecard,
    ScorecardEntry,
)
from anvilate.units import Quantity
from anvilate.verification import VerificationOutcome, plan_verification, record_outcome

_BTH1 = "ASME BTH-1-2020 §3-3.3.1 (pin-connected plates)"
_BAND_SOURCE = "the proof-test procedure, §4.2 acceptance"
_TEST_DAY = date(2026, 11, 1)
# These entries exist to be correlated, not to show their work; they say so rather than
# adding debt to the derivation ratchet.
_UNDERIVED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="a fixture entry built to carry two numbers into a correlation",
)


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _lug_entry(*, capacity: str = "120 kN", required: str = "100 kN") -> ScorecardEntry:
    """A passing lug check that carries its two numbers, as a comparison check does."""
    return ScorecardEntry(
        name="lug tension",
        status=CheckStatus.PASS,
        detail=f"capacity {capacity} against {required} required",
        reference=_BTH1,
        underived=_UNDERIVED,
        comparison=Comparison(
            measured=_q(capacity),
            limit=_q(required),
            sense=LimitSense.AT_LEAST,
            measured_label="capacity",
            limit_label="required",
        ),
    )


def _correlation(
    *,
    predicted: str = "100 kN",
    measured: str = "92 kN",
    band: AcceptanceBand | None = None,
    sense: PredictionSense = PredictionSense.CAPACITY,
    check_passed: bool = True,
) -> Correlation:
    return Correlation(
        check="lug tension",
        item="Proof load test",
        predicted=_q(predicted),
        measured=_q(measured),
        sense=sense,
        performed_on=_TEST_DAY,
        performed_by="A. Tester",
        instrument="load cell SN-7741",
        band=band,
        check_passed=check_passed,
    )


def _band(fraction: float = 0.05) -> AcceptanceBand:
    return AcceptanceBand(fraction=fraction, source=_BAND_SOURCE)


def _outcome(**overrides: object) -> VerificationOutcome:
    fields: dict[str, object] = {
        "passed": True,
        "measured": "held 92 kN with no permanent set",
        "performed_on": _TEST_DAY,
        "performed_by": "A. Tester",
        "instrument": "load cell SN-7741",
    }
    fields.update(overrides)
    return VerificationOutcome(**fields)  # type: ignore[arg-type]


# --- the correlation itself -------------------------------------------------------


def test_the_proof_test_held_less_than_predicted():
    """The spec's first scenario: 8% below prediction against a ±5% band."""
    correlation = _correlation(predicted="100 kN", measured="92 kN", band=_band(0.05))

    assert correlation.verdict is CorrelationVerdict.UNCONSERVATIVE
    assert correlation.ratio == pytest.approx(0.92)
    assert correlation.difference.magnitude == pytest.approx(-8.0)
    assert correlation.difference.unit == "kN"
    rendered = str(correlation)
    assert "100 kN" in rendered and "92 kN" in rendered
    assert "0.920" in rendered and "0.05" in rendered


def test_a_measurement_in_another_unit_of_the_same_dimension_still_correlates():
    """A preload predicted in kN and measured in lbf is one comparison, not two."""
    correlation = _correlation(predicted="100 kN", measured="22481 lbf", band=_band(0.01))

    assert correlation.verdict is CorrelationVerdict.AGREES
    assert correlation.ratio == pytest.approx(1.0, abs=1e-4)
    # And the difference is stated in the prediction's unit, not the instrument's.
    assert correlation.difference.unit == "kN"


def test_without_a_band_the_comparison_is_not_evaluated_and_says_which_band_it_needs():
    """The spec's second scenario. Both values and the ratio are still reported."""
    correlation = _correlation(predicted="10 mm", measured="14 mm")

    assert correlation.verdict is CorrelationVerdict.NOT_EVALUATED
    assert correlation.ratio == pytest.approx(1.4)
    rendered = str(correlation)
    assert "not evaluated" in rendered
    assert "no acceptance band declared" in rendered
    # The two values are still there: a not-evaluated comparison is not a silent one.
    assert "10 mm" in rendered and "14 mm" in rendered


def test_the_unsafe_direction_is_the_check_s_to_state_not_the_module_s_to_guess():
    """The same 8% is unconservative on a capacity and conservative on a response."""
    low = {"predicted": "100 kN", "measured": "92 kN", "band": _band(0.05)}
    assert _correlation(**low, sense=PredictionSense.CAPACITY).verdict is (
        CorrelationVerdict.UNCONSERVATIVE
    )
    assert _correlation(**low, sense=PredictionSense.RESPONSE).verdict is (
        CorrelationVerdict.CONSERVATIVE
    )
    high = {"predicted": "100 MPa", "measured": "108 MPa", "band": _band(0.05)}
    assert _correlation(**high, sense=PredictionSense.RESPONSE).verdict is (
        CorrelationVerdict.UNCONSERVATIVE
    )
    assert _correlation(**high, sense=PredictionSense.CAPACITY).verdict is (
        CorrelationVerdict.CONSERVATIVE
    )


@pytest.mark.parametrize(
    ("measured", "verdict"),
    [
        ("95 kN", CorrelationVerdict.AGREES),  # exactly on the lower edge
        ("105 kN", CorrelationVerdict.AGREES),  # exactly on the upper edge
        ("94.9 kN", CorrelationVerdict.UNCONSERVATIVE),
        ("105.1 kN", CorrelationVerdict.CONSERVATIVE),
    ],
)
def test_the_band_edges_are_inside_the_band(measured, verdict):
    """A refusal test cannot see the bound: both edges are pinned, and both neighbours."""
    assert _correlation(measured=measured, band=_band(0.05)).verdict is verdict


def test_a_correlation_refuses_what_a_ratio_cannot_be_computed_from():
    with pytest.raises(RefusalError, match="same dimension"):
        _correlation(predicted="100 kN", measured="92 degC")
    with pytest.raises(RefusalError, match="non-zero predicted"):
        _correlation(predicted="0 kN", measured="92 kN")
    with pytest.raises(RefusalError, match="non-finite"):
        Correlation(
            check="lug",
            item="Proof load test",
            predicted=Quantity(magnitude=float("nan"), unit="kN"),
            measured=_q("92 kN"),
            sense=PredictionSense.CAPACITY,
            performed_on=_TEST_DAY,
            performed_by="A. Tester",
            instrument="load cell SN-7741",
        )
    with pytest.raises(RefusalError, match="performed_by"):
        Correlation(
            check="lug",
            item="Proof load test",
            predicted=_q("100 kN"),
            measured=_q("92 kN"),
            sense=PredictionSense.CAPACITY,
            performed_on=_TEST_DAY,
            performed_by="   ",
            instrument="load cell SN-7741",
        )


def test_an_instrument_uncertainty_in_another_dimension_is_refused():
    with pytest.raises(RefusalError, match="cannot bound this measurement"):
        Correlation(
            check="lug",
            item="Proof load test",
            predicted=_q("100 kN"),
            measured=_q("92 kN"),
            sense=PredictionSense.CAPACITY,
            performed_on=_TEST_DAY,
            performed_by="A. Tester",
            instrument="load cell SN-7741",
            instrument_uncertainty=_q("0.2 mm"),
        )


# --- the acceptance band ----------------------------------------------------------


@pytest.mark.parametrize("fraction", [0.0, -0.05, 1.0001, 2.0])
def test_a_band_that_is_not_an_acceptance_criterion_is_refused(fraction):
    with pytest.raises(RefusalError):
        AcceptanceBand(fraction=fraction, source=_BAND_SOURCE)


def test_the_widest_band_is_accepted_at_its_own_edge():
    """The other side of the bound the refusal test above cannot see."""
    assert AcceptanceBand(fraction=1.0, source=_BAND_SOURCE).fraction == 1.0
    assert AcceptanceBand(fraction=1e-6, source=_BAND_SOURCE).fraction == 1e-6


def test_a_band_nobody_can_attribute_is_refused():
    """`Provenance` is where this is caught, one layer down and for every cited field."""
    with pytest.raises(ValidationError, match="state where it came from"):
        AcceptanceBand(fraction=0.05, source="   ")


# --- the escaped-defect candidate -------------------------------------------------


def test_the_candidate_reaches_the_process_with_the_digest_and_the_record():
    correlation = _correlation(measured="92 kN", band=_band(0.05))
    filed = candidates((correlation,), bundle_digest="sha256:7f3c")

    assert len(filed) == 1
    candidate = filed[0]
    assert candidate.bundle_digest == "sha256:7f3c"
    assert candidate.check == "lug tension"
    assert candidate.undispositioned
    assert candidate.correlation.instrument == "load cell SN-7741"
    assert candidate.correlation.performed_on == _TEST_DAY
    assert "undispositioned" in str(candidate)


def test_only_an_unconservative_correlation_on_a_passing_check_is_a_candidate():
    agreeing = _correlation(measured="99 kN", band=_band(0.05))
    conservative = _correlation(measured="130 kN", band=_band(0.05))
    unbanded = _correlation(measured="92 kN")
    failing = _correlation(measured="92 kN", band=_band(0.05), check_passed=False)

    assert candidates((agreeing, conservative, unbanded, failing), bundle_digest="d") == ()
    for correlation in (agreeing, conservative, unbanded, failing):
        with pytest.raises(RefusalError, match="not an escaped-defect candidate"):
            EscapedDefectCandidate(bundle_digest="d", correlation=correlation)


def test_a_candidate_needs_the_digest_of_the_bundle_the_verdict_came_from():
    with pytest.raises(RefusalError, match="needs the digest of the bundle"):
        EscapedDefectCandidate(bundle_digest="  ", correlation=_correlation(band=_band(0.05)))


def test_dispositioning_closes_the_candidate_and_leaves_the_finding_alone():
    candidate = candidates((_correlation(band=_band(0.05)),), bundle_digest="sha256:7f3c")[0]
    closed = candidate.model_copy(
        update={
            "disposition": Disposition(
                kind=DispositionKind.TEST_OR_INSTRUMENT_ISSUE,
                reason="the load cell was out of calibration on the test date",
                by="R. Reviewer",
                on=date(2026, 11, 3),
            )
        }
    )

    assert not closed.undispositioned
    # The finding is the correlation, and it did not move.
    assert closed.correlation == candidate.correlation
    assert closed.correlation.verdict is CorrelationVerdict.UNCONSERVATIVE
    assert "R. Reviewer" in str(closed)


def test_an_unattributed_disposition_is_refused():
    for field, value in (("reason", "  "), ("by", "")):
        fields = {
            "kind": DispositionKind.ESCAPED_DEFECT,
            "reason": "the lug check overpredicts bearing",
            "by": "R. Reviewer",
            "on": date(2026, 11, 3),
            field: value,
        }
        with pytest.raises(RefusalError, match=field):
            Disposition(**fields)  # type: ignore[arg-type]


# --- the conservative half --------------------------------------------------------


def test_a_conservative_correlation_is_a_ledger_note_and_not_a_finding():
    conservative = _correlation(predicted="100 kN", measured="112 kN", band=_band(0.05))
    notes = unattributed_conservatisms((conservative,))

    assert len(notes) == 1
    assert notes[0].quantity == "lug tension"
    assert notes[0].implied_factor == pytest.approx(1.12)
    assert "unattributed conservatism" in str(notes[0])
    # And it is not a candidate.
    assert candidates((conservative,), bundle_digest="d") == ()


def test_a_conservative_response_reads_as_a_factor_above_one_too():
    """A response measured 11% low is x1.125 of conservatism, not x0.89."""
    note = unattributed_conservatisms(
        (
            _correlation(
                predicted="100 MPa",
                measured="88.9 MPa",
                band=_band(0.05),
                sense=PredictionSense.RESPONSE,
            ),
        )
    )[0]
    assert note.implied_factor > 1.0
    assert note.implied_factor == pytest.approx(1.0 / 0.889)


# --- the plan and the card --------------------------------------------------------


def _planned_card() -> tuple[Scorecard, object]:
    card = Scorecard(entries=(_lug_entry(),))
    plan = plan_verification(card, parameters={"rated_load": _q("80 kN")})
    return card, plan


def test_a_measured_value_flows_from_the_outcome_into_the_correlation():
    """The verification-planning delta's first scenario."""
    card, plan = _planned_card()
    plan = record_outcome(
        plan,
        name="Proof load test",
        outcome=_outcome(
            measured="held 92 kN",
            measured_value=_q("92 kN"),
            instrument_uncertainty=_q("0.3 kN"),
        ),
    )

    found = correlate(plan, card, bands={"lug tension": _band(0.05)})
    assert len(found) == 1
    assert found[0].measured == _q("92 kN")
    assert found[0].instrument_uncertainty == _q("0.3 kN")
    assert found[0].predicted == _q("100 kN")
    assert plan.items[0].correlated
    assert "correlated" in plan.matrix()


def test_pass_with_no_number_is_performed_and_uncorrelated_never_agreeing():
    """The delta's second scenario. A bare 'passed' implies nothing about agreement."""
    card, plan = _planned_card()
    plan = record_outcome(plan, name="Proof load test", outcome=_outcome())

    assert plan.items[0].status is CheckStatus.PASS
    assert not plan.items[0].correlated
    assert "uncorrelated" in str(plan.items[0])
    assert "uncorrelated" in plan.matrix()
    assert correlate(plan, card, bands={"lug tension": _band(0.05)}) == ()


def test_an_instrument_uncertainty_with_no_number_to_bound_is_refused():
    """The refusal is a `ValueError`, so pydantic reports it as a validation error."""
    with pytest.raises(ValidationError, match="no number here to bound"):
        _outcome(instrument_uncertainty=_q("0.3 kN"))


def test_an_outcome_uncertainty_in_another_dimension_is_refused():
    with pytest.raises(ValidationError, match="cannot bound this measurement"):
        _outcome(measured_value=_q("92 kN"), instrument_uncertainty=_q("0.3 mm"))


def test_the_finding_lands_on_the_card_and_the_verdict_does_not_move():
    card, plan = _planned_card()
    plan = record_outcome(
        plan, name="Proof load test", outcome=_outcome(measured_value=_q("92 kN"))
    )
    found = correlate(plan, card, bands={"lug tension": _band(0.05)})

    annotated = annotate(card, found)
    entry = annotated.entries[0]
    assert entry.status is CheckStatus.PASS
    assert annotated.status is CheckStatus.PASS
    assert entry.correlation is not None
    assert entry.correlation.verdict is CorrelationVerdict.UNCONSERVATIVE
    # And it survives a round trip through the serialised card, which is what a bundle
    # holds and `anvilate verify` reads back.
    reloaded = Scorecard.model_validate(annotated.model_dump(mode="json"))
    assert reloaded.entries[0].correlation == entry.correlation


def test_a_card_with_no_correlation_serialises_exactly_as_it_did():
    card = Scorecard(entries=(_lug_entry(),))
    dumped = card.model_dump(mode="json")
    assert "correlation" not in dumped["entries"][0]
    assert "domain" not in dumped["entries"][0]


def test_a_check_whose_response_is_the_prediction_correlates_against_the_response():
    """An at-most check predicts a response; its limit is the allowable, not the number
    a test measures."""
    card = Scorecard(
        entries=(
            ScorecardEntry(
                name="tip deflection",
                status=CheckStatus.PASS,
                detail="8 mm against 12 mm allowed",
                reference="ISO 286-1:2010 H7/g6 clearance fit",
                underived=_UNDERIVED,
                comparison=Comparison(
                    measured=_q("8 mm"),
                    limit=_q("12 mm"),
                    sense=LimitSense.AT_MOST,
                    measured_label="deflection",
                    limit_label="allowed",
                ),
            ),
        )
    )
    plan = plan_verification(card, parameters={"tolerance": _q("0.05 mm")})
    plan = record_outcome(
        plan,
        name="Dimensional inspection",
        outcome=_outcome(measured="8.3 mm", measured_value=_q("8.3 mm")),
    )
    found = correlate(
        plan,
        card,
        bands={"tip deflection": _band(0.05)},
        senses={"tip deflection": PredictionSense.RESPONSE},
    )
    assert len(found) == 1
    assert found[0].predicted == _q("8 mm")
    assert found[0].verdict is CorrelationVerdict.AGREES


# --- the credibility factors ------------------------------------------------------


def test_the_eight_factors_are_revision_a_s_and_each_is_named_and_categorised():
    """Rev A renamed them. Anything carrying the 2008 names is a revision behind."""
    assert len(CredibilityFactor) == 8
    assert set(FACTOR_LABELS) == set(CredibilityFactor)
    assert set(EVIDENCE_CEILINGS) == set(CredibilityFactor)
    names = {label for label, _ in FACTOR_LABELS.values()}
    assert names == {
        "Data Pedigree",
        "Verification",
        "Validation",
        "Input Pedigree",
        "Uncertainty Characterization",
        "Results Robustness",
        "M&S History",
        "M&S Process/Product Management",
    }
    # The 2008 factor names are not anywhere in the set.
    assert not names & {"Code Verification", "Referent Validation", "Results Uncertainty"}


def test_a_closed_form_check_with_an_anchor_and_a_correlation():
    """The spec's scoring scenario, on the Rev A factors it maps onto."""
    proposed = propose_factor_set(
        "lug tension",
        HeldEvidence(
            cited_data_records=2,
            worked_example_anchors=1,
            agreeing_correlations=1,
            inputs_with_an_origin=6,
            inputs_total=6,
        ),
    )

    assert proposed.level(CredibilityFactor.VERIFICATION) == 2
    assert "worked example" in proposed.score(CredibilityFactor.VERIFICATION).evidence
    assert proposed.level(CredibilityFactor.VALIDATION) == 2
    assert "recorded test agreed" in proposed.score(CredibilityFactor.VALIDATION).evidence
    # No distribution was declared, so the uncertainty factor is 0 and says why.
    uncertainty = proposed.score(CredibilityFactor.UNCERTAINTY_CHARACTERIZATION)
    assert uncertainty.level == 0
    assert "no distribution was declared" in uncertainty.evidence
    assert CredibilityFactor.MS_HISTORY in proposed.insufficient


def test_a_factor_with_no_evidence_is_zero_and_says_what_is_missing():
    bare = propose_factor_set("empty", HeldEvidence())
    assert len(bare.insufficient) == 8
    for score in bare.scores:
        assert score.level == 0
        assert "no evidence held" in score.evidence
        # A bare zero is the thing the assessment exists to replace.
        assert score.evidence.strip() != "no evidence held"


def test_a_proposal_never_exceeds_the_published_ceiling():
    """The mapping is published so a reviewer can disagree with it, not with a number."""
    generous = propose_factor_set(
        "everything",
        HeldEvidence(
            cited_data_records=9999,
            worked_example_anchors=9999,
            agreeing_correlations=9999,
            inputs_with_an_origin=50,
            inputs_total=50,
            uncertainty_propagated=True,
            quantified_sensitivities=40,
            change_history="three patch releases, no formula changed",
            managed_process="the repository's documented review process",
        ),
    )
    for score in generous.scores:
        ceiling, _ = EVIDENCE_CEILINGS[score.factor]
        assert score.level <= ceiling
    # And nothing here reaches the standard's top two levels, which need comparison with
    # the real-world system across its operating range.
    assert max(score.level for score in generous.scores) == 2


def test_partly_traced_inputs_score_one_not_two():
    partial = propose_factor_set("partial", HeldEvidence(inputs_with_an_origin=3, inputs_total=6))
    score = partial.score(CredibilityFactor.INPUT_PEDIGREE)
    assert score.level == 1
    assert "3 of 6" in score.evidence


def test_more_traced_inputs_than_inputs_is_refused():
    with pytest.raises(RefusalError, match="more traced than there are"):
        HeldEvidence(inputs_with_an_origin=7, inputs_total=6)


def test_negative_evidence_is_refused():
    with pytest.raises(RefusalError, match="cannot be negative"):
        HeldEvidence(worked_example_anchors=-1)


def test_an_override_is_attributed_and_keeps_the_proposal_visible():
    proposed = propose_factor_set(
        "lug tension", HeldEvidence(agreeing_correlations=1, cited_data_records=1)
    )
    overridden = proposed.with_override(
        CredibilityFactor.VALIDATION,
        level=1,
        reason="one point does not span the operating range of this lug",
        by="R. Reviewer",
    )
    score = overridden.score(CredibilityFactor.VALIDATION)

    assert score.level == 1
    assert score.proposed_level == 2
    assert score.override_by == "R. Reviewer"
    assert "does not span" in (score.override_reason or "")
    rendered = str(score)
    assert "overridden from 2" in rendered and "R. Reviewer" in rendered
    # The other seven are untouched.
    for factor in CredibilityFactor:
        if factor is not CredibilityFactor.VALIDATION:
            assert not overridden.score(factor).overridden()


def test_an_unexplained_or_unattributed_override_is_refused():
    base = {
        "factor": CredibilityFactor.VALIDATION,
        "level": 1,
        "evidence": "one recorded test",
        "proposed_level": 2,
    }
    with pytest.raises(RefusalError, match="states no reason"):
        FactorScore(**base, override_by="R. Reviewer")  # type: ignore[arg-type]
    with pytest.raises(RefusalError, match="names nobody"):
        FactorScore(  # type: ignore[arg-type]
            **base, override_reason="one point is not a domain"
        )
    with pytest.raises(RefusalError, match="nothing on the other side"):
        FactorScore(
            factor=CredibilityFactor.VALIDATION,
            level=1,
            evidence="one recorded test",
            override_reason="one point is not a domain",
            override_by="R. Reviewer",
        )


@pytest.mark.parametrize("level", [-1, 5, 100])
def test_a_level_off_the_scale_is_refused(level):
    with pytest.raises(RefusalError, match="off the NASA-STD-7009A scale"):
        FactorScore(factor=CredibilityFactor.VALIDATION, level=level, evidence="x")


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_every_level_on_the_scale_is_accepted(level):
    """The other side of the bound the refusal test above cannot see: 0 and 4 are on it."""
    assert FactorScore(factor=CredibilityFactor.VALIDATION, level=level, evidence="x").level == (
        level
    )


def test_a_score_with_no_evidence_beside_it_is_refused():
    with pytest.raises(RefusalError, match="evidence"):
        FactorScore(factor=CredibilityFactor.VALIDATION, level=3, evidence="   ")


def test_a_partial_factor_set_is_refused():
    """The factor left out of a partial set is the one with no evidence."""
    full = propose_factor_set("x", HeldEvidence())
    with pytest.raises(RefusalError, match="omits"):
        CredibilityFactorSet(subject="x", scores=full.scores[:5])
    with pytest.raises(RefusalError, match="more than once"):
        CredibilityFactorSet(subject="x", scores=(*full.scores, full.scores[0]))


def test_the_set_cites_the_standard_and_offers_no_total():
    """NASA-STD-7009A E.4: the assessments are ordinal and are not to be averaged.

    The gate is the absence of the method, because a mean of eight ordinal scales is the
    one number every reader would compare against another one.
    """
    proposed = propose_factor_set("x", HeldEvidence(cited_data_records=1))

    assert proposed.citation == NASA_7009A_CITATION
    for forbidden in ("total", "mean", "average", "overall", "sum", "score_total"):
        assert not hasattr(proposed, forbidden), (
            f"CredibilityFactorSet.{forbidden} aggregates ordinal levels, which the "
            f"standard states they are not to be"
        )
    table = proposed.table()
    assert "NASA-STD-7009A" in table
    assert "not to be averaged" in table
    assert "not a certification" in table
    # Every factor is in the table, under one of the standard's three categories.
    for label, _ in FACTOR_LABELS.values():
        assert label in table


# --- the validation domain --------------------------------------------------------


def _pin_range(low: str, high: str, source: str) -> ValidationRange:
    return ValidationRange(parameter="pin_diameter", low=_q(low), high=_q(high), source=source)


def test_a_lug_twice_the_size_of_any_test_is_labelled_extrapolative():
    """The spec's domain scenario. The verdict is not this function's to touch."""
    ranges = (
        _pin_range("20 mm", "40 mm", "ASME BTH-1 worked example 3"),
        _pin_range("25 mm", "30 mm", "proof test 2026-04-11"),
    )
    label = label_use({"pin_diameter": _q("80 mm")}, ranges)

    assert label is not None
    assert label.kind is DomainKind.EXTRAPOLATIVE
    assert label.parameter == "pin_diameter"
    # Named with the *nearest* recorded range, which is the 20–40 one.
    assert label.nearest.low == _q("20 mm")
    assert "80" in str(label) and "20" in str(label)


def test_a_use_inside_a_recorded_range_is_interpolative_with_the_range_named():
    ranges = (_pin_range("20 mm", "40 mm", "ASME BTH-1 worked example 3"),)
    label = label_use({"pin_diameter": _q("32 mm")}, ranges)

    assert label is not None
    assert label.kind is DomainKind.INTERPOLATIVE
    assert "ASME BTH-1 worked example 3" in str(label)


def test_a_parameter_inside_one_range_is_not_extrapolating_because_it_is_outside_another():
    """Two recorded ranges for one parameter are two tests, not two requirements."""
    ranges = (
        _pin_range("20 mm", "40 mm", "worked example 3"),
        _pin_range("60 mm", "70 mm", "proof test 2026-04-11"),
    )
    label = label_use({"pin_diameter": _q("32 mm")}, ranges)
    assert label is not None
    assert label.kind is DomainKind.INTERPOLATIVE


def test_a_check_compared_nowhere_has_no_domain_to_label():
    """Labelling it interpolative would claim a validation domain it does not have."""
    assert label_use({"pin_diameter": _q("32 mm")}, ()) is None
    assert label_use({"pin_diameter": _q("32 mm")}, (_pin_range("1 kN", "2 kN", "x"),)) is None


def test_the_parameter_named_is_the_one_doing_the_extrapolating():
    ranges = (
        _pin_range("20 mm", "40 mm", "worked example 3"),
        ValidationRange(parameter="load", low=_q("10 kN"), high=_q("20 kN"), source="proof test"),
    )
    label = label_use(
        {"pin_diameter": _q("41 mm"), "load": _q("200 kN")},
        ranges,
    )
    assert label is not None
    assert label.kind is DomainKind.EXTRAPOLATIVE
    # 41 mm is 5% outside a 20 mm-wide range; 200 kN is 18 range-widths outside. The
    # reader is pointed at the second.
    assert label.parameter == "load"


def test_a_range_that_is_not_a_range_is_refused():
    with pytest.raises(RefusalError, match="low to high"):
        _pin_range("40 mm", "20 mm", "worked example 3")
    with pytest.raises(RefusalError, match="same dimension"):
        ValidationRange(parameter="pin", low=_q("20 mm"), high=_q("40 kN"), source="worked example")
    with pytest.raises(ValidationError, match="state where it came from"):
        _pin_range("20 mm", "40 mm", "   ")
    # A non-finite bound is caught one layer down, because a range states requirements.
    with pytest.raises(ValidationError, match="not a number a document can state"):
        ValidationRange(
            parameter="pin",
            low=Quantity(magnitude=float("-inf"), unit="mm"),
            high=_q("40 mm"),
            source="worked example",
        )


def test_a_single_validated_point_is_a_range_of_zero_width():
    """One anchored point is still a domain, and a use at it is interpolative."""
    single = _pin_range("25 mm", "25 mm", "worked example 3")
    assert single.contains(_q("25 mm"))
    assert label_use({"pin_diameter": _q("25 mm")}, (single,)).kind is DomainKind.INTERPOLATIVE
    assert single.distance(_q("30 mm")) == pytest.approx(5.0 / 25.0)


# --- the rendering ----------------------------------------------------------------


def test_the_report_prints_the_correlation_beside_the_verdict_and_the_ledger_note():
    from anvilate.report import CalculationReport, ReportSection

    card, plan = _planned_card()
    plan = record_outcome(
        plan, name="Proof load test", outcome=_outcome(measured_value=_q("92 kN"))
    )
    annotated = annotate(card, correlate(plan, card, bands={"lug tension": _band(0.05)}))
    report = CalculationReport(
        title="Lug",
        sections=(ReportSection(entry=annotated.entries[0]),),
    )
    text = report.to_text()

    assert "correlation:" in text
    assert "unconservative" in text
    assert "load cell SN-7741" in text
    # The verdict is still a pass, printed in the same document.
    assert annotated.status is CheckStatus.PASS

    conservative = annotate(
        card,
        correlate(
            plan, card, bands={"lug tension": AcceptanceBand(fraction=0.5, source=_BAND_SOURCE)}
        ),
    )
    assert conservative.entries[0].correlation.verdict is CorrelationVerdict.AGREES


def test_the_dossier_carries_the_factor_set_and_lists_the_open_candidates():
    """The spec's "visible in the dossier until it is dispositioned"."""
    from anvilate.review import build_dossier

    card = Scorecard(entries=(_lug_entry(),))
    correlation = _correlation(band=_band(0.05))
    dossier = build_dossier(
        card,
        toolchain="anvilate 0.0.1",
        credibility=(propose_factor_set("lug tension", HeldEvidence(cited_data_records=1)),),
        candidates=candidates((correlation,), bundle_digest="sha256:7f3c"),
    )

    assert len(dossier.undispositioned) == 1
    assert "undispositioned escaped-defect candidate" in dossier.summary()
    assert "lug tension" in dossier.summary()
    table = dossier.credibility_table()
    assert NASA_7009A_CITATION in table
    assert "Data Pedigree: 2" in table


def test_a_dossier_with_no_assessment_says_so_rather_than_reading_reassuring():
    from anvilate.review import build_dossier

    dossier = build_dossier(Scorecard(entries=(_lug_entry(),)), toolchain="anvilate 0.0.1")
    assert dossier.credibility_table() == "no credibility assessment was made for this artifact"
    assert "escaped-defect" not in dossier.summary()


def test_a_dispositioned_candidate_leaves_the_dossier_s_open_count_but_not_the_list():
    from anvilate.review import build_dossier

    candidate = candidates((_correlation(band=_band(0.05)),), bundle_digest="sha256:7f3c")[0]
    closed = candidate.model_copy(
        update={
            "disposition": Disposition(
                kind=DispositionKind.ESCAPED_DEFECT,
                reason="the lug check overpredicts bearing at this edge distance",
                by="R. Reviewer",
                on=date(2026, 11, 3),
            )
        }
    )
    dossier = build_dossier(
        Scorecard(entries=(_lug_entry(),)), toolchain="anvilate 0.0.1", candidates=(closed,)
    )
    assert dossier.undispositioned == ()
    assert len(dossier.candidates) == 1
    assert "undispositioned" not in dossier.summary()


def test_the_report_renders_the_factor_set_with_the_standard_and_no_total():
    from anvilate.report import CalculationReport, ReportSection

    factors = propose_factor_set(
        "lug tension", HeldEvidence(cited_data_records=1, worked_example_anchors=1)
    )
    report = CalculationReport(
        title="Lug",
        sections=(ReportSection(entry=_lug_entry()),),
        credibility=(factors,),
    )
    text = report.to_text()
    html = report.to_html()

    for surface in (text, html):
        assert "Model credibility" in surface
        assert "NASA-STD-7009A" in surface
        assert "Data Pedigree" in surface
        assert "M&S Process/Product Management" in surface or (
            "M&amp;S Process/Product Management" in surface
        )
    # The one row a reader would compare against another document is absent from both.
    assert "Total" not in text and "Overall credibility" not in text
    # And a report that assessed nothing says so rather than omitting the section.
    bare = CalculationReport(title="Lug", sections=(ReportSection(entry=_lug_entry()),))
    assert "no credibility assessment was made" in bare.to_text()
    assert "no credibility assessment was made" in bare.to_html()


def test_a_check_records_the_domain_it_has_been_compared_over():
    domain = ValidationDomain(
        check="lug tension",
        ranges=(
            _pin_range("20 mm", "40 mm", "ASME BTH-1-2020 worked example 3"),
            _pin_range("25 mm", "30 mm", "proof test 2026-04-11"),
            ValidationRange(
                parameter="plate_thickness",
                low=_q("6 mm"),
                high=_q("12 mm"),
                source="ASME BTH-1-2020 worked example 3",
            ),
        ),
    )
    assert domain.parameters == ("pin_diameter", "plate_thickness")
    assert domain.label({"pin_diameter": _q("32 mm")}).kind is DomainKind.INTERPOLATIVE
    assert domain.label({"pin_diameter": _q("80 mm")}).kind is DomainKind.EXTRAPOLATIVE
    assert domain.label({"edge_distance": _q("18 mm")}) is None
    assert "compared over" in str(domain)


def test_a_domain_with_no_range_is_refused():
    with pytest.raises(RefusalError, match="records no range"):
        ValidationDomain(check="lug tension", ranges=())


def test_the_extrapolative_label_lands_on_the_entry_and_the_verdict_does_not_move():
    card = Scorecard(entries=(_lug_entry(),))
    labels = label_checks(
        (
            ValidationDomain(
                check="lug tension",
                ranges=(_pin_range("20 mm", "40 mm", "ASME BTH-1-2020 worked example 3"),),
            ),
        ),
        {"lug tension": {"pin_diameter": _q("80 mm")}},
    )
    annotated = annotate(card, labels=labels)
    entry = annotated.entries[0]

    assert entry.status is CheckStatus.PASS
    assert entry.domain is not None
    assert entry.domain.kind is DomainKind.EXTRAPOLATIVE
    assert entry.domain.parameter == "pin_diameter"
    assert entry.correlation is None
    # And it survives the round trip a bundle reader takes.
    reloaded = Scorecard.model_validate(annotated.model_dump(mode="json"))
    assert reloaded.entries[0].domain == entry.domain


def test_a_check_with_no_recorded_domain_gets_no_label():
    assert label_checks((), {"lug tension": {"pin_diameter": _q("80 mm")}}) == {}
    # And annotating with nothing to add returns the entries untouched.
    card = Scorecard(entries=(_lug_entry(),))
    assert annotate(card).entries[0] is card.entries[0]


def test_each_category_renders_as_the_standard_names_it():
    """ "ms use" is not one of the standard's three category names."""
    from anvilate.credibility import FactorCategory

    labels = {category.label for category in FactorCategory}
    assert labels == {"M&S Development", "M&S Use (Operations)", "Supporting Evidence"}
    table = propose_factor_set("x", HeldEvidence()).table()
    for label in labels:
        assert label in table
    assert "ms use" not in table and "ms_use" not in table


def test_the_evidence_lines_count_in_the_singular_when_there_is_one():
    """A rendered page said "1 bundled records"; the page is the product here."""
    one = propose_factor_set(
        "x",
        HeldEvidence(
            cited_data_records=1,
            worked_example_anchors=1,
            agreeing_correlations=1,
            quantified_sensitivities=1,
        ),
    ).table()
    for plural in ("1 bundled records", "1 checks", "1 recorded tests", "1 parameters"):
        assert plural not in one
    many = propose_factor_set(
        "x",
        HeldEvidence(
            cited_data_records=2,
            worked_example_anchors=2,
            agreeing_correlations=2,
            quantified_sensitivities=2,
        ),
    ).table()
    for plural in ("2 bundled records", "2 checks", "2 recorded tests", "2 parameters"):
        assert plural in many


def test_the_docs_page_quotes_what_the_library_actually_renders():
    """The page's figures are recomputed, not transcribed.

    A number quoted only in prose has no gate on it, and this page argues from three:
    the 100-against-92 correlation line, the ±0.05 band, and a ceiling of 2 on every one
    of the eight factors.
    """
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "docs" / "model-credibility.md").read_text()

    quoted = re.search(
        r"# lug tension: predicted (\S+) kN, measured (\S+) kN "
        r"\(ratio ([\d.]+), band ±([\d.]+)",
        page,
    )
    assert quoted is not None, "the page's rendered correlation line has moved"
    predicted, measured, ratio, fraction = quoted.groups()
    rendered = str(
        _correlation(
            predicted=f"{predicted} kN",
            measured=f"{measured} kN",
            band=AcceptanceBand(fraction=float(fraction), source="proof-test procedure §4.2"),
        )
    )
    assert f"ratio {ratio}" in rendered
    assert "unconservative" in rendered and "unconservative" in page

    # Every row of the published ceiling table says 2, and the code is where that is true.
    rows = re.findall(r"^\| ([A-Z][^|]+?) \| [^|]+ \| (\d) \|$", page, re.M)
    assert len(rows) == len(CredibilityFactor), f"the ceiling table lists {len(rows)} factors"
    by_label = {
        label: ceiling
        for factor, (ceiling, _) in EVIDENCE_CEILINGS.items()
        for label, _ in (FACTOR_LABELS[factor],)
    }
    for label, claimed in rows:
        name = label.replace("(NASA-STD-7009A Rev A)", "").strip()
        assert name in by_label, f"the page names a factor the code does not: {name}"
        assert by_label[name] == int(claimed), (
            f"the page claims a ceiling of {claimed} for {name}; the code publishes "
            f"{by_label[name]}"
        )


def test_the_one_line_rendering_counts_the_factors_with_no_evidence():
    """The short form, which is what a pane prints when the table will not fit."""
    bare = propose_factor_set("lug tension", HeldEvidence())
    assert str(bare) == (
        "credibility of lug tension: eight factors on the NASA-STD-7009A scale, "
        "8 with insufficient evidence"
    )
    some = propose_factor_set(
        "lug tension", HeldEvidence(cited_data_records=1, worked_example_anchors=1)
    )
    assert "6 with insufficient evidence" in str(some)
    # The subject is in it: two sets in one document are told apart by this line alone.
    assert "lug tension" in str(some)
