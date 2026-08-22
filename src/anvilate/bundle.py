"""The evidence bundle assembled: every layer in one document, with one honest roll-up.

Anvilate grew its cross-cutting layers one at a time, and each ships its own verdict: the
scorecard rolls up the checks, the verification plan rolls up the physical tests, the
reviewer dossier rolls up what a licensed engineer still has to look at. Separately they
are all correct. Together, nobody had written down what the *part* is — and three of them
carried an open task that said, in three different files, "evidence-bundle serialization".

This is that. :class:`BundleSections` collects what each layer produced,
:attr:`BundleSections.status` rolls the lot up under one precedence, and
:func:`assemble_evidence_bundle` hands the result to the attestation layer as the body of
a signed, content-addressed claim.

The roll-up is where the judgement is, and it has three rules:

**A layer that is absent is not a layer that passed.** A bundle with a green scorecard and
no verification plan has not verified anything, so the roll-up cannot say PASS on the
strength of the checks alone. :meth:`BundleSections.missing` names what is not there and
:meth:`BundleSections.covers` names what is, so "we did not test it" and "we tested it and
it held" are never the same sentence. A bundle that carries only a scorecard is a perfectly
legitimate screening bundle — it simply says so.

**A plan is not evidence, and the bundle inherits that.** A verification plan with nothing
performed is ``NOT_EVALUATED`` in its own layer, and it pulls the bundle down with it even
when every check passed. The physics passing is the reason to test, not a substitute.

**A review that no longer applies is not a review.** The dossier already detects that the
artifact moved under a review record; here it degrades the bundle rather than sitting as a
flag somebody has to notice. That state looks identical to "reviewed" from the outside,
which is exactly why it has to be loud from the inside.

Precedence follows :class:`~anvilate.scorecard.Scorecard` exactly — FAIL, then
NOT_EVALUATED, then OVER_MARGIN, then PASS — because a second roll-up that ordered them
differently would let one layer's blocking failure hide behind another layer's gap.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, model_validator

from .attestation import (
    AIDisclosure,
    AnvilatePredicate,
    EnvironmentBOM,
    EvidenceBundle,
    Subject,
    canonical_json,
)
from .callouts import CalloutSet, callout_scorecard
from .evidence import SourceRecord
from .explore import StudyResult
from .gdt import FeatureControlFrame
from .review import ReviewerDossier
from .scorecard import CheckStatus, Scorecard
from .units import Quantity
from .verification import VerificationPlan

__all__ = [
    "SectionStatus",
    "BundleSections",
    "assemble_evidence_bundle",
]


# The order the roll-up resolves in, lowest first. Identical to Scorecard's precedence by
# construction rather than by coincidence: a second ordering is a second place for a
# blocking failure to hide.
_PRECEDENCE: tuple[CheckStatus, ...] = (
    CheckStatus.PASS,
    CheckStatus.OVER_MARGIN,
    CheckStatus.NOT_EVALUATED,
    CheckStatus.FAIL,
)


def _worst(statuses: Iterable[CheckStatus]) -> CheckStatus:
    """The most blocking of ``statuses``.

    The empty case cannot arise — ``BundleSections`` always carries a non-informational
    ``checks`` section — and the default is PASS rather than NOT_EVALUATED so that the
    identity holds: the worst of nothing does not make a bundle worse. The invariant is
    asserted rather than assumed, because a future section that is informational by
    default would otherwise silently empty this.
    """
    candidates = list(statuses)
    if not candidates:
        raise ValueError(
            "a bundle roll-up needs at least one section that is a verdict about the part; "
            "the checks section always is, so an empty set here means a caller built "
            "BundleSections in a way its validator was supposed to refuse"
        )
    return max(candidates, key=_PRECEDENCE.index)


class SectionStatus(BaseModel):
    """One layer's contribution: what it is, what it concluded, and whether that is a verdict.

    ``informational`` marks a layer whose conclusion is *about something other than this
    part*. A design-space sweep says what the space contains; a set of feature control
    frames says the callouts parse. Neither is a statement that the part is or is not
    sound, so neither enters the roll-up — and letting them would mean an exhaustive sweep
    with nothing feasible in it condemning a part that passes every check on its own
    drawing. They are still carried, still rendered, and still counted in
    :meth:`BundleSections.covers`.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    status: CheckStatus
    detail: str
    informational: bool = False

    def __str__(self) -> str:
        mark = " (informational)" if self.informational else ""
        return f"[{self.status.value.upper()}] {self.name}{mark}: {self.detail}"


