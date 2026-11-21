"""Risk records in the open hazard structure, each control verified by its own check.

ISO 14971 (medical devices) and ISO 12100 (machinery) share one chain: a **hazard** meets a
person in a **hazardous situation** that can lead to a **harm**; the risk is estimated from
the harm's severity and its probability; **risk controls** reduce it; and each control's
**verification** shows it was implemented and works. That chain is open structure. The
severity and probability categories, and whether the residual risk is acceptable, belong
to the manufacturer's risk-management plan, so here they are labels you supply and are
never computed.

What Anvilate adds is the last link. A control that *is* a check on the card (a guard's
clearance, a lifting lug's margin) names it, and :func:`assess_risks` gives the control
that check's verdict as its verification: a passing check verifies it, and a failing or
unrun one leaves it **not verified**, naming the entry. A control verified some other way
says how, in words, and is reported as declared rather than as checked.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from pydantic import ConfigDict, Field, model_validator

from ._models import ItemCollection, Named, Provenance, StatableModel, each_one
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard

__all__ = [
    "RISK_COLUMNS",
    "RiskControl",
    "RiskRecord",
    "ControlVerification",
    "RiskRow",
    "RiskReport",
    "assess_risks",
]

_SOURCE = "the risk-management file: each hazard, its controls, and how each is verified"

#: The risk file's CSV columns, in order: one row per control (or per record with none).
RISK_COLUMNS = (
    "record",
    "hazard",
    "hazardous situation",
    "harm",
    "severity",
    "probability",
    "risk control",
    "verification",
    "verified",
)


class _RiskInputError(RefusalError, ValueError):
    """A risk-record input that cannot be used without correction."""


def _refuse(message: str, *, subject: str) -> _RiskInputError:
    return _RiskInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=_SOURCE),)
    )


class RiskControl(StatableModel):
    """One measure that reduces a risk, and how it is verified.

    ``check`` names an entry on the scorecard; the control then takes that check's verdict.
    ``verification`` says in words how a control with no check is verified (a usability
    test, a label review). One or the other, not both: a control verified twice two ways
    would report whichever is kinder.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: Named
    check: Named | None = None
    verification: Provenance | None = None

    @model_validator(mode="after")
    def _one_way(self) -> RiskControl:
        if self.check is not None and self.verification is not None:
            raise _refuse(
                f"control '{self.description}' names both a check and a verification; a "
                "control linked to a check is verified by that check",
                subject="check, verification",
            )  # fmt: skip
        return self


class RiskRecord(StatableModel):
    """One hazard chain, as ISO 14971 and ISO 12100 both structure it.

    ``severity`` and ``probability`` are your risk-management plan's own categories, as you
    estimated them; they are carried as written and never computed or compared.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    hazard: Named
    hazardous_situation: Named
    harm: Named
    severity: Named
    probability: Named
    controls: tuple[RiskControl, ...] = Field(default=(), max_length=256)


class ControlVerification(StatableModel):
    """One control and whether it is verified.

    ``verified`` is ``True`` only when its check passes, ``False`` when its check failed,
    did not run or was deferred, and ``None`` when nothing on the card verifies it: a
    verification declared in words, or none at all, is the user's to show.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    control: Named
    check: Named | None = None
    status: CheckStatus | None = None
    verified: bool | None
    statement: str

    def __str__(self) -> str:
        return f"{self.control}: {self.statement}"


