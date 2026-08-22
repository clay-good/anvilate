"""The assembled evidence bundle: the cross-layer roll-up and what it refuses to imply."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from anvilate.attestation import (
    AIDisclosure,
    Component,
    ComponentKind,
    EnvironmentBOM,
    Subject,
    sha256_hex,
)
from anvilate.bundle import BundleSections, assemble_evidence_bundle
from anvilate.callouts import CalloutSet, ProductionMethod, SurfaceFinish
from anvilate.review import ReviewRecord, artifact_digest, build_dossier
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity
from anvilate.verification import (
    VerificationArchetype,
    VerificationItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationPlan,
)

TOOLCHAIN = "anvilate 0.0.1"


def _q(magnitude: float, unit: str) -> Quantity:
    return Quantity(magnitude=magnitude, unit=unit)


def _card(*, passing: bool = True) -> Scorecard:
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "pin bearing", computed=2.7 if passing else 0.8, required=2.0
            ),
            ScorecardEntry.from_safety_factor("net tension", computed=2.2, required=2.0),
        )
    )


def _archetype() -> VerificationArchetype:
    return VerificationArchetype(
        key="proof_load",
        method=VerificationMethod.TEST,
        title="proof load test",
        citation="ASME B30.20 / OSHA 29 CFR 1926.251(a)(4)",
    )


def _plan(*, performed: bool) -> VerificationPlan:
    outcome = (
        VerificationOutcome(
            passed=True,
            measured="no permanent set at 125% of rated load",
            performed_on=date(2026, 8, 20),
            performed_by="Test Lab Ltd, cert 1234",
            instrument="calibrated load cell, cal due 2027-01",
        )
        if performed
        else None
    )
    return VerificationPlan(
        items=(
            VerificationItem(
                name="lug proof load",
                archetype=_archetype(),
                driving_checks=("pin bearing", "net tension"),
                acceptance="no permanent deformation at 125% of the rated load",
                outcome=outcome,
            ),
        ),
        analysis_only=(),
        unresolved=(),
    )


def _bom() -> EnvironmentBOM:
    return EnvironmentBOM(
        application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION),
        components=(Component(name="pydantic", version="2.9.2"),),
    )


def _sections(**overrides) -> BundleSections:
    fields = {"scorecard": _card()}
    fields.update(overrides)
    return BundleSections(**fields)


# --- the floor -------------------------------------------------------------------------


def test_a_bundle_needs_at_least_one_check():
    with pytest.raises(ValidationError, match="nothing to be evidence of"):
        BundleSections(scorecard=Scorecard())


def test_a_scorecard_only_bundle_is_legitimate_and_says_what_it_is_not():
    sections = _sections()
    assert sections.covers() == ("checks",)
    assert set(sections.missing()) == {"verification", "review", "exploration", "callouts"}
    assert sections.status is CheckStatus.PASS
    # Passing the checks is not being verified, and the summary says both.
    assert sections.verified is False
    assert "not test-verified" in sections.summary()


# --- a plan is not evidence, and the bundle inherits it -----------------------------------


def test_an_unperformed_plan_pulls_a_green_bundle_down():
    sections = _sections(verification=_plan(performed=False))
    assert sections.scorecard.status is CheckStatus.PASS
    assert sections.verification.status is CheckStatus.NOT_EVALUATED
    # The layer that would have said "verified" has not said it yet.
    assert sections.status is CheckStatus.NOT_EVALUATED
    assert sections.verified is False


def test_a_performed_plan_over_passing_checks_is_the_only_verified_state():
    sections = _sections(verification=_plan(performed=True))
    assert sections.status is CheckStatus.PASS
    assert sections.verified is True
    assert "test-verified" in sections.summary()


def test_verified_is_never_true_without_a_plan():
    assert _sections().verified is False


def test_a_failing_check_fails_the_bundle_even_with_every_test_performed():
    sections = _sections(scorecard=_card(passing=False), verification=_plan(performed=True))
    assert sections.status is CheckStatus.FAIL
    # And `verified` is about the tests, not the verdict — it stays honest either way.
    assert sections.verified is True


# --- a review that no longer applies is not a review ---------------------------------------


def _dossier(*, stale: bool) -> object:
    card = _card()
    record = ReviewRecord(
        reviewer="A. Engineer, P.E.",
        reviewed_on=date(2026, 8, 1),
        covers_digest=artifact_digest(card, toolchain="anvilate 0.0.0" if stale else TOOLCHAIN),
        scope="both lug checks",
    )
    return build_dossier(card, toolchain=TOOLCHAIN, record=record)


def test_a_stale_review_degrades_the_bundle_rather_than_sitting_as_a_flag():
    fresh = _sections(review=_dossier(stale=False))
    assert fresh.status is CheckStatus.PASS

    stale = _sections(review=_dossier(stale=True))
    assert stale.review.stale_record is True
    # The dossier's own status is the scorecard's, so without this the staleness would be
    # lost in the roll-up — and "reviewed" and "reviewed, then the artifact moved" look
    # identical from the outside.
    assert stale.status is CheckStatus.NOT_EVALUATED
    assert "no longer applies" in stale.render()  # in the review section, by name


# --- the roll-up precedence ------------------------------------------------------------------


def test_the_roll_up_never_reports_better_than_its_worst_layer():
    sections = _sections(
        scorecard=_card(passing=False),
        verification=_plan(performed=False),
        review=_dossier(stale=True),
    )
    # FAIL outranks NOT_EVALUATED, exactly as the scorecard's own roll-up orders them.
    assert sections.status is CheckStatus.FAIL
    assert [s.status for s in sections.sections()] == [
        CheckStatus.FAIL,
        CheckStatus.NOT_EVALUATED,
        CheckStatus.NOT_EVALUATED,
    ]


def test_an_over_margin_check_is_visible_without_blocking():
    over = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("pin bearing", computed=9.0, required=2.0, upper=4.0),
        )
    )
    sections = _sections(scorecard=over, verification=_plan(performed=True))
    assert sections.status is CheckStatus.OVER_MARGIN


def test_every_section_appears_in_the_rendering():
    sections = _sections(
        verification=_plan(performed=True),
        review=_dossier(stale=False),
        callouts=CalloutSet(
            callouts=(
                SurfaceFinish(
                    scope="pin_bore", roughness=_q(1.6, "um"), method=ProductionMethod.MACHINED
                ),
            )
        ),
        ultimate_strength=_q(655, "MPa"),
    )
    rendered = sections.render()
    for name in ("checks", "verification", "review", "callouts"):
        assert name in rendered
    assert sections.covers() == ("checks", "verification", "review", "callouts")
    assert sections.missing() == ("exploration",)


def test_a_callout_section_with_no_strength_reports_not_evaluated_not_absent():
    # The distinction the bundle exists to keep: the callouts are declared and carried, and
    # the layer could not conclude. That is different from no callouts at all.
    sections = _sections(
        callouts=CalloutSet(
            callouts=(
                SurfaceFinish(
                    scope="pin_bore", roughness=_q(1.6, "um"), method=ProductionMethod.MACHINED
                ),
            )
        )
    )
    assert "callouts" in sections.covers()
    assert sections.status is CheckStatus.NOT_EVALUATED
    assert sections.callout_card().status is CheckStatus.NOT_EVALUATED


# --- assembly into an attestable bundle ---------------------------------------------------------


def test_the_assembled_bundle_carries_the_roll_up_into_the_predicate():
    sections = _sections(verification=_plan(performed=True))
    bundle = assemble_evidence_bundle(
        sections,
        subjects=(),
        artifacts={"scorecard.json": b'{"status":"pass"}'},
        spec_digest=sha256_hex(b"the spec"),
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    body = bundle.statement()["predicate"]
    assert body["sections"]["status"] == "pass"
    assert body["sections"]["testVerified"] is True
    assert body["sections"]["covers"] == ["checks", "verification"]
    assert body["sections"]["missing"] == ["review", "exploration", "callouts"]
    # A verifier reads the roll-up the reviewer saw rather than recomputing it.
    assert [s["name"] for s in body["sections"]["sections"]] == ["checks", "verification"]


def test_the_assembled_bundle_is_still_content_addressed_and_reproducible():
    kwargs = {
        "spec_digest": sha256_hex(b"the spec"),
        "bom": _bom(),
        "ai_disclosure": AIDisclosure.none(),
        "artifacts": {"scorecard.json": b'{"status":"pass"}'},
    }
    first = assemble_evidence_bundle(_sections(), subjects=(), **kwargs)
    second = assemble_evidence_bundle(_sections(), subjects=(), **kwargs)
    assert first.digest == second.digest
    # And a layer arriving changes the address, because the bundle now claims more.
    with_plan = assemble_evidence_bundle(
        _sections(verification=_plan(performed=True)), subjects=(), **kwargs
    )
    assert with_plan.digest != first.digest


def test_supplying_both_subjects_and_artifacts_is_an_error_not_a_merge():
    with pytest.raises(ValueError, match="not both"):
        assemble_evidence_bundle(
            _sections(),
            subjects=(Subject.over("a.dxf", b"one"),),
            artifacts={"b.dxf": b"two"},
            spec_digest=sha256_hex(b"the spec"),
            bom=_bom(),
            ai_disclosure=AIDisclosure.none(),
        )


def test_artifacts_become_subjects_in_a_stable_order():
    bundle = assemble_evidence_bundle(
        _sections(),
        subjects=(),
        artifacts={"z.dxf": b"z", "a.json": b"a"},
        spec_digest=sha256_hex(b"the spec"),
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    assert [s.name for s in bundle.subjects] == ["a.json", "z.dxf"]


def test_a_predicate_without_sections_is_unchanged():
    # The field is additive: a bundle built straight through the attestation layer, with no
    # sections at all, must produce the same predicate body it always did.
    from anvilate.attestation import AnvilatePredicate

    predicate = AnvilatePredicate(
        spec_digest=sha256_hex(b"the spec"),
        scorecard=_card(),
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    assert "sections" not in predicate.to_json_dict()
