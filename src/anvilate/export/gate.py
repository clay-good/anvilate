"""The gate every artifact export passes, and the watermark it stamps.

``artifact-export`` says it in one sentence: export of CAD artifacts is enabled only when
the part's acceptance checks pass; a caller *may* export an unvalidated part, and then the
exported file's metadata must be watermarked as unvalidated. Until this module existed the
sentence was enforced nowhere. :func:`~anvilate.export.dxf.export_plate_dxf` took a width,
a height and a list of holes, and wrote a file a plasma cutter reads — with no scorecard in
sight and nothing in the file saying what, if anything, had been checked.

The shape of the fix is the whole point:

* **The authorization is an argument, not a default.** Every export entry point takes an
  :class:`ExportAuthorization` as a required keyword. An optional one is one a caller can
  omit, and the calls that omit it are exactly the calls that would have been ungated.
* **A refusal is an exception, not a flag.** :func:`authorize_export` raises
  :class:`ExportRefused` naming the blocking checks. There is no return value that means
  "not allowed" for a caller to forget to read.
* **There is no unwatermarked authorization.** Both branches carry a watermark. A passing
  card is still a T1 analytical screen, and a file that says so is the difference between
  evidence and a drawing somebody builds from.
* **The override is consumed where it is declared.** ``override=True`` on a card that
  already passes raises: an override that overrides nothing means the caller believed the
  card was failing, and the interesting case is the one where they were right about a
  *different* card.
"""

from __future__ import annotations

from pydantic import ConfigDict, model_validator

from .._models import RevalidatedModel
from ..refusal import RefusalError, Remedy
from ..scorecard import CheckStatus, Scorecard

_SCORECARD_SOURCE = "the part's acceptance scorecard from its screening run"
_GATE_DECISION_SOURCE = "the authorization authorize_export returned for the part's scorecard"
_ARTIFACT_NAME_SOURCE = "the exported file's name or format as written"


class _GateInputError(RefusalError, ValueError):
    """An export-gate input that cannot be used without correction."""


def _gate_refusal(message: str, *, subject: str, source: str) -> _GateInputError:
    return _GateInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "ExportAuthorization",
    "ExportRecord",
    "ExportRefused",
    "SCREENING_NOTICE",
    "authorize_export",
]

# The one sentence that goes into every exported file regardless of verdict. It is not the
# unvalidated watermark — it is the statement that even a clean pass is a screen. Kept short
# because a DXF custom property holds a single line, and quoted verbatim by the tests.
SCREENING_NOTICE = (
    "T1 analytical screening, not a certified analysis and not a release for fabrication."
)

# The line that carries the requirement's "watermarked as unvalidated". Distinct enough that
# a grep for it over an exported file is a yes/no answer.
_UNVALIDATED_NOTICE = (
    "UNVALIDATED EXPORT: the acceptance checks did not pass and were explicitly overridden."
)

# The metadata keys an exported file carries. Namespaced, because a DXF header and a QIF
# header are shared with whatever else wrote to them.
STATUS_KEY = "ANVILATE_EXPORT_STATUS"
NOTICE_KEY = "ANVILATE_EXPORT_NOTICE"
BLOCKING_KEY = "ANVILATE_EXPORT_BLOCKING"


class ExportRefused(RefusalError):
    """Raised when an export is attempted on a part whose acceptance checks did not pass.

    Carries the blocking check names so the message says *what* is unmet rather than that
    something is. A caller who means it asks again with ``override=True`` and gets a
    watermarked artifact; there is no way to ask again and get an unmarked one.
    """

    def __init__(self, blocking: tuple[str, ...], *, unverified: bool = False) -> None:
        self.blocking = blocking
        named = ", ".join(blocking) if blocking else "no checks were run at all"
        # What is unmet, without the remedy: `override=True` is a remedy for a caller
        # holding the library, and a surface with its own remedy (the CLI's `--unvalidated`,
        # or none) states that one after this instead.
        self.unmet = (
            "export is gated on checks this library ships, and this card passes on the word "
            f"of a third-party module, which is evidence to weigh, not validation: {named}"
            if unverified
            else f"export is gated on the acceptance checks passing, and these did not: {named}"
        )
        super().__init__(
            f"{self.unmet}. "
            f"Pass override=True to export anyway; the file will be watermarked as "
            f"unvalidated",
            remedies=(
                Remedy(
                    action="pass override=True for",
                    subject=f"the export blocked by {named}",
                    source="the export policy and the blocking checks named in this refusal",
                ),
            ),
        )