class BundleSections(BaseModel):
    """What each layer produced for one part, and the one status over all of them.

    ``scorecard`` is the only required section — a bundle with no checks in it is not a
    bundle of anything. The rest are optional because a screening run legitimately stops
    before them, and the difference between "this layer concluded" and "this layer was
    never run" is reported rather than smoothed over.
    """

    model_config = ConfigDict(frozen=True)

    scorecard: Scorecard
    citations: tuple[SourceRecord, ...] = ()
    verification: VerificationPlan | None = None
    review: ReviewerDossier | None = None
    exploration: StudyResult | None = None
    callouts: CalloutSet | None = None
    frames: tuple[FeatureControlFrame, ...] = ()
    # The strength the callout layer derives its surface factor against, when a callout
    # set is present. Without it the finish callouts report NOT_EVALUATED, which is the
    # honest outcome rather than a reason to omit the section.
    ultimate_strength: Quantity | None = None
    base_material: str | None = None
    known_materials: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _the_scorecard_is_the_floor(self) -> BundleSections:
        if not self.scorecard.entries:
            raise ValueError(
                "an evidence bundle needs at least one check; a bundle over an empty "
                "scorecard has nothing to be evidence of"
            )
        if self.review is not None and self.review.digest.strip() == "":
            raise ValueError("a reviewer dossier in a bundle must carry the digest it covers")
        return self

    def callout_card(self) -> Scorecard | None:
        """The callout layer's own scorecard, or ``None`` when no callouts are declared."""
        if self.callouts is None:
            return None
        return callout_scorecard(
            self.callouts,
            ultimate_strength=self.ultimate_strength,
            base_material=self.base_material,
            known_materials=self.known_materials,
        )

    def sections(self) -> tuple[SectionStatus, ...]:
        """Every present layer, with what it concluded — the roll-up's own inputs."""
        found: list[SectionStatus] = [
            SectionStatus(
                name="checks",
                status=self.scorecard.status,
                detail=(
                    f"{len(self.scorecard.entries)} run, "
                    f"{len(self.scorecard.failures())} failing, "
                    f"{len(self.scorecard.not_evaluated())} not evaluated"
                ),
            )
        ]
        if self.verification is not None:
            plan = self.verification
            found.append(
                SectionStatus(
                    name="verification",
                    status=plan.status,
                    detail=(
                        f"{len(plan.verified)} of {len(plan.items)} planned tests performed, "
                        f"{len(plan.analysis_only)} verified by analysis, "
                        f"{len(plan.unresolved)} unresolved"
                    ),
                )
            )
        if self.review is not None:
            found.append(
                SectionStatus(
                    name="review",
                    # A stale record is worse than no record, because it reads as a review
                    # from the outside. The dossier's own status is the scorecard's, so the
                    # staleness has to be applied here or it is lost in the roll-up.
                    status=(
                        CheckStatus.NOT_EVALUATED
                        if self.review.stale_record
                        else self.review.status
                    ),
                    detail=self.review.summary(),
                )
            )
        if self.exploration is not None:
            study = self.exploration
            found.append(
                SectionStatus(
                    name="exploration",
                    informational=True,
                    status=(CheckStatus.PASS if study.feasible else CheckStatus.NOT_EVALUATED),
                    detail=(
                        f"{len(study.points)} candidates evaluated, "
                        f"{len(study.feasible)} feasible, "
                        f"{len(study.front)} on the Pareto front"
                    ),
                )
            )
        card = self.callout_card()
        if card is not None:
            found.append(
                SectionStatus(
                    name="callouts",
                    status=card.status,
                    detail=f"{len(card.entries)} typed callouts consumed",
                )
            )
        if self.frames:
            found.append(
                SectionStatus(
                    name="geometric tolerances",
                    informational=True,
                    status=CheckStatus.PASS,
                    detail=(
                        f"{len(self.frames)} feature control frames, each legal at construction"
                    ),
                )
            )
        return tuple(found)

    def covers(self) -> tuple[str, ...]:
        """The layers this bundle actually carries — the scope of what it claims."""
        return tuple(section.name for section in self.sections())

    def missing(self) -> tuple[str, ...]:
        """The layers this bundle does not carry, named rather than left to inference."""
        present = set(self.covers())
        return tuple(
            name
            for name in (
                "verification",
                "review",
                "exploration",
                "callouts",
                "geometric tolerances",
            )
            if name not in present
        )

    @property
    def status(self) -> CheckStatus:
        """The one status over every present layer, at the scorecard's own precedence.

        Never better than the worst section. A green scorecard under an unperformed
        verification plan is ``NOT_EVALUATED``, because the plan is the layer that would
        have said otherwise and it has not said it yet.
        """
        return _worst(section.status for section in self.sections() if not section.informational)

    @property
    def verified(self) -> bool:
        """Whether the bundle is backed by *performed* tests, not merely by analysis.

        Strictly narrower than :attr:`status`: it is True only when a verification plan is
        present and every item in it has a recorded, passing outcome. A bundle with no plan
        is not verified, and neither is one whose plan is still intent.
        """
        # `VerificationPlan.status` is already NOT_EVALUATED for an empty plan, so an
        # `and self.verification.items` here was dead weight that read like a real guard.
        return self.verification is not None and self.verification.status is CheckStatus.PASS

    def summary(self) -> str:
        """One line naming the roll-up, what is covered, and what is not."""
        covered = self.covers()
        missing = ", ".join(self.missing()) or "nothing"
        plural = "layer" if len(covered) == 1 else "layers"
        return (
            f"bundle {self.status.value.upper()} over {len(covered)} {plural} "
            f"({', '.join(covered)}); not covered: {missing}; "
            f"{'test-verified' if self.verified else 'not test-verified'}"
        )

    def render(self) -> str:
        """The bundle as a readable block: the roll-up, then every section under it."""
        return "\n".join([self.summary(), *(f"  {section}" for section in self.sections())])

    def to_json_dict(self) -> dict[str, object]:
        """The sections as JSON-safe primitives, for the attestation predicate."""
        card = self.callout_card()
        body: dict[str, object] = {
            "status": self.status.value,
            "covers": list(self.covers()),
            "missing": list(self.missing()),
            "testVerified": self.verified,
            "sections": [section.model_dump(mode="json") for section in self.sections()],
        }
        if self.verification is not None:
            body["verification"] = self.verification.model_dump(mode="json")
        if self.review is not None:
            body["review"] = self.review.model_dump(mode="json")
        if self.exploration is not None:
            body["exploration"] = self.exploration.model_dump(mode="json")
        if self.callouts is not None:
            body["callouts"] = self.callouts.model_dump(mode="json")
            body["calloutScorecard"] = None if card is None else card.model_dump(mode="json")
        if self.frames:
            body["geometricTolerances"] = [frame.render() for frame in self.frames]
        return body


