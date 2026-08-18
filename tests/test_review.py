"""Responsible-charge review: the dossier an engineer needs before deciding to seal."""

from __future__ import annotations

from datetime import date

import pytest

from anvilate.review import (
    PROHIBITED_ASSURANCE_LANGUAGE,
    DecisionOrigin,
    ReviewPriority,
    ReviewRecord,
    artifact_digest,
    build_dossier,
    review_priority,
)
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

TOOLCHAIN = "anvilate 0.1.0"


def _card(**over) -> Scorecard:
    entries = over.get(
        "entries",
        (
            ScorecardEntry.from_safety_factor("bending", computed=3.0, required=1.5),
            ScorecardEntry.from_safety_factor("shear", computed=1.55, required=1.5),
            ScorecardEntry(
                name="fatigue",
                status=CheckStatus.NOT_EVALUATED,
                detail="no S-N curve supplied",
            ),
            ScorecardEntry.from_safety_factor("deflection", computed=0.8, required=1.0),
        ),
    )
    return Scorecard(entries=entries)


def _record(card: Scorecard, **over) -> ReviewRecord:
    kwargs = {
        "reviewer": "A. Engineer, P.E.",
        "reviewed_on": date(2026, 8, 17),
        "covers_digest": artifact_digest(card, toolchain=TOOLCHAIN),
        "scope": "structural checks on the bracket",
    }
    kwargs.update(over)
    return ReviewRecord(**kwargs)


def test_the_unevaluated_check_outranks_the_failing_one():
    """The order is 'most likely to change the decision', not 'worst'.

    A FAIL is already visible and already blocking. A NOT_EVALUATED is the check that
    silently is not there, and it is the one a reviewer can miss entirely — so it sorts
    first. The ordering is fixed and documented so two runs agree and a diff between
    dossiers means something.
    """
    dossier = build_dossier(_card(), toolchain=TOOLCHAIN)
    names = [item.entry.name for item in dossier.items]
    assert names[0] == "fatigue"
    assert names[1] == "deflection"
    priorities = [item.priority for item in dossier.items]
    assert priorities == sorted(priorities)
    assert dossier.items[0].priority is ReviewPriority.NOT_EVALUATED
    assert dossier.items[1].priority is ReviewPriority.FAILING

    # Ties keep the scorecard's own order, so the ordering is total and reproducible.
    twice = build_dossier(_card(), toolchain=TOOLCHAIN)
    assert [i.entry.name for i in twice.items] == names


def test_a_check_with_no_recorded_origin_is_unattributed_not_routine():
    """Defaulting an unrecorded origin to something reassuring would make the whole
    attribution feature worse than useless, by making its absence invisible."""
    dossier = build_dossier(_card(), toolchain=TOOLCHAIN)
    by_name = {i.entry.name: i for i in dossier.items}
    assert by_name["bending"].origin is DecisionOrigin.UNATTRIBUTED
    assert by_name["bending"].priority is ReviewPriority.UNATTRIBUTED_ASSUMPTION

    # Attribute it and it drops to routine; attribute it to a model and it does not.
    attributed = build_dossier(
        _card(),
        toolchain=TOOLCHAIN,
        origins={"bending": DecisionOrigin.DETERMINISTIC},
    )
    assert {i.entry.name: i.priority for i in attributed.items}["bending"] is (
        ReviewPriority.ROUTINE
    )
    modelled = build_dossier(
        _card(),
        toolchain=TOOLCHAIN,
        origins={"bending": DecisionOrigin.MODEL},
        origin_details={"bending": "claude-opus-5"},
    )
    assert {i.entry.name: i.priority for i in modelled.items}["bending"] is (
        ReviewPriority.MODEL_ASSUMPTION
    )
    assert modelled.model_involvement == ("claude-opus-5",)


def test_a_passing_check_close_to_its_requirement_is_surfaced():
    """The band where an assumption the reviewer disagrees with flips the answer."""
    origins = dict.fromkeys(("bending", "shear"), DecisionOrigin.DETERMINISTIC)
    dossier = build_dossier(_card(), toolchain=TOOLCHAIN, origins=origins)
    by_name = {i.entry.name: i for i in dossier.items}
    assert by_name["shear"].priority is ReviewPriority.THIN_MARGIN  # 1.55/1.5 = 1.03
    assert by_name["bending"].priority is ReviewPriority.ROUTINE  # 3.0/1.5 = 2.0
    assert "close to its requirement" in by_name["shear"].headline
    assert {i.entry.name for i in dossier.attention_first} == {"fatigue", "deflection", "shear"}


