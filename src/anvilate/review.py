"""The dossier a licensed engineer needs before deciding whether to seal.

Anvilate's output eventually reaches someone who must decide whether to put their seal on
it, and that decision is theirs — the NSPE Board of Ethical Review has held that failing
to maintain responsible charge over an AI tool's output before sealing is unethical, with
the framing that such a tool is like an engineering intern: the engineer sets the
constraints, does not blindly accept the output, and must satisfy themselves before
sealing.

This module produces the raw material for that scrutiny, assembled *for a reviewer*
rather than for a machine. Three things it does, and one it refuses to.

**It orders by what deserves attention, deterministically.** A reviewer's scarcest
resource is the decision about where to look first, and a scorecard in declaration order
does not help. :class:`ReviewPriority` fixes the order and :func:`review_priority`
assigns it, so two runs over the same scorecard produce the same dossier and a diff
between them means something.

**It attributes decisions.** :class:`DecisionOrigin` says whether a value came from the
user, from a deterministic computation, from a model (with its version), or from nowhere
anybody recorded. That last one is not an omission to tidy away — an unattributed
assumption is exactly what a reviewer most needs to see, and it sorts near the top.

**It binds a review to what was reviewed.** A :class:`ReviewRecord` carries the digest of
the artifact it covers. Change anything — a load, a material, a toolchain version — and
the digest moves and the record no longer applies. A review that survives the thing it
reviewed is worse than no review, because it reads like assurance.

**It never changes a verdict.** An engineer may accept an exception on a failing check;
that is their prerogative and it is recorded. The check still renders FAIL. Anvilate does
not have an "approved" state, does not certify, and the language gate in the test suite
enforces that every rendering here stays out of the vocabulary of certification.

Sources: NSPE Board of Ethical Review, "Use of Artificial Intelligence in Engineering
Practice"; NSPE Position Statement 03-1774 (AI-generated technical work receives at least
the same scrutiny as human work).
"""

from __future__ import annotations

import hashlib
from datetime import date
from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from ._models import RevalidatedModel
from .scorecard import CheckStatus, Scorecard, ScorecardEntry

__all__ = [
    "DecisionOrigin",
    "ReviewPriority",
    "ReviewItem",
    "ReviewRecord",
    "ReviewerDossier",
    "PROHIBITED_ASSURANCE_LANGUAGE",
    "review_priority",
    "artifact_digest",
    "build_dossier",
]

# The words a screening tool must never use about its own output. Checked over every
# rendering this module produces, by a gate in the test suite, because the failure mode
# is not a bug that shows up in a number — it is a sentence someone forwards.
PROHIBITED_ASSURANCE_LANGUAGE: frozenset[str] = frozenset(
    {
        "certified",
        "certifies",
        "certification",
        "approved for construction",
        "fit for service",
        "fit for continued service",
        "code compliant",
        "code-compliant",
        "meets all requirements",
        "sealed",
        "stamped",
        "guaranteed",
        "warrants",
    }
)

# A margin this close to its requirement is worth a reviewer's attention even though it
# passes: it is the band where an assumption the reviewer disagrees with flips the answer.
_THIN_MARGIN_RATIO = 1.10


class DecisionOrigin(StrEnum):
    """Where a value in the dossier came from.

    ``UNATTRIBUTED`` is not a tidy-up item. An assumption nobody recorded the source of is
    the single thing a reviewer most needs surfaced, so it sorts near the top rather than
    being defaulted to something reassuring.
    """

    USER = "user"  # the engineer supplied it
    DETERMINISTIC = "deterministic"  # computed by a cited closed form
    MODEL = "model"  # proposed by a language model, version recorded
    UNATTRIBUTED = "unattributed"  # nobody recorded where it came from


class ReviewPriority(IntEnum):
    """The order a reviewer should work in. Lower sorts first.

    Fixed and documented rather than tuned, because the point of an ordering is that two
    runs agree and a diff between dossiers means something. The order is not "worst
    first" — it is *most likely to change the engineer's decision* first, which is why an
    unevaluated check outranks a failing one: a FAIL is already visible and already
    blocking, while a NOT_EVALUATED is the check that silently is not there.
    """

    NOT_EVALUATED = 0
    FAILING = 1
    FRAGILE_MARGIN = 2
    UNATTRIBUTED_ASSUMPTION = 3
    MODEL_ASSUMPTION = 4
    THIN_MARGIN = 5
    OVER_MARGIN = 6
    ROUTINE = 7


