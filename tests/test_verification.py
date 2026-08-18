"""Verification planning: a plan is not evidence, and a check that did not run gets no test."""

from __future__ import annotations

from datetime import date

import pytest

from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity
from anvilate.verification import (
    DEFAULT_ARCHETYPES,
    VerificationMethod,
    VerificationOutcome,
    plan_verification,
    record_outcome,
)


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


_BTH1 = "ASME BTH-1 §3-2/§3-3 (allowable stresses)"


def _entry(name: str, *, reference: str, factor: float = 2.0) -> ScorecardEntry:
    return ScorecardEntry.from_safety_factor(name, computed=factor, required=1.0).model_copy(
        update={"reference": reference}
    )


def _lifter_card() -> Scorecard:
    return Scorecard(
        entries=(
            _entry("beam bending", reference=_BTH1, factor=1.19),
            _entry("bail pin bearing", reference=_BTH1, factor=1.16),
            _entry("pin fit", reference="ISO 286 H7/g6 clearance fit"),
            _entry("weld throat", reference="AWS D1.1 fillet weld", factor=1.4),
            ScorecardEntry(
                name="fatigue",
                status=CheckStatus.NOT_EVALUATED,
                detail="no cycle data",
                reference="ASME BTH-1 §3-1.4 (Service Class)",
            ),
        )
    )


def test_the_proof_load_factor_and_the_rating_rule_are_the_same_statement_inverted():
    """B30.20 caps the proof load at 125% of rated and the rating at 80% of the test load.

    1/1.25 = 0.80 exactly. That identity is the anchor: a proof factor transcribed wrong
    breaks it, and the two halves of the rule appear in the same acceptance line, so a
    reader can check them against each other without the standard in hand.
    """
    plan = plan_verification(_lifter_card(), parameters={"rated_load": _q("100 kN")})
    proof = next(item for item in plan.items if item.name == "Proof load test")
    assert "125 kN" in proof.acceptance
    assert "1.25 x the 100 kN rated load" in proof.acceptance
    assert "80% of the load sustained" in proof.acceptance
    assert proof.archetype.method is VerificationMethod.TEST
    assert "B30.20" in proof.archetype.citation
    assert "1926.251" in proof.archetype.citation
    # One proof load stands behind every BTH-1 member check on the device it loads.
    assert proof.driving_checks == ("beam bending", "bail pin bearing")


def test_a_check_that_did_not_run_gets_no_test_and_is_named_unresolved():
    """There is no physical counterpart to an analysis that was never performed.

    Omitting it would make the plan shorter, and a shorter plan reads as a smaller job.
    """
    plan = plan_verification(
        _lifter_card(), parameters={"rated_load": _q("100 kN"), "tolerance": _q("0.05 mm")}
    )
    assert ("fatigue", "the check did not run, so there is nothing to verify against") in (
        plan.unresolved
    )
    assert all("fatigue" not in item.driving_checks for item in plan.items)
    assert "fatigue" not in plan.analysis_only
    # And it holds the whole plan open: an unresolved check cannot be rolled up as done.
    assert plan.status is CheckStatus.NOT_EVALUATED
    assert "unresolved: the check did not run" in plan.matrix()


def test_a_planned_test_never_renders_as_a_performed_one():
    """The rule the change exists for: intending to test something is not testing it."""
    plan = plan_verification(_lifter_card(), parameters={"rated_load": _q("100 kN")})
    assert plan.items
    assert all(item.outcome is None for item in plan.items)
    assert all(item.status is CheckStatus.NOT_EVALUATED for item in plan.items)
    assert plan.verified == ()
    assert plan.status is CheckStatus.NOT_EVALUATED
    assert "planned" in plan.matrix()
    assert "verified" not in plan.summary()
    # Every check passing upstream changes none of it — nothing infers a result.
    assert _lifter_card().entries[0].status is CheckStatus.PASS
    assert plan.status is CheckStatus.NOT_EVALUATED