def test_any_change_to_the_artifact_or_the_toolchain_invalidates_the_review():
    """A review that survives the thing it reviewed is worse than no review.

    Including the toolchain in the digest is the part that is easy to leave out and
    matters most: the same inputs through a different library version are a different
    piece of work.
    """
    card = _card()
    record = _record(card)
    assert record.applies_to(card, toolchain=TOOLCHAIN)

    # A changed input moves the digest.
    changed = _card(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=2.9, required=1.5),
            *card.entries[1:],
        )
    )
    assert not record.applies_to(changed, toolchain=TOOLCHAIN)
    # So does a changed toolchain, with the artifact untouched.
    assert not record.applies_to(card, toolchain="anvilate 0.2.0")

    # A stale record is carried through and FLAGGED, not dropped: "there was a review and
    # it no longer covers this" is different information from "there was never a review".
    stale = build_dossier(changed, toolchain=TOOLCHAIN, record=record)
    assert stale.stale_record is True
    assert stale.record is record
    assert "no longer applies" in stale.summary()
    fresh = build_dossier(card, toolchain=TOOLCHAIN, record=record)
    assert fresh.stale_record is False
    assert "A. Engineer, P.E." in fresh.summary()
    unreviewed = build_dossier(card, toolchain=TOOLCHAIN)
    assert "not yet reviewed" in unreviewed.summary()

    with pytest.raises(ValueError, match="toolchain must identify"):
        artifact_digest(card, toolchain="  ")
    with pytest.raises(ValueError, match="may not be blank"):
        _record(card, reviewer="")


def test_an_accepted_exception_never_turns_a_failing_check_into_a_pass():
    """A tool that let a review change a verdict would be laundering the engineer's
    judgement into an appearance of analysis."""
    card = _card()
    record = _record(card, accepted_exceptions=("deflection",))
    dossier = build_dossier(card, toolchain=TOOLCHAIN, record=record)
    by_name = {i.entry.name: i for i in dossier.items}
    assert by_name["deflection"].entry.status is CheckStatus.FAIL
    assert by_name["deflection"].priority is ReviewPriority.FAILING
    assert dossier.status is CheckStatus.FAIL
    assert "overall fail" in dossier.summary()
    # The exception is recorded, and recorded is all it is.
    assert dossier.record is not None
    assert dossier.record.accepted_exceptions == ("deflection",)


def test_no_rendering_in_this_module_uses_the_language_of_certification():
    """The failure mode here is not a wrong number — it is a sentence someone forwards.

    Every string this module renders ABOUT AN ARTIFACT is swept for the vocabulary a
    screening tool must never use about its own output: the summary line and every item
    headline, in the reviewed, unreviewed and stale states, with an accepted exception in
    play.

    Docstrings are deliberately out of scope, and the distinction is real rather than a
    dodge: a rendering is a statement about the user's design, and it is what gets
    forwarded, pasted into an email and read as assurance. A docstring is a statement
    about the code, and this module's own says it "stays out of the vocabulary of
    certification" — a sentence the gate would flag for containing the word it exists to
    prohibit. Gating prose about the policy is how a language gate becomes unusable and
    then gets deleted.
    """
    card = _card()
    record = _record(card, accepted_exceptions=("deflection",), notes="accepted per RFI 12")
    renderings: list[str] = []
    for dossier in (
        build_dossier(card, toolchain=TOOLCHAIN),
        build_dossier(card, toolchain=TOOLCHAIN, record=record),
        build_dossier(
            card,
            toolchain=TOOLCHAIN,
            origins={"bending": DecisionOrigin.MODEL},
            origin_details={"bending": "claude-opus-5"},
            record=_record(_card(entries=card.entries[:2])),  # deliberately stale
        ),
    ):
        renderings.append(dossier.summary())
        renderings.extend(item.headline for item in dossier.items)
    offenders = [
        (phrase, text)
        for text in renderings
        for phrase in PROHIBITED_ASSURANCE_LANGUAGE
        if phrase in text.lower()
    ]
    assert not offenders, (
        "these renderings use the language of certification, which a screening tool must "
        f"never use about its own output: {offenders[:3]}"
    )
    # And the gate can actually fail — a sentence that does use it is caught.
    assert any(
        p in "this design is certified and fit for service".lower()
        for p in PROHIBITED_ASSURANCE_LANGUAGE
    )


def test_review_priority_is_decided_by_status_then_attribution_then_margin():
    """The three-level rule, asserted directly rather than only through a dossier."""
    unevaluated = ScorecardEntry(name="x", status=CheckStatus.NOT_EVALUATED, detail="no data")
    failing = ScorecardEntry.from_safety_factor("x", computed=0.5, required=1.0)
    thin = ScorecardEntry.from_safety_factor("x", computed=1.05, required=1.0)
    ample = ScorecardEntry.from_safety_factor("x", computed=4.0, required=1.0)

    # Status wins over attribution: an unevaluated check is first however well sourced.
    assert review_priority(unevaluated, origin=DecisionOrigin.USER) is (
        ReviewPriority.NOT_EVALUATED
    )
    assert review_priority(failing, origin=DecisionOrigin.USER) is ReviewPriority.FAILING
    # Attribution wins over margin: an ample margin nobody sourced still surfaces.
    assert review_priority(ample, origin=DecisionOrigin.UNATTRIBUTED) is (
        ReviewPriority.UNATTRIBUTED_ASSUMPTION
    )
    assert review_priority(ample, origin=DecisionOrigin.MODEL) is (ReviewPriority.MODEL_ASSUMPTION)
    # Margin decides among well-sourced passes.
    assert review_priority(thin, origin=DecisionOrigin.USER) is ReviewPriority.THIN_MARGIN
    assert review_priority(ample, origin=DecisionOrigin.USER) is ReviewPriority.ROUTINE