def assemble_evidence_bundle(
    sections: BundleSections,
    *,
    subjects: Iterable[Subject],
    spec_digest: str,
    bom: EnvironmentBOM,
    ai_disclosure: AIDisclosure,
    artifacts: Mapping[str, bytes] | None = None,
) -> EvidenceBundle:
    """Assemble the layers into an attestable, content-addressed evidence bundle.

    ``subjects`` are the produced artifacts by digest; ``artifacts`` is the convenience
    form, a mapping of name to content from which the subjects are derived. Supply one or
    the other — supplying both is an error rather than a merge, because two sources for
    the same list is two chances for them to disagree.

    The predicate carries the scorecard and citations as before, plus the assembled
    sections, so a verifier reading the attestation sees the same roll-up the reviewer saw
    rather than having to recompute it from the parts.
    """
    named = tuple(subjects)
    if artifacts is not None:
        if named:
            raise ValueError(
                "supply either `subjects` or `artifacts`, not both; two sources for one "
                "subject list is two chances for them to disagree"
            )
        named = tuple(Subject.over(name, data) for name, data in sorted(artifacts.items()))
    predicate = AnvilatePredicate(
        spec_digest=spec_digest,
        scorecard=sections.scorecard,
        citations=sections.citations,
        bom=bom,
        ai_disclosure=ai_disclosure,
        sections_json=canonical_json(sections.to_json_dict()),
    )
    return EvidenceBundle(subjects=named, predicate=predicate)
