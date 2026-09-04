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

**An artifact that left unvalidated is disclosed here, not only in its own header.** The
export gate watermarks the file it writes; the requirement watermarks the bundle too, and
the fact the bundle adds is that an artifact *exists in the world* carrying that mark. A
bundle whose checks all pass and whose drawing was exported under an override is
``NOT_EVALUATED``, because something left the tool with no verdict behind it.

**The screening label is not a field a caller can leave out.** ``artifact-export`` requires
every evidence bundle to carry the screening-analysis disclaimer and the list of modelling
assumptions. The disclaimer is therefore a constant on the rendered bundle rather than a
field: there is no argument that omits it, which is what "non-dismissable" has to mean in a
library. The assumptions *are* the caller's, and an empty list renders as "none declared"
rather than as no heading at all — a bundle that declared no assumptions and one whose
author forgot the section must not look identical.

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

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from ._models import Named, RevalidatedModel
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
from .export.gate import ExportRecord
from .gdt import FeatureControlFrame
from .loads import CombinationEvidence
from .report.document import SCREENING_DISCLAIMER
from .review import ReviewerDossier
from .scorecard import CheckStatus, Scorecard
from .spec import DesignSpec, dump_spec_yaml
from .standards.effectivity import DesignBasis, design_basis_scorecard
from .units import Quantity
from .verification import VerificationPlan