class RiskRow(StatableModel):
    """One risk record with each control's verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record: RiskRecord
    controls: tuple[ControlVerification, ...] = ()

    @property
    def not_verified(self) -> tuple[ControlVerification, ...]:
        """The controls whose check failed, did not run or was deferred."""
        return tuple(c for c in self.controls if c.verified is False)

    def __str__(self) -> str:
        r = self.record
        head = (f"{r.id}: {r.hazard} -> {r.hazardous_situation} -> {r.harm} "
                f"(severity {r.severity}, probability {r.probability})")  # fmt: skip
        if not self.controls:
            return f"{head}\n  no risk control declared"
        return "\n".join([head, *(f"  {c}" for c in self.controls)])


class RiskReport(ItemCollection, StatableModel):
    """Every risk record, each control with its verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[RiskRow, ...]

    @property
    def not_verified(self) -> tuple[tuple[str, str], ...]:
        """Each (record, control) whose check does not verify it."""
        return tuple((row.record.id, c.control) for row in self.rows for c in row.not_verified)

    def to_csv(self) -> str:
        """The risk file as CSV, one row per control and one for a record with none. A cell
        a spreadsheet would read as a formula is written as text."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(RISK_COLUMNS)
        for row in self.rows:
            r = row.record
            head = (r.id, r.hazard, r.hazardous_situation, r.harm, r.severity, r.probability)
            for c in row.controls or (None,):
                if c is None:
                    tail: tuple[str, ...] = ("", "no risk control declared", "")
                else:
                    tail = (c.control, c.statement, _VERIFIED[c.verified])
                writer.writerow(_safe((*head, *tail)))
        return out.getvalue()

    def __str__(self) -> str:
        bad = self.not_verified
        head = f"{len(self.rows)} risk record(s); {len(bad)} control(s) not verified"
        return "\n".join([head, *(str(row) for row in self.rows)])


_VERIFIED = {True: "yes", False: "NO", None: ""}
_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _safe(cells: Sequence[str]) -> list[str]:
    return [("'" + c) if c.startswith(_FORMULA_LEADS) else c for c in cells]


def _verify(control: RiskControl, card: Scorecard) -> ControlVerification:
    if control.check is None:
        statement = (f"declared: {control.verification}" if control.verification
                     else "no verification declared")  # fmt: skip
        return ControlVerification(control=control.description, verified=None,
                                   statement=statement)  # fmt: skip
    entry = next(e for e in card.entries if e.name == control.check)
    status = entry.status
    if status in (CheckStatus.PASS, CheckStatus.OVER_MARGIN, CheckStatus.WARNING):
        verified, statement = True, f"verified by {entry.name} ({status.value})"
    elif status is CheckStatus.FAIL:
        verified, statement = False, f"NOT verified: {entry.name} fails — {entry.detail}"
    elif status is CheckStatus.OUT_OF_DEPTH:
        verified, statement = False, f"NOT verified: {entry.name} was deferred to a later depth"
    else:
        verified, statement = False, f"NOT verified: {entry.name} did not run — {entry.detail}"
    return ControlVerification(control=control.description, check=entry.name, status=status,
                               verified=verified, statement=statement)  # fmt: skip


def assess_risks(records: Sequence[RiskRecord], *, scorecard: Scorecard) -> RiskReport:
    """Each risk record with each control's verification, from the checks it names.

    A control naming a check takes its verdict: a pass (or a warning or over-margin pass)
    verifies it; a failure, a check that did not run, or one deferred leaves it not
    verified, naming the entry. A check name the card does not hold is refused: a control
    verified by a check that does not exist would read as verified and is not.
    """
    records = each_one(records, RiskRecord, named="records")
    if not isinstance(scorecard, Scorecard):
        raise _refuse("scorecard must be a Scorecard", subject="scorecard")
    ids = [r.id for r in records]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    if twice:
        raise _refuse(f"risk records {twice} are declared twice", subject="records")
    held = {entry.name for entry in scorecard.entries}
    for record in records:
        unknown = sorted({c.check for c in record.controls if c.check and c.check not in held})
        if unknown:
            raise _refuse(f"risk record {record.id} names checks {unknown}, which are not on "
                          f"the card ({sorted(held)})", subject="records")  # fmt: skip
    return RiskReport(rows=tuple(
        RiskRow(record=r, controls=tuple(_verify(c, scorecard) for c in r.controls))
        for r in records
    ))  # fmt: skip
