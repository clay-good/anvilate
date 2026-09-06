"""The assembled evidence bundle: the cross-layer roll-up and what it refuses to imply."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

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
from anvilate.bundle import SCREENING_DISCLAIMER, BundleSections, assemble_evidence_bundle
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
    assert set(sections.missing()) == {
        "design basis",
        "verification",
        "review",
        "exploration",
        "callouts",
        "load combinations",
        "export",
        "geometric tolerances",
    }
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
    assert sections.missing() == (
        "design basis",
        "exploration",
        "load combinations",
        "export",
        "geometric tolerances",
    )


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
    assert body["sections"]["missing"] == [
        "design basis",
        "review",
        "exploration",
        "callouts",
        "load combinations",
        "export",
        "geometric tolerances",
    ]
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


# --- what a mutation run over this file left standing ------------------------------------
#
# Six mutants survived the first version of these tests, and the precedence one mattered
# most: both the module docstring and the docs page stake the claim "identical to
# `Scorecard` by construction", and the only pair that claim is really about — OVER_MARGIN
# against NOT_EVALUATED — had no test. `test_an_over_margin_check_is_visible_without_
# blocking` paired OVER_MARGIN with a *passing* plan, so swapping the two in `_PRECEDENCE`
# changed nothing. Neither `exploration` nor `frames` was constructed by any test at all.


def test_not_evaluated_outranks_over_margin_exactly_as_the_scorecard_orders_them():
    over = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("pin bearing", computed=9.0, required=2.0, upper=4.0),
        )
    )
    sections = _sections(scorecard=over, verification=_plan(performed=False))
    assert over.status is CheckStatus.OVER_MARGIN
    assert sections.verification.status is CheckStatus.NOT_EVALUATED
    # A gap outranks an over-engineered pass, which is what Scorecard does too.
    assert sections.status is CheckStatus.NOT_EVALUATED
    # And prove the two orderings agree rather than asserting they were written to.
    mixed = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("a", computed=9.0, required=2.0, upper=4.0),
            ScorecardEntry(name="b", status=CheckStatus.NOT_EVALUATED, detail="no data"),
        )
    )
    assert mixed.status is CheckStatus.NOT_EVALUATED


def test_the_roll_up_refuses_a_section_set_with_nothing_to_judge():
    from anvilate.bundle import _worst

    with pytest.raises(ValueError, match="at least one section that is a verdict"):
        _worst([])


def test_an_exploration_section_is_carried_and_is_not_a_verdict_about_the_part():
    """A sweep says what the design space contains, not whether this part is sound.

    Letting it into the roll-up would mean an exhaustive sweep with nothing feasible in it
    condemning a part that passes every check on its own drawing.
    """
    from anvilate.explore import (
        Objective,
        ObjectiveSense,
        Parameter,
        Study,
        StudyEvaluation,
        run_study,
    )

    study = Study(
        name="wall thickness",
        parameters=(Parameter(name="t", low=4.0, high=6.0, unit="mm", steps=2),),
        objectives=(Objective(name="mass", sense=ObjectiveSense.MINIMIZE),),
    )
    infeasible = run_study(
        study,
        evaluate=lambda point: StudyEvaluation(
            objectives={"mass": point["t"]},
            scorecard=Scorecard(
                entries=(ScorecardEntry.from_safety_factor("wall", computed=0.5, required=2.0),)
            ),
        ),
    )
    sections = _sections(exploration=infeasible)
    section = next(s for s in sections.sections() if s.name == "exploration")
    assert section.informational is True
    assert section.status is CheckStatus.NOT_EVALUATED
    assert "exploration" in sections.covers()
    # Carried, rendered, and not dragging a passing part down with it.
    assert sections.status is CheckStatus.PASS
    assert "(informational)" in sections.render()


def test_a_geometric_tolerance_section_is_carried_and_is_not_a_verdict_either():
    from anvilate.gdt import Characteristic, FeatureControlFrame, FeatureType

    frame = FeatureControlFrame(
        characteristic=Characteristic.FLATNESS,
        tolerance=_q(0.05, "mm"),
        feature_type=FeatureType.SURFACE,
    )
    sections = _sections(frames=(frame,))
    section = next(s for s in sections.sections() if s.name == "geometric tolerances")
    assert section.informational is True
    assert section.status is CheckStatus.PASS
    assert "geometric tolerances" in sections.covers()
    assert "geometric tolerances" not in sections.missing()


def test_the_predicate_headline_verdict_is_the_roll_up_not_the_scorecard():
    """One verdict in the statement, and it is the pessimistic one.

    A signed document used to read ``"status": "pass"`` at the top with
    ``"sections": {"status": "not_evaluated"}`` underneath. Standard attestation tooling
    reads the top.
    """
    sections = _sections(verification=_plan(performed=False))
    assert sections.scorecard.status is CheckStatus.PASS
    assert sections.status is CheckStatus.NOT_EVALUATED
    bundle = assemble_evidence_bundle(
        sections,
        subjects=(),
        artifacts={"scorecard.json": b'{"status":"pass"}'},
        spec_digest=sha256_hex(b"the spec"),
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    body = bundle.statement()["predicate"]
    assert body["status"] == "not_evaluated"
    assert body["sections"]["status"] == "not_evaluated"


def test_a_sections_payload_that_is_not_an_object_is_refused():
    from anvilate.attestation import AnvilatePredicate

    common = {
        "spec_digest": sha256_hex(b"the spec"),
        "scorecard": _card(),
        "bom": _bom(),
        "ai_disclosure": AIDisclosure.none(),
    }
    for payload, match in (
        ("[1, 2, 3]", "must encode an object"),
        ('"a string"', "must encode an object"),
        ("not json", "not readable JSON"),
        ('{"status": "probably fine"}', "not one of"),
    ):
        with pytest.raises(ValidationError, match=match):
            AnvilatePredicate(sections_json=payload, **common)


def test_the_bundle_digest_survives_a_material_database_that_differs_only_by_case():
    """The case fold used to be built from a set, so which spelling won was hash order.

    That spelling reaches the heat-treatment entry's detail, the sections payload, and the
    content address — so the same inputs hashed differently between processes.
    """
    script = (
        "import sys; sys.path.insert(0, 'tests');"
        "from test_bundle import _case_folded_digest; print(_case_folded_digest())"
    )
    digests = set()
    for seed in ("0", "2", "5"):
        env = os.environ | {"PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        out = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(Path(__file__).resolve().parent.parent),
            env=env,
        )
        digests.add(out.stdout.strip())
    assert len(digests) == 1, f"the digest depends on the interpreter's hash seed: {digests}"


def _case_folded_digest() -> str:
    """A bundle whose material lookup has to fold two ids differing only by case."""
    from anvilate.callouts import HeatTreatment

    sections = BundleSections(
        scorecard=_card(),
        callouts=CalloutSet(
            callouts=(HeatTreatment(scope=None, specification="AMS 2759", condition="1"),)
        ),
        base_material="X-1",
        known_materials=("X-1", "x-1"),
    )
    return assemble_evidence_bundle(
        sections,
        subjects=(),
        artifacts={"scorecard.json": b'{"status":"pass"}'},
        spec_digest=sha256_hex(b"the spec"),
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    ).digest


# --- the governing combination, carried into the bundle -------------------------------


def _combination_evidence(**kwargs):
    from anvilate.loads import LoadNature, asce7_lrfd_basic, combination_evidence

    defaults = {"loads": {LoadNature.DEAD: 10_000.0}}
    loads = kwargs.pop("loads", defaults["loads"])
    return combination_evidence(asce7_lrfd_basic(), loads, **kwargs)


def test_the_bundle_names_the_governing_combination():
    sections = BundleSections(scorecard=_card(), combinations=_combination_evidence())
    row = next(s for s in sections.sections() if s.name == "load combinations")
    assert row.status is CheckStatus.PASS
    assert "LRFD" in row.detail and "§2.3.1" in row.detail
    assert not row.informational, (
        "which combination the checks were screened against is a statement about this "
        "part, so it belongs in the roll-up"
    )
    assert sections.status is CheckStatus.PASS


def test_an_unclassified_load_case_drops_a_green_bundle_to_not_evaluated():
    """The whole point of carrying it: the scorecard passes and the bundle does not.

    The checks were screened against a demand summed from part of the declared loads, and
    nothing in the scorecard says so — this is the layer that does.
    """
    sections = BundleSections(
        scorecard=_card(),
        combinations=_combination_evidence(unclassified=("lateral_thrust",)),
    )
    assert sections.scorecard.status is CheckStatus.PASS
    assert sections.status is CheckStatus.NOT_EVALUATED
    assert "lateral_thrust" in sections.render()


def test_a_bundle_with_no_combination_basis_says_so_rather_than_implying_one():
    sections = BundleSections(scorecard=_card())
    assert "load combinations" in sections.missing()
    assert "load combinations" not in sections.covers()


# --- The design basis: absent is named, and a real split blocks -------------------------


def _cited(*references: str) -> Scorecard:
    return Scorecard(
        entries=tuple(
            ScorecardEntry(
                name=f"check {index}",
                status=CheckStatus.PASS,
                detail="ok",
                reference=reference,
            )
            for index, reference in enumerate(references)
        )
    )


def test_a_bundle_with_no_design_basis_says_so_rather_than_omitting_the_idea():
    """`missing()` is what a reviewer reads to find out what was *not* looked at.

    Before this, "design basis" appeared in neither `covers()` nor `missing()`, so a
    bundle whose citations nobody checked against an adopted edition and one whose
    citations check out rendered identically. The concept was not absent from the answer —
    it was absent from the question.
    """
    sections = BundleSections(scorecard=_cited("AISC 360-16 §J4.1"))
    assert "design basis" in sections.missing()
    assert "design basis" not in sections.covers()


def test_citations_at_two_editions_fail_the_bundle_rather_than_riding_along():
    """A FAIL here is evidence that misrepresents itself, so it enters the roll-up.

    The bundle reads as though every number came from one book, and it did not. A roll-up
    reporting PASS over that would be doing the same thing one level up.
    """
    from anvilate.standards import DesignBasis

    sections = BundleSections(
        scorecard=_cited("AISC 360-16 §J4.1", "AISC 360-22 §J4.3"),
        design_basis=DesignBasis(),
    )
    assert "design basis" in sections.covers()
    assert sections.status is CheckStatus.FAIL
    rendered = sections.render()
    assert "editions 16, 22" in rendered
    assert "(informational)" not in rendered.split("design basis")[1].split("\n")[0]


def test_unversioned_citations_do_not_degrade_a_bundle_whose_checks_ran():
    """The ordinary case, and the reason this section is informational until it fails.

    Most references in this library name a clause and no edition — `ASME BTH-1 §3-3` names
    a paragraph in a book nobody dated. Letting that NOT_EVALUATED into the roll-up would
    put nearly every bundle at NOT_EVALUATED over checks that ran and passed, which teaches
    a reader to ignore the status line. It is reported, in full, and marked informational.
    """
    from anvilate.standards import DesignBasis

    sections = BundleSections(scorecard=_cited("ASME BTH-1 §3-3"), design_basis=DesignBasis())
    assert sections.status is CheckStatus.PASS
    rendered = sections.render()
    assert "design basis (informational)" in rendered
    assert "name no edition" in rendered


def test_a_consistent_basis_passes_and_says_what_it_checked():
    from anvilate.standards import DesignBasis

    sections = BundleSections(
        scorecard=_cited("AISC 360-16 §J4.1", "AISC 360-16 §J4.3"),
        design_basis=DesignBasis(),
    )
    assert sections.status is CheckStatus.PASS
    assert "all 2 references name an edition" in sections.render()


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("base_material", "   ", "a blank base material"),
        ("known_materials", ("",), "a blank entry in known_materials"),
        ("assumptions", ("",), "a blank modelling assumption"),
    ],
)
def test_a_blank_section_is_refused_the_way_the_neighbouring_ones_are(field, value, expected):
    """`assumptions` and `design_basis` already refused a blank; the two material fields did
    not, and they are the ones a reader follows.

    A bundle naming its base material as three spaces renders a material line nobody can
    resolve — worse than the `None` that means "this bundle does not say", because the None
    is reported by `missing()` and the blank reads as an answer.
    """
    with pytest.raises(ValidationError, match=expected):
        BundleSections(scorecard=_card(), **{field: value})


def test_the_material_fields_are_still_optional():
    """The refusal is about a blank, not about an absence: a bundle that names no base
    material is an ordinary bundle, and `missing()` is where that is reported."""
    sections = BundleSections(scorecard=_card())
    assert sections.base_material is None
    assert sections.known_materials == ()


# ------------------------------------------------------- the bundle a reviewer receives


def _a_card_worth_reading() -> Scorecard:
    """A card with all three verdicts on it, so a rendering that drops one is visible."""
    return Scorecard(
        entries=(
            ScorecardEntry(
                name="net tension",
                status=CheckStatus.PASS,
                detail="safety factor 4.40 vs required minimum 1.50",
                reference="ASME BTH-1 §3-3",
            ),
            ScorecardEntry.from_safety_factor("pin bearing", computed=1.1, required=1.5),
            ScorecardEntry(
                name="material resolution",
                status=CheckStatus.NOT_EVALUATED,
                detail="unknown material 'NOT-A-REAL-ALLOY'",
            ),
        )
    )


def test_the_rollup_counts_the_over_margin_checks_that_set_its_own_status():
    """A status with no supporting count is the roll-up's version of a silent green.

    The checks line gave "N run, M failing, K not evaluated" and no more, so a card whose
    status is OVER_MARGIN rendered as

        [OVER_MARGIN] checks: 3 run, 0 failing, 0 not evaluated

    — the verdict on the left, and under it two zeroes accounting for none of it. The
    roll-up is the whole document some readers see.
    """
    banded = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "net tension", computed=6.67, required=2.0, upper=4.0
            ),
            ScorecardEntry.from_safety_factor("pin bearing", computed=2.4, required=2.0),
        )
    )
    line = next(s for s in BundleSections(scorecard=banded).sections() if s.name == "checks")
    assert line.status is CheckStatus.OVER_MARGIN
    assert line.detail == "2 run, 0 failing, 0 not evaluated, 1 over margin"

    # A band is opt-in, so a card without one reads exactly as it always did: printing
    # "0 over margin" on every bundle in the library teaches a reader to skip the field.
    plain = next(s for s in BundleSections(scorecard=_card()).sections() if s.name == "checks")
    assert plain.detail == "2 run, 0 failing, 0 not evaluated"
    assert "over margin" not in plain.detail


def test_the_exported_bundle_carries_every_check_and_the_rollup_does_not():
    """`artifact-export` asks the bundle to carry "the scorecard with thresholds and measured
    values", and its scenario is an engineer who receives **only the bundle**.

    For a long time both export surfaces handed that engineer `render()` — the roll-up over
    layers, whose checks line reads `3 run, 1 failing, 0 not evaluated` and names nothing.
    Which check failed, at what margin, against which clause: none of it was in the document.
    The requirement was quoted in a spec and enforced nowhere, and the reason it survived is
    that `render()` was correct for the consumer it was written for — the attestation
    predicate, which carries the card in its own field beside the roll-up.

    So the two are asserted apart. The roll-up must stay silent about individual checks,
    because moving it moves the canonical form under every signature already given; the
    exported document must name all of them.
    """
    sections = BundleSections(scorecard=_a_card_worth_reading())

    rollup = sections.render()
    document = sections.render_document()
    for entry in sections.scorecard.entries:
        assert entry.name not in rollup, f"the roll-up names {entry.name}; its digest is signed"
        assert entry.name in document, f"the exported bundle does not name {entry.name}"
        assert str(entry) in document, f"{entry.name} is named without its detail"
    # The clause a check cites travels with it, which is the half a reviewer checks against
    # the standard on their own desk.
    assert "ASME BTH-1 §3-3" in document
    assert SCREENING_DISCLAIMER in document
    # And the disclaimer stays last: a label a reader scrolls past the evidence to find is
    # one they read after forming the opinion it exists to qualify.
    assert document.rstrip().endswith(SCREENING_DISCLAIMER)


def test_the_exported_json_carries_the_card_and_the_predicates_form_does_not():
    """The same split, in JSON. `to_json_dict` is hashed into `sections_json`."""
    sections = BundleSections(scorecard=_a_card_worth_reading())
    rollup = sections.to_json_dict()
    document = sections.to_document_dict()

    assert "scorecard" not in rollup
    assert "spec" not in rollup
    assert document["scorecard"] == sections.scorecard.model_dump(mode="json")
    # The document is a superset: every key of the roll-up survives with its value, so a
    # client reading the roll-up's keys off the exported bundle is not reading a different
    # document that happens to share a name.
    assert all(document[key] == value for key, value in rollup.items())
    assert set(document) - set(rollup) == {"scorecard", "spec"}
    # `spec` is present and null rather than absent, so a consumer can tell "this bundle
    # carries no spec" from "a key I did not think to look for".
    assert document["spec"] is None


def test_a_bundle_over_an_empty_card_cannot_be_constructed_to_be_rendered():
    """Why `render_document` has no empty-checks branch, asserted rather than assumed.

    The first draft of it carried one — a "checks: none on the card" line, so a bundle whose
    card was empty could not render identically to one whose checks nobody printed. The line
    was unreachable: the model refuses the bundle a step earlier. An unreachable branch is a
    claim about behaviour nobody can observe, so it went, and this is what took its place.
    """
    with pytest.raises(ValidationError, match="nothing to be evidence of"):
        BundleSections(scorecard=Scorecard())


def test_the_attested_predicate_still_carries_the_rollup_and_not_the_document():
    """The reason the split exists, asserted where it would actually go wrong.

    Folding the card into `to_json_dict` would have been the one-line fix, and it would have
    moved the canonical form hashed into every predicate — invalidating attestations already
    signed — and put two copies of one scorecard inside one signed document, which is two
    chances for them to disagree.
    """
    import json

    sections = BundleSections(scorecard=_a_card_worth_reading())
    bundle = assemble_evidence_bundle(
        sections,
        subjects=(),
        artifacts={"scorecard.json": b'{"status":"fail"}'},
        spec_digest="a" * 64,
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    carried = json.loads(bundle.predicate.sections_json)
    assert carried == sections.to_json_dict()
    assert "scorecard" not in carried
    # It is carried once, in the field that exists for it.
    assert bundle.predicate.scorecard == sections.scorecard


def test_the_exported_bundle_shows_the_work_not_only_the_verdict():
    """The reader this document is for receives only the bundle and re-runs the analysis.

    A verdict and a clause cannot be re-run: the formula, the values put into it and the
    result are what a checker recomputes, and the library carries them for most of the
    clauses it cites. Leaving them out made the exported bundle a document that names its
    conclusions and withholds their arithmetic — the same shape as the defect this
    rendering already fixed once, when both export surfaces were handing a reviewer the
    roll-up and calling it evidence.
    """
    from anvilate.packs.structural import LiftingLug, screen_lifting_lug
    from anvilate.report import ReportSection
    from anvilate.units import Quantity

    card = screen_lifting_lug(
        LiftingLug(
            name="padeye",
            width=Quantity.parse("80 mm"),
            hole_diameter=Quantity.parse("25 mm"),
            thickness=Quantity.parse("12 mm"),
            load=Quantity.parse("50 kN"),
            material="ASTM-A36",
        ),
        required_safety_factor=2.0,
    )
    document = BundleSections(scorecard=card).render_document()

    worked = [entry for entry in card.entries if ReportSection(entry=entry).is_worked]
    assert worked, "the lug screen stopped writing derivations; this test sees nothing"
    for entry in worked:
        for line in ReportSection(entry=entry).worked_lines():
            assert line.strip() in document, f"the bundle dropped a line of the work: {line!r}"

    # The roll-up is untouched: its canonical form is hashed into signed attestations.
    rollup = BundleSections(scorecard=card)._render_rollup()
    assert "where:" not in rollup
    assert "where:" in document

    # And every check still has its own line, worked or not.
    for entry in card.entries:
        assert f"  {entry}" in document


@pytest.mark.parametrize(
    "verdict, entry",
    [
        (CheckStatus.PASS, ScorecardEntry.from_safety_factor("a", computed=3.0, required=2.0)),
        (CheckStatus.FAIL, ScorecardEntry.from_safety_factor("a", computed=0.5, required=2.0)),
        (
            CheckStatus.OVER_MARGIN,
            ScorecardEntry.from_safety_factor("a", computed=9.0, required=2.0, upper=3.0),
        ),
        (
            CheckStatus.NOT_EVALUATED,
            ScorecardEntry(name="a", status=CheckStatus.NOT_EVALUATED, detail="no cycle data"),
        ),
    ],
    ids=lambda value: value.value if isinstance(value, CheckStatus) else "",
)
def test_every_bundle_surface_carries_the_disclaimer_and_its_status(verdict, entry):
    """`headless-automation`: a bundle "SHALL carry the screening disclaimer and its own
    rolled-up status in every case".

    Every case is both halves of a product nobody had swept: each verdict a card can roll up
    to, against each surface a caller can receive a bundle through. The scenarios covered
    pass and fail through the readable rendering; a caller taking the structured content —
    which is what the MCP export tool returns — was reading a different renderer.
    """
    sections = BundleSections(scorecard=Scorecard(entries=(entry,)))
    assert sections.status is verdict, "the fixture no longer produces the verdict it names"

    for name in ("render", "render_document", "to_document_dict", "to_json_dict"):
        produced = getattr(sections, name)()
        blob = produced if isinstance(produced, str) else json.dumps(produced, default=str)
        assert SCREENING_DISCLAIMER in blob, (
            f"{name}() returns a bundle with no screening disclaimer on it"
        )
        # Read the status the surface itself declares, not any occurrence of the word. A
        # substring search over the whole rendering is satisfied by the single check's own
        # status and passes with the bundle's roll-up deleted outright — measured.
        if isinstance(produced, dict):
            declared = produced.get("status")
        else:
            declared = produced.splitlines()[0].split()[1].lower()
        assert declared == verdict.value.replace("_", " ") or declared == verdict.value, (
            f"{name}() rolled up to {declared!r}, not to the {verdict.value} it stands on"
        )


def test_the_evidence_bundle_pages_worked_block_is_what_the_bundle_prints():
    """The block on `docs/evidence-bundle.md`, held against the document it claims to show.

    The page now argues from numbers — a safety factor, a stress, four dimensions — and a
    number quoted only in prose has no gate on it. These are not typed into the page from
    a run somebody remembers; every line of the block has to appear in the bundle the
    library renders for the lug the block names.
    """
    import re
    from pathlib import Path

    from anvilate.packs.structural import LiftingLug, screen_lifting_lug
    from anvilate.units import Quantity

    page = (Path(__file__).resolve().parent.parent / "docs" / "evidence-bundle.md").read_text(
        encoding="utf-8"
    )
    block = re.search(r"```text\nchecks:\n(.*?)```", page, re.S)
    assert block is not None, "the worked block on docs/evidence-bundle.md has moved"

    # The lug the block shows: the padeye of examples/padeye.spec.yaml.
    card = screen_lifting_lug(
        LiftingLug(
            name="padeye",
            width=Quantity.parse("120 mm"),
            hole_diameter=Quantity.parse("40 mm"),
            thickness=Quantity.parse("20 mm"),
            load=Quantity.parse("60 kN"),
            material="ASTM-A36",
        ),
        required_safety_factor=2.0,
    )
    document = BundleSections(scorecard=card).render_document()
    missing = [
        line for line in block.group(1).splitlines() if line.strip() and line not in document
    ]
    assert not missing, (
        "these lines are on the page and not in the rendered bundle:\n  " + "\n  ".join(missing)
    )


def test_the_bundle_shows_its_work_in_the_units_the_spec_it_carries_declares():
    """The reader of a bundle receives only the bundle, and it carries the spec.

    So the one line of that spec saying what units its reader works in is *in the same
    file*, forty lines below a formula substituted in the other system. A document stating
    `units: US` was handed to its reviewer in millimetres and megapascals.
    """
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    source = (Path(__file__).resolve().parent.parent / "examples" / "padeye.spec.yaml").read_text()
    assert "units: {value: SI" in source, "the fixture spec no longer declares SI"

    for declared, wanted, unwanted in (("SI", " mm", "kip"), ("US", "kip", " mm")):
        spec = load_spec_yaml(source.replace("units: {value: SI", f"units: {{value: {declared}"))
        sections = BundleSections(scorecard=screen_spec(spec), spec=spec)
        # Only the checks block: the spec is echoed below it in the units it was written in,
        # which is the document rather than a rendering of it.
        checks = sections.render_document().split("spec:")[0]
        assert wanted in checks, checks
        assert unwanted not in checks, checks


def test_the_bundle_headline_is_the_entrys_own_line():
    """The check line is `ScorecardEntry.__str__` with its verdict restated, not a copy.

    A hand-built version at this call site dropped the fragility warning — a nominal pass
    that input scatter would fail one time in five printed exactly like one that never
    does, in the document a reviewer receives instead of the analysis.
    """
    from anvilate.report import ReportSection
    from anvilate.uncertainty import MarginUncertainty, Sensitivity

    plain = ScorecardEntry.from_safety_factor("bending", computed=1.9, required=1.5).model_copy(
        update={"reference": "AISC 360-16 §F2"}
    )
    assert ReportSection(entry=plain).headline() == str(plain)

    # Through the BUNDLE, not through `headline` alone. The first version of this test
    # asserted the helper and passed while `render_document` still built the line by hand
    # and still dropped the warning — a gate on the fix rather than on the thing fixed.

    fragile = plain.model_copy(
        update={
            "uncertainty": MarginUncertainty(
                samples=1000,
                seed=1,
                required=1.5,
                mean=1.9,
                std=0.4,
                shortfall_probability=0.2,
                lower=1.2,
                upper=2.6,
                coverage=0.9,
                sensitivities=(Sensitivity(name="load", variance_share=1.0),),
            )
        }
    )
    assert "fragile" in ReportSection(entry=fragile).headline()
    assert ReportSection(entry=fragile).headline() == str(fragile)

    rendered = BundleSections(scorecard=Scorecard(entries=(fragile,))).render_document()
    assert "fragile: 20.0% of samples fall short" in rendered, rendered


# --- every key the document can carry -------------------------------------------------


def _every_section() -> BundleSections:
    """A bundle carrying every optional section at once.

    Nothing in the suite built one. Across a whole run, `to_document_dict` produced only its
    nine unconditional keys — and of the seven conditional ones, `verification` and `exports`
    appeared solely in a *predicate body*, while `review`, `exploration`, `callouts`,
    `calloutScorecard` and `geometricTolerances` were produced by no test at all. Seven
    branches of the one method both export surfaces render, none of them ever taken.
    """
    from anvilate.evidence import SourceRecord
    from anvilate.explore import Objective, Parameter, Study, StudyEvaluation, run_study
    from anvilate.export.gate import ExportRecord, authorize_export
    from anvilate.gdt import (
        Characteristic,
        DatumReference,
        FeatureControlFrame,
        FeatureType,
        FrameModifier,
        MaterialCondition,
    )

    def evaluate(parameters):
        x, y = parameters["x"], parameters["y"]
        return StudyEvaluation(
            objectives={"f": x, "g": y},
            scorecard=Scorecard(
                entries=(
                    ScorecardEntry.from_safety_factor(
                        "feasible", computed=2.0 if x + y >= 4.0 else 0.5, required=2.0
                    ),
                )
            ),
        )

    study = Study(
        name="analytic",
        parameters=(
            Parameter(name="x", low=0.0, high=4.0, unit="mm", steps=3),
            Parameter(name="y", low=0.0, high=4.0, unit="mm", steps=3),
        ),
        objectives=(Objective(name="f"), Objective(name="g")),
    )
    return _sections(
        verification=_plan(performed=True),
        review=_dossier(stale=False),
        exploration=run_study(study, evaluate),
        callouts=CalloutSet(
            callouts=(
                SurfaceFinish(
                    scope="shaft_journal", roughness=_q(0.8, "um"), method=ProductionMethod.GROUND
                ),
            )
        ),
        frames=(
            FeatureControlFrame(
                characteristic=Characteristic.POSITION,
                tolerance=_q(0.2, "mm"),
                feature_type=FeatureType.FEATURE_OF_SIZE,
                material_condition=MaterialCondition.MMC,
                modifiers=(FrameModifier.DIAMETER,),
                datums=(DatumReference(letter="A"), DatumReference(letter="B")),
            ),
        ),
        exports=(ExportRecord(artifact="part.dxf", authorization=authorize_export(_card())),),
        assumptions=("linear elastic, small deflection",),
        citations=(
            SourceRecord(
                ref="AA-6061-T6",
                kind="material",
                name="Aluminium 6061-T6",
                sources=("Aluminum Design Manual 2020, Table A.3.4",),
            ),
        ),
    )


def _keys_the_document_can_carry() -> set[str]:
    """Every key `to_document_dict` and `to_json_dict` can put in the document.

    Read out of the source rather than listed here. A list would be a second copy of the
    method, and a key added to the method and not to the copy is exactly the drift that let
    seven branches go unexercised — the test would have gone on passing over a document it no
    longer described.
    """
    import ast
    import inspect
    import textwrap

    keys: set[str] = set()
    for name in ("to_document_dict", "to_json_dict"):
        source = inspect.getsource(getattr(BundleSections, name))
        # `getsource` keeps the method's own indentation, which is not a parseable module.
        # `cleandoc` will not fix it either: it leaves the `def` line flush and the body
        # indented relative to nothing.
        tree = ast.parse(textwrap.dedent(source))
        for node in ast.walk(tree):
            # `"key": value` inside a dict literal, and `body["key"] = value`.
            if isinstance(node, ast.Dict):
                keys.update(
                    key.value
                    for key in node.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                        if isinstance(target.slice.value, str):
                            keys.add(target.slice.value)
    return keys


def test_the_document_can_carry_every_key_it_names_and_a_bare_bundle_carries_none_of_them():
    """Both directions, over keys read out of the method rather than restated.

    The conditional keys are *absent* rather than null when their section is — the bundle's
    rule that "this layer never ran" and "this layer concluded nothing" are different facts —
    and `spec` is the deliberate exception, null rather than absent so a reader can tell "no
    spec" from "a key I forgot to look for".
    """
    can_carry = _keys_the_document_can_carry()
    assert len(can_carry) >= 15, f"the key reader found only {sorted(can_carry)}"

    full = _every_section().to_document_dict()
    unreachable = can_carry - set(full)
    assert not unreachable, (
        f"these keys are in the method and no bundle here produces them: {sorted(unreachable)}. "
        f"A branch of the document nothing builds is a branch nothing renders."
    )

    bare = _sections().to_document_dict()
    always = {
        "disclaimer",
        "assumptions",
        "status",
        "covers",
        "missing",
        "testVerified",
        "sections",
        "scorecard",
        "spec",
    }
    assert set(bare) == always, sorted(set(bare) ^ always)
    # `spec` is present and null; every other optional key is absent, not null.
    assert bare["spec"] is None
    for key in can_carry - always:
        assert key not in bare, f"{key} appears on a bundle that has no such section"


def test_every_document_this_library_can_build_validates_against_its_published_contract():
    """What holds `BundleDocument` to the document it describes but does not build.

    The obvious construction — build the model, dump it with `exclude_unset` — reproduces the
    absent-versus-null rule at the top level and also applies it to every nested model,
    dropping `informational: false`, `reference: null`, `blocking: []` and more out of eight
    nested structures. Pydantic has no per-level control, so the model describes the document
    rather than producing it, and this is what keeps the two from drifting.

    Both halves matter and they are different checks. The **model** accepting the document says
    the Python types are right. The **released schema** accepting it says the artifact a client
    actually fetches is right, with its `$ref`s resolved — and that is the one a consumer runs,
    so it is the one that has to be true.
    """
    from anvilate.bundle import BundleDocument

    documents = {
        "every section at once": _every_section().to_document_dict(),
        "a scorecard and nothing else": _sections().to_document_dict(),
        "a failing card": _sections(scorecard=_card(passing=False)).to_document_dict(),
        "a plan with nothing performed": _sections(
            verification=_plan(performed=False)
        ).to_document_dict(),
        "a review that no longer applies": _sections(
            review=_dossier(stale=True)
        ).to_document_dict(),
    }
    for document in documents.values():
        BundleDocument.model_validate(document)

    jsonschema = pytest.importorskip("jsonschema")
    from referencing import Registry, Resource

    from anvilate.contracts import (
        BUNDLE_SCHEMA_VERSION,
        SCORECARD_SCHEMA_VERSION,
        SPEC_SCHEMA_VERSION,
    )

    released = Path(__file__).resolve().parent.parent / "docs" / "api" / "schemas" / "released"
    bundle_schema = json.loads(
        (released / f"evidence-bundle-{BUNDLE_SCHEMA_VERSION}.json").read_text(encoding="utf-8")
    )
    # The released files, not the live generators: validating against the same call that
    # produced the document would agree with itself. A client resolves the versioned URL, and
    # these files are what that URL serves.
    registry = Registry().with_resources(
        [
            (document["$id"], Resource.from_contents(document))
            for document in (
                bundle_schema,
                json.loads(
                    (released / f"design-spec-{SPEC_SCHEMA_VERSION}.json").read_text(
                        encoding="utf-8"
                    )
                ),
                json.loads(
                    (released / f"scorecard-{SCORECARD_SCHEMA_VERSION}.json").read_text(
                        encoding="utf-8"
                    )
                ),
            )
        ]
    )
    validator = jsonschema.Draft202012Validator(bundle_schema, registry=registry)
    for label, document in documents.items():
        errors = [
            f"{list(error.absolute_path)}: {error.message}"
            for error in validator.iter_errors(document)
        ]
        assert not errors, f"{label} does not validate against the published contract: {errors}"

    # The schema has to be discriminating, or every assertion above passes on a document the
    # schema does not really describe. Not by closing `additionalProperties`: this artifact
    # leaves it open on purpose, the way the scorecard contract does, so a client pinned to
    # 1.0.0 keeps reading a later bundle that gained a section. (The Design Spec schema *is*
    # closed, and the asymmetry is right — it is an input, where a misspelled key must be
    # refused rather than ignored.) So the probes are a required key removed and a required
    # key given the wrong type.
    baseline = documents["a scorecard and nothing else"]
    for label, broken in (
        ("a required key removed", {k: v for k, v in baseline.items() if k != "disclaimer"}),
        ("status as a number", {**baseline, "status": 7}),
        ("status outside the enumeration", {**baseline, "status": "probably fine"}),
        ("sections as a string", {**baseline, "sections": "one"}),
        ("a section missing its own status", {**baseline, "sections": [{"name": "checks"}]}),
    ):
        assert list(validator.iter_errors(broken)), (
            f"the published bundle schema accepts {label}, so validating against it says "
            f"nothing about the document"
        )


# --- the reading side of the predicate, which is the only side that is untrusted ----------


def _wire_predicate_with_sections(*, passing: bool = True) -> dict:
    """A wire predicate carrying every key `to_json_dict` can write, `sections` included."""
    bundle = assemble_evidence_bundle(
        BundleSections(scorecard=_card(passing=passing)),
        subjects=(),
        artifacts={"scorecard.json": b"{}"},
        spec_digest="a" * 64,
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    wire = bundle.predicate.to_json_dict()
    assert "sections" in wire, "the maximal predicate stopped carrying sections"
    return wire


def test_every_key_the_predicate_writes_is_a_key_the_verifier_checks():
    """`to_json_dict`'s keys, held against the checker by corrupting each one in turn.

    A substring gate over the checker's source would pass on a mention in a comment. This
    one replaces the value at each key with something that cannot be right and requires a
    reported problem, which is the claim the gate is actually making. It is written from the
    method's own dict literal, so a key added on the writing side has to be answered here.

    `sections` is what it caught: the one key `to_json_dict` writes conditionally, and the
    only one the checker had never looked at.
    """
    import ast
    import inspect

    from anvilate.attestation import AnvilatePredicate, _predicate_schema_problems

    source = inspect.getsource(AnvilatePredicate.to_json_dict)
    written = {
        key.value
        for node in ast.walk(ast.parse(source.lstrip()))
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    written |= {
        node.slice.value
        for node in ast.walk(ast.parse(source.lstrip()))
        if isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    }
    assert len(written) >= 7, f"only {sorted(written)} were found in to_json_dict"

    honest = _wire_predicate_with_sections()
    assert _predicate_schema_problems(honest) == [], "the honest predicate is not clean"
    for key in sorted(written):
        corrupted = {**honest, key: "not what belongs here"}
        assert _predicate_schema_problems(corrupted), f"{key!r} can carry anything at all"


def test_the_headline_verdict_is_checked_against_the_document_it_summarises():
    """The one claim on the outside of a signed document, and nothing read it.

    `AnvilatePredicate.status` computes the headline — the sections roll-up when there is
    one, the scorecard's own verdict otherwise — so the producing side cannot write anything
    else. The reading side never compared them, so a predicate saying `"status": "pass"` over
    a failing scorecard verified with **no problem reported**. That is the same defect as a
    predicate of `{"anything": "at all"}` verifying PASS, moved from the body to the headline.
    """
    from anvilate.attestation import _predicate_schema_problems

    honest = _wire_predicate_with_sections(passing=False)
    assert _predicate_schema_problems(honest) == []

    lying = {**honest, "status": "pass"}
    assert honest["status"] != "pass", "the fixture stopped being able to tell these apart"
    assert any(
        "predicate status is 'pass' while the sections roll-up says" in problem
        for problem in _predicate_schema_problems(lying)
    ), _predicate_schema_problems(lying)

    # And with no sections, the scorecard it carries is what the headline has to match.
    sectionless = {key: value for key, value in honest.items() if key != "sections"}
    assert _predicate_schema_problems(sectionless) == []
    assert any(
        "while the scorecard it carries says" in problem
        for problem in _predicate_schema_problems({**sectionless, "status": "pass"})
    )


def test_a_sections_block_can_no_longer_carry_anything_at_all():
    from anvilate.attestation import _predicate_schema_problems

    honest = _wire_predicate_with_sections()
    assert any(
        "sections is a JSON list" in problem
        for problem in _predicate_schema_problems({**honest, "sections": [1, 2]})
    )
    assert any(
        "sections carries status 'excellent'" in problem
        for problem in _predicate_schema_problems({**honest, "sections": {"status": "excellent"}})
    )


def test_a_source_record_renders_every_field_it_carries():
    """A record is a provenance claim, and a rendering that drops part of one makes a
    different claim than the record does.

    Exists because the exported bundle prints these and nothing rendered one before it did:
    the sources block came out as `ref='AA-6061-T6' kind='material' name=...`, pydantic's
    field dump. Held to the property the rendering sweep uses — move one field and the line
    has to move with it — over the model's own field list, so a fifth field cannot land
    unrendered.
    """
    from anvilate.evidence import SourceRecord

    record = SourceRecord(
        ref="AA-6061-T6",
        kind="material",
        name="Aluminium 6061-T6",
        sources=("Aluminum Design Manual 2020, Table A.3.4", "ASTM B209-14"),
    )
    line = str(record)
    assert line == (
        "AA-6061-T6 (material) Aluminium 6061-T6 — "
        "Aluminum Design Manual 2020, Table A.3.4; ASTM B209-14"
    ), line

    moved = {
        "ref": "AA-7075-T6",
        "kind": "component",
        "name": "Aluminium 7075-T6",
        "sources": ("ASTM B209-14",),
    }
    assert set(moved) == set(SourceRecord.model_fields), (
        "SourceRecord's fields and the ones moved here have diverged: "
        f"unmoved {sorted(set(SourceRecord.model_fields) - set(moved))}"
    )
    for field, value in moved.items():
        assert str(record.model_copy(update={field: value})) != line, (
            f"moving {field} left the rendering identical"
        )

    # An empty source list says so rather than collapsing to nothing, on the rule the blocks
    # around it follow: a record whose sources nobody recorded and one with sources must not
    # read the same.
    assert "none recorded" in str(record.model_copy(update={"sources": ()}))


def test_the_exported_bundle_carries_the_sources_its_numbers_were_read_from():
    """The signed predicate has carried them since that layer shipped; the document did not.

    `artifact-export`'s scenario is a reviewer who receives **only the bundle** and re-runs
    the analysis, and a screening result whose sources are somewhere else is not one they can
    act on. Same field, same records, two consumers, and only one of them had it.

    Both renderings, because they are two surfaces over one definition — the text a person
    reads and the JSON a tool does — and the absent case, because a bundle that collected no
    sources and one whose sources are all recorded are different facts.
    """
    from anvilate.evidence import SourceRecord

    record = SourceRecord(
        ref="AA-6061-T6",
        kind="material",
        name="Aluminium 6061-T6",
        sources=("Aluminum Design Manual 2020, Table A.3.4",),
    )
    carried = _sections(citations=(record,))
    bare = _sections()

    document = carried.render_document()
    assert "sources:" in document
    assert str(record) in document, document
    assert carried.to_document_dict()["citations"] == [record.model_dump(mode="json")]

    # Absent from the JSON, and stated in the text: the two ways this document says "no".
    assert "citations" not in bare.to_document_dict()
    assert "none recorded" in bare.render_document()

    # The roll-up is untouched. Its canonical form is hashed into attestations somebody has
    # already signed, and moving it would move every one of their digests.
    assert carried.render() == bare.render()


def test_the_exported_bundle_carries_the_callout_layers_checks_not_just_its_verdict():
    """The argument `_check_lines` makes, one card along, and the fix stopped one card short.

    `render_document` exists because the roll-up named a layer and withheld its checks —
    `[NOT_EVALUATED] callouts` with nothing under it. That fix carried the *scorecard's*
    checks into the document and left the callout card, which the JSON has published as
    `calloutScorecard` since the contract was written. So a reviewer holding only the text
    read that the callout layer could not be evaluated and not that it was because no base
    material had been supplied to resolve the condition against.

    The consequence is measurable in a way a missing block usually is not: `base_material`
    and `known_materials` are carried on the bundle, feed `callout_scorecard`, change the
    card it returns — and could not change the document at all.
    """
    from anvilate.callouts import CalloutSet, HeatTreatment

    treatment = HeatTreatment(scope="body", specification="AMS 2759", condition="QT")
    sections = _every_section().model_copy(update={"callouts": CalloutSet(callouts=(treatment,))})
    document = sections.render_document()
    card = sections.callout_card()
    assert card is not None and card.entries

    assert "callout checks:" in document
    for entry in card.entries:
        assert entry.name in document, entry.name
        assert entry.detail in document, entry.detail

    # The inputs the card is computed from now reach the document, which is the half a
    # missing block hides: they were carried, they changed the card, and nothing rendered it.
    resolved = sections.model_copy(
        update={"base_material": "ASTM-A36", "known_materials": ("ASTM-A36",)}
    )
    assert resolved.callout_card() != card
    assert resolved.render_document() != document

    # Absent when there is no callout layer, and that is not the `spec` rule: callouts are a
    # layer, so an absent one is already named in the roll-up's own `not covered` list.
    without = sections.model_copy(update={"callouts": None})
    assert "callout checks:" not in without.render_document()
    assert "callouts" in without.render_document(), "the roll-up should still name the gap"

    # The roll-up itself is untouched: its canonical form is hashed into signed attestations.
    assert (
        sections.render()
        == _every_section()
        .model_copy(update={"callouts": CalloutSet(callouts=(treatment,))})
        .render()
    )


def _spec_declaring_a_combination_basis():
    import yaml

    from anvilate.spec import load_spec_yaml

    source = (
        Path(__file__).resolve().parent.parent / "examples" / "nema23_bracket.spec.yaml"
    ).read_text(encoding="utf-8")
    document = yaml.safe_load(source)
    document["combination_basis"] = "asce7_lrfd"
    document["load_cases"] = [
        {
            "name": "dead",
            "kind": "static",
            "applied_to": "top",
            "force": {"magnitude": 5.0, "unit": "kN"},
            "nature": "D",
        },
        {
            "name": "live",
            "kind": "static",
            "applied_to": "top",
            "force": {"magnitude": 3.0, "unit": "kN"},
            "nature": "L",
        },
    ]
    return load_spec_yaml(yaml.safe_dump(document))


def test_a_bundle_does_not_say_a_layer_is_uncovered_while_printing_its_result():
    """One document, two statements about the same layer, and the roll-up had the wrong one.

    `DesignSpec.combination_evidence` says in its own docstring that it exists so "the
    evidence a bundle carries cannot forget the cases the factoring could not see", and no
    bundle carried it. So a spec declaring `asce7_lrfd` exported a document whose first line
    read `not covered: ... load combinations ...` while the card below it printed
    `[PASS] load combination: LRFD 2 [Lr] governs` with the factored demand worked out. The
    roll-up is the line a reviewer reads first, and it is the one that was wrong.
    """
    from anvilate.bundle import combinations_for

    spec = _spec_declaring_a_combination_basis()
    evidence = combinations_for(spec)
    assert evidence is not None, "the fixture no longer declares a resolvable basis"

    def not_covered(sections) -> str:
        """The roll-up's own `not covered:` list, and nothing after the semicolon.

        Splitting the whole rendering on `not covered` sweeps in the section lines below it,
        so a layer that IS covered shows up in its own not-covered list. The first version
        of this test did exactly that and failed on a correct document.
        """
        head = sections.render().splitlines()[0]
        return head.split("not covered:", 1)[1].split(";", 1)[0] if "not covered:" in head else ""

    carried = _sections(spec=spec, combinations=evidence)
    rolled = carried.render()
    assert "load combinations" not in not_covered(carried), rolled.splitlines()[0]
    assert evidence.detail() in rolled

    # And the layer is still named as missing when the spec declares no basis, which is the
    # half that stops "always covered" passing this.
    assert "load combinations" in not_covered(_sections())


def test_a_basis_that_cannot_resolve_carries_no_evidence_rather_than_raising():
    """A seismic set with no S_DS is a fact the card already states.

    `screening._combination_entry` puts it there as a NOT_EVALUATED check naming the reason,
    and a bundle that would not render over it would withhold that finding from its reader.
    The same rule `evidence.provenance_for` follows one field along.
    """
    import pytest as _pytest

    from anvilate.bundle import combinations_for

    spec = _spec_declaring_a_combination_basis()
    seismic = spec.model_copy(update={"combination_basis": "asce7_lrfd_seismic"})
    with _pytest.raises(ValueError):
        seismic.combination_evidence()
    assert combinations_for(seismic) is None