__all__ = [
    "SectionStatus",
    "BundleDocument",
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


class SectionStatus(RevalidatedModel):
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

    name: Named
    status: CheckStatus
    detail: str
    informational: bool = False

    def __str__(self) -> str:
        mark = " (informational)" if self.informational else ""
        return f"[{self.status.value.upper()}] {self.name}{mark}: {self.detail}"


class BundleDocument(BaseModel):
    """The exported evidence bundle, as the document a consumer receives.

    This exists so the bundle has a **published contract**. It is what
    :meth:`BundleSections.to_document_dict` returns and what the ``export_artifact`` MCP tool
    serves, and that tool used to describe its entire output as ``{"type": "object"}`` — a
    published ``outputSchema`` that said nothing about the one thing it publishes. The schema
    is generated from this model by :mod:`anvilate.contracts`, the same way the Design Spec
    and scorecard contracts are, because a hand-written copy of a live document is wrong the
    first time somebody adds a field.

    **A wire model, so the field names are the wire's.** They are camelCase because the
    document has been camelCase since before it had a contract, and renaming a published key
    to satisfy a naming convention would break every reader to no purpose. The aliases carry
    that; the Python attributes stay snake_case.

    **Absent and null mean different things here.** A section that never ran is *absent*; the
    bundle's whole doctrine is that "this layer never ran" and "this layer concluded nothing"
    are different facts, and collapsing them to null would assert the second. ``spec`` and
    ``calloutScorecard`` are the two exceptions, present-and-null, because for those a null
    *is* the modelled answer — ``spec: null`` lets a reader tell "no spec" from "a key I forgot
    to look for".

    **This model describes the document; it does not build it.** Dumping it with
    ``exclude_unset=True`` would reproduce the absent-versus-null rule at this level and also
    apply it to every nested model, dropping ``informational: false``, ``reference: null``,
    ``blocking: []`` and more from eight nested structures. Pydantic has no per-level control,
    so the alternative was to change bytes this document has always emitted — the wrong trade
    for a schema's provenance. What holds the two together is
    ``test_every_document_this_library_can_build_validates_against_its_published_contract``,
    which validates every document the library builds against this model and against the
    released schema, and the key-set test that holds these fields to the keys
    :meth:`BundleSections.to_document_dict` actually emits.

    What the generated schema is looser about than reality: the six absent-when-missing keys
    are described as optional *and* nullable, because that is what an ``X | None`` field
    generates. Every real document validates; a hand-written schema could say it more exactly
    and would go stale instead.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    disclaimer: str
    assumptions: tuple[str, ...]
    status: CheckStatus
    covers: tuple[str, ...]
    missing: tuple[str, ...]
    test_verified: bool = Field(serialization_alias="testVerified", alias="testVerified")
    sections: tuple[SectionStatus, ...]
    scorecard: Scorecard
    # Null rather than absent, deliberately: see the class docstring.
    spec: DesignSpec | None

    verification: VerificationPlan | None = None
    review: ReviewerDossier | None = None
    exploration: StudyResult | None = None
    callouts: CalloutSet | None = None
    # Null when a callout set is present and derives no card of its own, which is why it is
    # passed explicitly rather than left unset alongside `callouts`.
    callout_scorecard: Scorecard | None = Field(
        default=None, serialization_alias="calloutScorecard", alias="calloutScorecard"
    )
    exports: tuple[ExportRecord, ...] | None = None
    geometric_tolerances: tuple[str, ...] | None = Field(
        default=None, serialization_alias="geometricTolerances", alias="geometricTolerances"
    )


class BundleSections(RevalidatedModel):
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
    # Which load combination the checks were screened against. Optional because a part
    # screened per load case declares no combination basis; present, it is a verdict about
    # this part, so it enters the roll-up rather than riding along as information.
    combinations: CombinationEvidence | None = None
    # The strength the callout layer derives its surface factor against, when a callout
    # set is present. Without it the finish callouts report NOT_EVALUATED, which is the
    # honest outcome rather than a reason to omit the section.
    ultimate_strength: Quantity | None = None
    base_material: str | None = None
    known_materials: tuple[str, ...] = ()
    # The artifacts emitted for this part and the authorization each left under. Empty is
    # not "nothing was exported" — it is "this bundle does not say", which `missing()`
    # reports rather than smoothing over.
    exports: tuple[ExportRecord, ...] = ()
    # The modelling assumptions the screening ran under, in the caller's own words. Empty
    # renders as "none declared" rather than vanishing: see the module docstring.
    assumptions: tuple[str, ...] = ()
    # The editions this project designs to. Optional, and its absence is *named* by
    # `missing()` rather than left out: a bundle whose citations nobody checked against a
    # basis and one whose citations check out are different documents, and without this
    # field a reader could not tell which they were holding — the concept did not appear.
    design_basis: DesignBasis | None = None
    # The document these verdicts were computed from. `artifact-export` asks the bundle to
    # carry "the spec, the scorecard ... sufficient for an independent engineer to reproduce
    # the run", and its scenario is a reviewer holding **only the bundle**. Without this the
    # bundle named what passed and not the load, the thickness or the material it passed on,
    # so the scenario was not merely untested — it was false.
    #
    # Optional, and its absence is *named* by `render_document` rather than left out: a
    # bundle that cannot be re-run and one whose author forgot the section must not read the
    # same. It stays out of the roll-up — `to_json_dict` is hashed into signed attestations,
    # and a spec is not a layer with a verdict — so adding it moves no existing digest.
    spec: DesignSpec | None = None

    @model_validator(mode="after")
    def _an_assumption_says_something(self) -> BundleSections:
        for assumption in self.assumptions:
            if not assumption.strip():
                raise ValueError(
                    "a blank modelling assumption is a line that reads as a declared one; "
                    "state it or leave it out"
                )
        # The same rule, two fields along, where it was missing. `design_basis` and
        # `assumptions` refuse a blank and these did not — a bundle naming its base material
        # as three spaces renders a material line nobody can follow, which is worse than the
        # `None` that means "this bundle does not say".
        if self.base_material is not None and not self.base_material.strip():
            raise ValueError(
                "a blank base material reads as a declared one; name it or leave it None, "
                "which is what 'this bundle does not say' looks like"
            )
        for material in self.known_materials:
            if not material.strip():
                raise ValueError(
                    "a blank entry in known_materials is an identifier nothing can resolve; "
                    "it would be counted as a material this bundle knows"
                )
        return self

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
        # The over-margin count is appended only when there is one, and the asymmetry with
        # the other two is deliberate: a target band is opt-in, so most cards have none, and
        # printing "0 over margin" on every bundle in the library teaches a reader to skip
        # the field. What is NOT acceptable is the roll-up this line used to give — the
        # status said OVER_MARGIN and the only prose under it read "3 run, 0 failing, 0 not
        # evaluated", two zeroes accounting for none of the verdict above them.
        over_margin = len(self.scorecard.over_margin())
        found: list[SectionStatus] = [
            SectionStatus(
                name="checks",
                status=self.scorecard.status,
                detail=(
                    f"{len(self.scorecard.entries)} run, "
                    f"{len(self.scorecard.failures())} failing, "
                    f"{len(self.scorecard.not_evaluated())} not evaluated"
                    + (f", {over_margin} over margin" if over_margin else "")
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
        if self.design_basis is not None:
            entry = design_basis_scorecard(
                "design basis",
                basis=self.design_basis,
                references=[e.reference for e in self.scorecard.entries if e.reference],
            )
            found.append(
                SectionStatus(
                    name="design basis",
                    status=entry.status,
                    detail=entry.detail,
                    # Informational except when it FAILs, and the split is the point.
                    # Most references in this library name no edition, so a
                    # NOT_EVALUATED here is the ordinary case; letting it into the roll-up
                    # would mean nearly every bundle reporting NOT_EVALUATED over checks
                    # that ran and passed, which teaches a reader to ignore the status.
                    # A FAIL is different in kind: the citations contradict each other, so
                    # the bundle reads as though every number came from one book and did
                    # not. That is evidence misrepresenting itself, and a roll-up that
                    # said PASS over it would be doing the same thing one level up.
                    informational=entry.status is not CheckStatus.FAIL,
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
        if self.combinations is not None:
            found.append(
                SectionStatus(
                    name="load combinations",
                    status=self.combinations.status,
                    detail=self.combinations.detail(),
                )
            )
        if self.exports:
            unvalidated = [record for record in self.exports if not record.authorization.validated]
            found.append(
                SectionStatus(
                    name="export",
                    # PASS only when every artifact left validated. An unvalidated artifact
                    # is not a failing check — nothing here failed — it is a file in the
                    # world whose verdict was never established, which is what
                    # NOT_EVALUATED means everywhere else in this library.
                    status=(CheckStatus.NOT_EVALUATED if unvalidated else CheckStatus.PASS),
                    detail=(
                        f"{len(self.exports)} artifact(s) emitted, "
                        f"{len(unvalidated)} unvalidated"
                        + (
                            ""
                            if not unvalidated
                            else ": " + "; ".join(str(record) for record in unvalidated)
                        )
                    ),
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
                "design basis",
                "verification",
                "review",
                "exploration",
                "callouts",
                "load combinations",
                "export",
                "geometric tolerances",
            )
            if name not in present
        )

    # A verdict a serialised document does not carry is one its reader has to
    # rebuild. See `Scorecard.status` for what that costs.
    @computed_field  # type: ignore[prop-decorator]
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

    def assumptions_block(self) -> tuple[str, ...]:
        """The assumptions as rendered lines — never empty, so the heading never vanishes."""
        if not self.assumptions:
            return ("assumptions: none declared",)
        return ("assumptions:", *(f"  - {item}" for item in self.assumptions))

    def render(self) -> str:
        """The bundle as a readable block: the roll-up, every section, the screening label.

        The disclaimer is appended here rather than passed in, so there is no call that
        renders a bundle without it.
        """
        return "\n".join([self._render_rollup(), SCREENING_DISCLAIMER])

    def _render_rollup(self) -> str:
        """The roll-up block without the trailing disclaimer, shared by both renderings.

        Factored out rather than duplicated: the disclaimer has to be last in each rendering
        and the block above it is the same block, so a section added here reaches the
        exported bundle too instead of only the summary somebody remembered to update.

        Private, because it is the one way to obtain a bundle roll-up with no disclaimer on
        it. `headless-automation` requires a bundle to carry the disclaimer "in every case",
        and what upheld that was both callers here remembering to append it. A third caller
        reaching a public method would have shipped an undisclaimed roll-up and broken no
        test. Callers outside this class want `render` or `render_document`.
        """
        return "\n".join(
            [
                self.summary(),
                *(f"  {section}" for section in self.sections()),
                *self.assumptions_block(),
            ]
        )

    def render_document(self) -> str:
        """The exported bundle: the roll-up block, and then the checks themselves.

        `artifact-export` asks the evidence bundle to carry "the scorecard with thresholds
        and measured values", and its scenario is a senior engineer who receives **only the
        bundle** and re-runs the analysis. :meth:`render` cannot serve that reader and was
        never meant to: it is the roll-up over layers, one line per layer, and the line for
        the checks layer says ``3 run, 1 failing, 0 not evaluated``. Which one failed, at
        what safety factor, against which clause — none of it is in there.

        That was fine while the only consumer was the attestation predicate, which carries
        :attr:`scorecard` alongside the roll-up. It stopped being fine when ``anvilate
        export`` printed the roll-up as *the bundle*, and again when the MCP tool returned
        it: two surfaces handing a reviewer a document with no evidence in it, both saying
        the word "evidence" while they did it.

        So the roll-up stays exactly as it is — the predicate's canonical form must not move
        under an attestation somebody already signed — and the exported document is this,
        which is the roll-up, every check the card carries, and the spec they were computed
        from. ``ScorecardEntry.__str__`` does the per-check line, so the bundle and
        ``anvilate check`` cannot describe one check two ways.

        The spec is rendered as the YAML a reader can paste back into ``anvilate check``,
        which is what "reproduce the run" has to mean in a tool with a text front door: the
        document round-trips, so the bundle is not a description of the inputs but the
        inputs. A bundle carrying none says so in a line of its own.
        """
        # No empty-card branch: `_a_bundle_is_evidence_of_something` refuses a bundle over a
        # scorecard with no entries, so "checks:" is never a heading over nothing.
        return "\n".join(
            [
                self._render_rollup(),
                "checks:",
                *self._check_lines(),
                *self.spec_block(),
                SCREENING_DISCLAIMER,
            ]
        )

    def _check_lines(self) -> tuple[str, ...]:
        """One line per check, and under it the work, where the check did any.

        The reader this document is for receives **only the bundle** and re-runs the
        analysis. A verdict and a clause is not enough to re-run anything: the formula, the
        values put into it and the result are what a checker recomputes, and the library
        carries them for most of the clauses it cites. Leaving them out made the exported
        bundle a document that names its conclusions and withholds their arithmetic, which
        is the shape of the defect this method's own history already fixed once.

        The block comes from :meth:`anvilate.report.ReportSection.worked_lines`, which is
        also what the calculation report and ``anvilate check --show-work`` print, so one
        derivation cannot be described three ways.

        **In the units the spec declares**, which this bundle carries. It did not, so a
        document stating `units: US` was handed to its reviewer with every formula
        substituted in millimetres and megapascals — and the spec saying otherwise printed
        forty lines further down the same file.
        """
        from .report import ReportSection

        system = self.spec.units.value if self.spec is not None and self.spec.units else None
        lines: list[str] = []
        for entry in self.scorecard.entries:
            section = ReportSection(entry=entry)
            lines.append(f"  {section.headline(system=system)}")
            lines.extend(f"  {line}" for line in section.worked_lines(system=system))
        return tuple(lines)

    def spec_block(self) -> tuple[str, ...]:
        """The spec as rendered lines — never empty, so the heading never vanishes.

        The same rule :meth:`assumptions_block` follows one field along. A bundle with no
        spec in it cannot be re-run from, and that is a fact about the bundle a reader is
        owed in the document rather than by noticing an absence.
        """
        if self.spec is None:
            return (
                "spec: not carried — this bundle names its verdicts and not the inputs they "
                "were computed from, so the run cannot be reproduced from it alone",
            )
        return ("spec:", *(f"  {line}" for line in dump_spec_yaml(self.spec).splitlines()))

    def to_document_dict(self) -> dict[str, object]:
        """The exported bundle as JSON: the roll-up, and the whole card under ``scorecard``.

        The JSON half of :meth:`render_document`, and the same reasoning. Kept separate from
        :meth:`to_json_dict` rather than folded into it because that one is hashed into an
        attested predicate that already carries the card in its own field — folding it in
        would move every existing attestation's digest and put two copies of one card inside
        one signed document. The spec is here for the same reason and on the same terms:
        ``null`` rather than absent, so a consumer reading this document can tell "no spec"
        from "a key I forgot to look for".

        :class:`BundleDocument` is this document's published contract, and it deliberately
        does not *build* it. Constructing the model and dumping it with ``exclude_unset`` is
        the obvious way to reproduce the absent-versus-null distinction, and it also applies
        that exclusion to every nested model — dropping ``informational: false``,
        ``reference: null``, ``blocking: []`` and more out of eight nested structures.
        Pydantic offers no per-level control, so the choice was between changing what this
        document has always emitted and letting the model describe rather than produce it.
        Changing published bytes to improve a schema's provenance is the wrong trade.

        What keeps the two from drifting is a gate rather than a shared code path:
        ``test_every_document_this_library_can_build_validates_against_its_published_contract``
        validates every document built here against the model and against the released schema,
        and the key-set test beside it holds the model's fields to the keys this method emits.
        """
        return {
            **self.to_json_dict(),
            "scorecard": self.scorecard.model_dump(mode="json"),
            "spec": None if self.spec is None else self.spec.model_dump(mode="json"),
        }

    def to_json_dict(self) -> dict[str, object]:
        """The sections as JSON-safe primitives, for the attestation predicate.

        The **roll-up**, not the exported bundle: no per-check detail, because the predicate
        carries :attr:`AnvilatePredicate.scorecard` beside it. A surface handing this to a
        person wants :meth:`to_document_dict`.
        """
        card = self.callout_card()
        body: dict[str, object] = {
            # Always present, in both the rendered block and the predicate body: a label a
            # caller could omit is one that is missing from exactly the bundles that most
            # need it.
            "disclaimer": SCREENING_DISCLAIMER,
            "assumptions": list(self.assumptions),
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
        if self.exports:
            body["exports"] = [record.model_dump(mode="json") for record in self.exports]
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