def review_priority(entry: ScorecardEntry, *, origin: DecisionOrigin) -> ReviewPriority:
    """The priority band an entry falls in, given where its inputs came from.

    Status decides first, then attribution, then how close the margin runs. A passing
    check resting on an unattributed assumption outranks a passing check resting on a
    cited one, because the verdict is only as good as the input nobody sourced.
    """
    if entry.status is CheckStatus.NOT_EVALUATED:
        return ReviewPriority.NOT_EVALUATED
    if entry.status is CheckStatus.FAIL:
        return ReviewPriority.FAILING
    # A nominal PASS whose attached margin distribution shows a material shortfall
    # probability is the dossier's whole reason for existing, and it used to sort as
    # ROUTINE — headline "passes", absent from `attention_first`, and summarised as
    # "nothing above routine" — because the only closeness test here was the NOMINAL
    # ratio. A check at 1.6x its requirement on paper with a 46% chance of falling short
    # under its own declared input scatter is not routine, and it is not thin either: the
    # nominal margin looks ample, which is exactly what makes it worth a reviewer's eye.
    if entry.is_fragile():
        return ReviewPriority.FRAGILE_MARGIN
    if origin is DecisionOrigin.UNATTRIBUTED:
        return ReviewPriority.UNATTRIBUTED_ASSUMPTION
    if origin is DecisionOrigin.MODEL:
        return ReviewPriority.MODEL_ASSUMPTION
    if entry.status is CheckStatus.OVER_MARGIN:
        return ReviewPriority.OVER_MARGIN
    computed, required = entry.safety_factor, entry.required_safety_factor
    if computed is not None and required is not None and required > 0:
        if computed / required < _THIN_MARGIN_RATIO:
            return ReviewPriority.THIN_MARGIN
    return ReviewPriority.ROUTINE


class ReviewItem(BaseModel):
    """One line of a dossier: a check, why it is where it is, and who to ask about it."""

    model_config = ConfigDict(frozen=True)

    entry: ScorecardEntry
    priority: ReviewPriority
    origin: DecisionOrigin
    origin_detail: str = ""  # the model and version, or the user, or the citation

    @property
    def headline(self) -> str:
        """One line for a reviewer skimming: what it is and why it is here."""
        reason = {
            ReviewPriority.NOT_EVALUATED: "did not run — the check is not there",
            ReviewPriority.FAILING: "fails",
            ReviewPriority.UNATTRIBUTED_ASSUMPTION: "rests on an assumption nobody sourced",
            ReviewPriority.MODEL_ASSUMPTION: "rests on a value a model proposed",
            ReviewPriority.FRAGILE_MARGIN: (
                "passes nominally, but its input scatter fails it materially often"
            ),
            ReviewPriority.THIN_MARGIN: "passes, but close to its requirement",
            ReviewPriority.OVER_MARGIN: "passes above its band — possibly over-designed",
            ReviewPriority.ROUTINE: "passes",
        }[self.priority]
        suffix = f" ({self.origin_detail})" if self.origin_detail else ""
        return f"{self.entry.name}: {reason}{suffix}"


def artifact_digest(scorecard: Scorecard, *, toolchain: str) -> str:
    """A content digest binding a review to exactly what was reviewed.

    Covers the scorecard's full serialised content *and* the ``toolchain`` identifier, so
    a change to either moves the digest. Including the toolchain is the part that is easy
    to leave out and matters most: the same inputs through a different library version are
    a different piece of work, and a review that silently carried across the upgrade would
    be assurance nobody actually gave.
    """
    if not toolchain.strip():
        raise ValueError(
            "toolchain must identify what produced this artifact — the same inputs "
            "through a different version are a different piece of work, and a digest "
            "that ignores it would let a review survive an upgrade it never saw"
        )
    payload = scorecard.model_dump_json() + "\x00" + toolchain.strip()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ReviewRecord(RevalidatedModel):
    """A licensed engineer's record that they reviewed a specific artifact.

    ``covers_digest`` is the :func:`artifact_digest` of what was reviewed.
    :meth:`applies_to` re-derives the digest and says whether this record still covers the
    artifact in hand. Anything that moves the digest — an input, a material, a toolchain
    version — invalidates it, and that is the intended behaviour rather than an
    inconvenience.

    ``accepted_exceptions`` names checks the engineer has decided to accept despite their
    status. Recording an exception does **not** change the check: it still renders with
    the status it computed. A tool that let a review turn a FAIL into a pass would be
    laundering the engineer's judgement into an appearance of analysis.
    """

    model_config = ConfigDict(frozen=True)

    reviewer: str
    reviewed_on: date
    covers_digest: str
    scope: str
    accepted_exceptions: tuple[str, ...] = ()
    notes: str = ""

    @model_validator(mode="after")
    def _well_formed(self) -> ReviewRecord:
        for value, name in (
            (self.reviewer, "reviewer"),
            (self.scope, "scope"),
            (self.covers_digest, "covers_digest"),
        ):
            if not value.strip():
                raise ValueError(
                    f"{name} may not be blank — a review record with no {name} is not a "
                    f"record of anything"
                )
        return self

    def applies_to(self, scorecard: Scorecard, *, toolchain: str) -> bool:
        """True only if this record covers exactly this artifact from this toolchain."""
        return self.covers_digest == artifact_digest(scorecard, toolchain=toolchain)