def test_recording_an_outcome_is_the_only_way_an_item_becomes_evidence():
    card = Scorecard(entries=(_entry("beam bending", reference=_BTH1, factor=1.19),))
    plan = plan_verification(card, parameters={"rated_load": _q("100 kN")})
    assert plan.status is CheckStatus.NOT_EVALUATED

    outcome = VerificationOutcome(
        passed=True,
        measured="125.4 kN held 10 min, no permanent set",
        performed_on=date(2026, 8, 18),
        performed_by="M. Okonkwo",
        instrument="Load cell LC-4471",
    )
    performed = record_outcome(plan, name="Proof load test", outcome=outcome)
    assert performed.items[0].status is CheckStatus.PASS
    assert performed.verified == performed.items
    assert performed.status is CheckStatus.PASS
    # A failed outcome fails the plan; it does not merely leave it open.
    failed = record_outcome(
        plan, name="Proof load test", outcome=outcome.model_copy(update={"passed": False})
    )
    assert failed.status is CheckStatus.FAIL
    # Recording against an item the plan does not have is an error, not a new item.
    with pytest.raises(KeyError, match="not an item of this plan"):
        record_outcome(plan, name="Hydrostatic pressure test", outcome=outcome)
    # An untraceable record is closer to a claim than to evidence.
    for blank in ("measured", "performed_by", "instrument"):
        with pytest.raises(ValueError, match=f"needs a {blank}"):
            VerificationOutcome(
                **{
                    **outcome.model_dump(),
                    blank: "   ",
                }
            )


def test_an_archetype_missing_its_quantity_is_unresolved_not_omitted():
    """A proof test whose rated load nobody supplied is not a plan."""
    plan = plan_verification(_lifter_card(), parameters={})
    assert plan.items == ()
    reasons = dict(plan.unresolved)
    assert "rated_load" in reasons["beam bending"]
    assert "Proof load test needs" in reasons["beam bending"]
    assert "tolerance" in reasons["pin fit"]
    assert plan.status is CheckStatus.NOT_EVALUATED


def test_analysis_only_checks_are_counted_rather_than_left_off_the_matrix():
    """'12 checks, 2 tests' and '12 checks, 12 tests' must not render identically."""
    plan = plan_verification(
        _lifter_card(), parameters={"rated_load": _q("100 kN"), "tolerance": _q("0.05 mm")}
    )
    assert plan.analysis_only == ("weld throat",)
    assert "weld throat" in plan.matrix()
    assert "analysis" in plan.matrix()
    assert "1 by analysis alone" in plan.summary()


def test_the_hydrostatic_criterion_carries_ug99_and_names_the_pneumatic_alternative():
    card = Scorecard(entries=(_entry("shell wall", reference="ASME VIII Div 1 UG-27", factor=2.1),))
    plain = plan_verification(card, parameters={"mawp": _q("2 MPa")})
    item = plain.items[0]
    # 1.3 x MAWP with no stress ratio supplied, and it says the ratio was taken as 1.0.
    assert "2.6 MPa" in item.acceptance
    assert "taken as 1.0" in item.acceptance
    assert "UG-100 runs at 1.1" in item.acceptance
    assert item.archetype.citation == "ASME VIII Div 1 UG-99(b)"
    # With the ratio, the test pressure moves with it — hot design, colder test.
    derated = plan_verification(
        card,
        parameters={
            "mawp": _q("2 MPa"),
            "stress_ratio": Quantity(magnitude=1.2, unit="dimensionless"),
        },
    )
    assert "3.12 MPa" in derated.items[0].acceptance


def test_a_practice_default_says_it_is_one():
    """The 10:1 accuracy ratio is measurement practice, not a clause Anvilate cites."""
    plan = plan_verification(
        Scorecard(entries=(_entry("pin fit", reference="ISO 286 H7/g6"),)),
        parameters={"tolerance": _q("0.05 mm")},
    )
    item = plan.items[0]
    assert item.archetype.practice_default is True
    assert item.archetype.method is VerificationMethod.INSPECTION
    assert "0.005 mm" in item.required_accuracy
    assert "not a cited clause" in item.required_accuracy
    # And the archetypes that DO carry a clause are not marked as practice defaults.
    assert [a.key for a in DEFAULT_ARCHETYPES if not a.practice_default] == [
        "proof-load",
        "hydrostatic",
    ]


def test_routing_runs_off_the_citation_not_the_check_name():
    """A caller names checks freely; the clause they cite is not theirs to choose."""
    misleading = Scorecard(
        entries=(
            _entry("proof load test", reference="AWS D1.1 fillet weld"),
            _entry("something else entirely", reference=_BTH1),
        )
    )
    plan = plan_verification(misleading, parameters={"rated_load": _q("50 kN")})
    assert plan.analysis_only == ("proof load test",)
    assert plan.items[0].driving_checks == ("something else entirely",)