class ExportAuthorization(RevalidatedModel):
    """Permission to write one artifact, and the watermark that goes into it.

    Constructed by :func:`authorize_export` and not usefully by hand: the validator below
    refuses the two combinations that would let a caller assemble a clean-looking
    authorization for a part that did not pass.
    """

    model_config = ConfigDict(frozen=True)

    validated: bool
    # True exactly when a caller asked to export past a failing card. Never true alongside
    # ``validated`` — see the validator.
    overridden: bool = False
    # The checks that stood in the way, empty for a validated export. Names only: the
    # scorecard itself is the place to read the details, and a file header is not.
    blocking: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _watermark_matches_the_verdict(self) -> ExportAuthorization:
        if self.validated and self.overridden:
            raise _gate_refusal(
                "an authorization cannot be both validated and overridden; an override "
                "exists only because the acceptance checks did not pass",
                subject="validated and overridden",
                source=_GATE_DECISION_SOURCE,
            )
        if self.validated and self.blocking:
            raise _gate_refusal(
                f"a validated export names blocking checks {list(self.blocking)}; a check "
                "that blocks is a check that did not pass, and the card did",
                subject="validated and blocking",
                source=_GATE_DECISION_SOURCE,
            )
        if not self.validated and not self.overridden:
            raise _gate_refusal(
                "an unvalidated export exists only as an explicit override; without one "
                "there is no authorization to hold, there is a refusal",
                subject="validated and overridden",
                source=_GATE_DECISION_SOURCE,
            )
        return self

    def model_copy(self, **kwargs: object) -> ExportAuthorization:
        """A copy with the invariant re-checked, because ``model_copy`` skips validators.

        The whole value of this object is that ``validated`` cannot disagree with
        ``blocking``. ``model_copy(update={"validated": True})`` on a refused export would
        walk straight around the ``mode="after"`` validator and hand an exporter a clean
        watermark for a failing part, which is the one outcome this module exists to
        prevent.
        """
        copied = super().model_copy(**kwargs)  # type: ignore[arg-type]
        return ExportAuthorization.model_validate(copied.model_dump())

    @property
    def status(self) -> str:
        """``"VALIDATED"`` or ``"UNVALIDATED"`` — the value of the status metadata key."""
        return "VALIDATED" if self.validated else "UNVALIDATED"

    def watermark(self) -> tuple[str, ...]:
        """The lines to write into the artifact, screening notice first.

        Never empty. A validated export carries one line, an overridden one carries three:
        the screening notice, the unvalidated notice, and the checks it was exported past.
        """
        lines = [SCREENING_NOTICE]
        if not self.validated:
            lines.append(_UNVALIDATED_NOTICE)
            named = ", ".join(self.blocking) if self.blocking else "no checks were run at all"
            lines.append(f"Blocking checks: {named}.")
        return tuple(lines)

    def metadata(self) -> tuple[tuple[str, str], ...]:
        """The watermark as key/value pairs for a file header.

        A DXF custom property and a QIF header entry are both key/value, so the watermark
        is expressed once, here, and each exporter only has to know where its format puts a
        pair. Values are single lines: a DXF custom property is one string.
        """
        pairs = [(STATUS_KEY, self.status), (NOTICE_KEY, SCREENING_NOTICE)]
        if not self.validated:
            named = ", ".join(self.blocking) if self.blocking else "no checks were run at all"
            pairs.append((BLOCKING_KEY, f"{_UNVALIDATED_NOTICE} Blocking checks: {named}."))
        return tuple(pairs)