class ReviewerDossier(BaseModel):
    """Everything a reviewer needs, ordered by what most deserves their attention.

    ``items`` are in :class:`ReviewPriority` order and ties keep the scorecard's own
    order, so the ordering is total and two runs over the same inputs agree exactly.

    ``status`` is the scorecard's status, unchanged and unchangeable from here. ``record``
    is the review, if one has been made and still applies; ``stale_record`` is True when a
    record exists but the artifact has moved underneath it — the state a reviewer most
    needs told, because it looks identical to "reviewed" from the outside.
    """

    model_config = ConfigDict(frozen=True)

    items: tuple[ReviewItem, ...]
    status: CheckStatus
    digest: str
    model_involvement: tuple[str, ...] = ()
    record: ReviewRecord | None = None
    stale_record: bool = False

    @property
    def attention_first(self) -> tuple[ReviewItem, ...]:
        """The items above routine — what a reviewer should read before anything else."""
        return tuple(i for i in self.items if i.priority < ReviewPriority.ROUTINE)

    def summary(self) -> str:
        """The line that goes at the top of a report pane. Never says 'approved'."""
        counts: dict[ReviewPriority, int] = {}
        for item in self.items:
            counts[item.priority] = counts.get(item.priority, 0) + 1
        parts = [
            f"{counts[p]} {p.name.lower().replace('_', ' ')}"
            for p in sorted(counts)
            if p < ReviewPriority.ROUTINE
        ]
        head = f"{len(self.items)} checks, overall {self.status.value}"
        needing = "; ".join(parts) if parts else "nothing above routine"
        if self.stale_record:
            state = "a prior review no longer applies — the artifact changed under it"
        elif self.record is not None:
            state = f"reviewed by {self.record.reviewer} on {self.record.reviewed_on.isoformat()}"
        else:
            state = "not yet reviewed"
        return f"{head}. For attention: {needing}. {state}."


def build_dossier(
    scorecard: Scorecard,
    *,
    toolchain: str,
    origins: dict[str, DecisionOrigin] | None = None,
    origin_details: dict[str, str] | None = None,
    record: ReviewRecord | None = None,
) -> ReviewerDossier:
    """Assemble a scorecard into a reviewer's dossier.

    ``origins`` maps a check name to where its inputs came from. **A check absent from the
    map is :attr:`DecisionOrigin.UNATTRIBUTED`, not routine** — defaulting an unrecorded
    origin to something reassuring is precisely the silent green this library exists to
    refuse, and it would make the attribution feature worse than useless by making its
    absence invisible.

    ``record`` is checked against the artifact rather than trusted: if it does not apply,
    it is carried through with ``stale_record`` set instead of being silently dropped,
    because "there was a review and it no longer covers this" is different information
    from "there was never a review".
    """
    origins = origins or {}
    origin_details = origin_details or {}
    items: list[ReviewItem] = []
    for entry in scorecard.entries:
        origin = origins.get(entry.name, DecisionOrigin.UNATTRIBUTED)
        items.append(
            ReviewItem(
                entry=entry,
                priority=review_priority(entry, origin=origin),
                origin=origin,
                origin_detail=origin_details.get(entry.name, ""),
            )
        )
    ordered = tuple(
        item for _, item in sorted(enumerate(items), key=lambda pair: (pair[1].priority, pair[0]))
    )
    digest = artifact_digest(scorecard, toolchain=toolchain)
    stale = record is not None and record.covers_digest != digest
    involvement = tuple(
        sorted(
            {
                origin_details.get(item.entry.name, "unspecified model")
                for item in ordered
                if item.origin is DecisionOrigin.MODEL
            }
        )
    )
    return ReviewerDossier(
        items=ordered,
        status=scorecard.status,
        digest=digest,
        model_involvement=involvement,
        record=record,
        stale_record=stale,
    )
