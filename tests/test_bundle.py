"""The assembled evidence bundle: the cross-layer roll-up and what it refuses to imply."""

from __future__ import annotations

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