def _blocking(scorecard: Scorecard | None) -> tuple[str, ...]:
    """The names of the checks standing between this card and an export.

    Failures and could-not-runs both block, which is the scorecard's own roll-up rather
    than a second opinion about it: :attr:`Scorecard.passed` is already false while a check
    is unevaluated, so counting only ``failures()`` here would let a card export whose
    checks never ran. ``None`` — nothing was screened — blocks with an empty list, which
    :class:`ExportRefused` and the watermark both spell out rather than print as ``[]``.
    """
    if scorecard is None:
        return ()
    return tuple(e.name for e in (*scorecard.failures(), *scorecard.not_evaluated()))


def authorize_export(scorecard: Scorecard | None, *, override: bool = False) -> ExportAuthorization:
    """Decide whether one artifact may be written, and with what watermark.

    ``scorecard`` is the part's acceptance card; ``None`` means nothing was screened, which
    is not a pass. Returns an :class:`ExportAuthorization` when the card passes, or when
    ``override`` is set. Raises :class:`ExportRefused` otherwise, and :class:`ValueError`
    when ``override`` is set on a card that passes — an override that overrides nothing is
    a caller working from a different card than the one they handed in.
    """
    passed = scorecard is not None and scorecard.passed
    # A pass that rests on a third-party module's word is evidence for a reader to weigh,
    # not a validated part: the discipline-packs spec forbids treating it as an in-tree
    # check. So such a card exports only the way a failing one does, watermarked.
    unverified = (
        ()
        if scorecard is None
        else tuple(
            f"{entry.name} ({entry.origin})"
            for entry in scorecard.entries
            if entry.origin is not None and entry.status is not CheckStatus.NOT_EVALUATED
        )
    )
    if passed and unverified:
        if not override:
            raise ExportRefused(unverified, unverified=True)
        return ExportAuthorization(validated=False, overridden=True, blocking=unverified)
    if passed:
        if override:
            raise _gate_refusal(
                "override=True was passed for a part whose acceptance checks pass, so "
                "there is nothing to override. An override that is a no-op means the "
                "caller expected a failing card and did not get one",
                subject="override and scorecard",
                source=_SCORECARD_SOURCE,
            )
        return ExportAuthorization(validated=True)
    blocking = _blocking(scorecard)
    if not override:
        raise ExportRefused(blocking)
    return ExportAuthorization(validated=False, overridden=True, blocking=blocking)


class ExportRecord(RevalidatedModel):
    """One artifact that was emitted, and the authorization it left under.

    The requirement watermarks two things, not one: the exported file's own metadata *and*
    the evidence bundle. The file half is :meth:`ExportAuthorization.metadata`, written by
    each exporter. This is the bundle half — the disclosure that an artifact exists in the
    world, named, with the verdict it carries.

    It is deliberately a *record of what happened* rather than a permission: nothing
    consults it before writing. A bundle that carries none of these is not a bundle that
    exported nothing; it is one that does not say, and
    :meth:`~anvilate.bundle.BundleSections.missing` names it as such.
    """

    model_config = ConfigDict(frozen=True)

    # What was written — a filename, a format name, whatever identifies the artifact to
    # someone holding the bundle. Non-empty, because an unnamed artifact is a disclosure
    # nobody can act on.
    artifact: str
    authorization: ExportAuthorization

    @model_validator(mode="after")
    def _the_artifact_is_named(self) -> ExportRecord:
        if not self.artifact.strip():
            raise _gate_refusal(
                "an export record needs the artifact it is about; an unnamed artifact is a "
                "disclosure that an unvalidated file exists somewhere",
                subject="artifact",
                source=_ARTIFACT_NAME_SOURCE,
            )
        return self

    def __str__(self) -> str:
        if self.authorization.validated:
            return f"{self.artifact}: VALIDATED"
        named = ", ".join(self.authorization.blocking) or "no checks were run at all"
        return f"{self.artifact}: UNVALIDATED, exported past {named}"
