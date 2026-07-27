"""The scorecard vocabulary: one typed result per validation check.

Every check in the pipeline — a T1 analytical safety factor, a DFM tolerance
screen, a stack-up gap — reports a :class:`ScorecardEntry`: a name, a tri-state
:class:`CheckStatus`, and a human-readable detail line. The tri-state is the
"No silent green" rule made concrete: a check that *could not run* reports
``NOT_EVALUATED``, never ``PASS``. A caller filters ``failed`` for the blocking
issues and ``not_evaluated`` for the gaps.

This module holds the primitive; the checks that produce entries and the roll-up
that collects them into a full scorecard land as those layers are built out (see
openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .derivation import Derivation

__all__ = [
    "CheckStatus",
    "ScorecardEntry",
    "Scorecard",
]


class CheckStatus(StrEnum):
    """A check's outcome. ``NOT_EVALUATED`` is never silently treated as a pass —
    a check that could not run is reported as such."""

    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class ScorecardEntry(BaseModel):
    """One check's result: a name, a tri-state status, and a detail line."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: CheckStatus
    detail: str
    reference: str | None = None  # the code/standard clause behind the check, if any
    # The numbers behind the verdict, kept alongside the detail line so a report
    # can rank checks by how close they run to their limit rather than re-parsing
    # prose. Both are None for a check that did not come from a safety factor.
    safety_factor: float | None = None
    required_safety_factor: float | None = None
    # The worked calculation behind the verdict, when the check declares one. It
    # travels with the entry so a report renders the real formula and values
    # rather than a reconstruction.
    derivation: Derivation | None = None

    @property
    def utilization(self) -> float | None:
        """How much of the allowed margin the check uses, required/computed.

        1.0 sits exactly at the limit, above 1.0 is a failure, and the *largest*
        utilization among a set of checks is the governing one. ``None`` when the
        check did not come from a safety factor.
        """
        if self.safety_factor is None or self.required_safety_factor is None:
            return None
        if self.safety_factor == 0:
            return float("inf")
        return self.required_safety_factor / self.safety_factor

    @property
    def passed(self) -> bool:
        """True only when the check actually ran and passed — never for a check
        that could not be evaluated."""
        return self.status is CheckStatus.PASS

    @property
    def evaluated(self) -> bool:
        """Whether the check ran at all (pass or fail, not ``NOT_EVALUATED``)."""
        return self.status is not CheckStatus.NOT_EVALUATED

    @classmethod
    def from_safety_factor(
        cls,
        name: str,
        *,
        computed: float | None,
        required: float,
    ) -> ScorecardEntry:
        """Build an entry from a computed safety factor against a required minimum.

        ``computed`` is ``None`` when the safety factor could not be found (e.g. a
        material property was missing) — the entry is ``NOT_EVALUATED``, never a
        silent pass. Otherwise it is ``PASS`` when ``computed >= required`` and
        ``FAIL`` below.
        """
        if computed is None:
            return cls(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail="not evaluated — safety factor unavailable",
            )
        if computed >= required:
            status = CheckStatus.PASS
        else:
            status = CheckStatus.FAIL
        return cls(
            name=name,
            status=status,
            detail=f"safety factor {computed:.2f} vs required minimum {required:.2f}",
            safety_factor=computed,
            required_safety_factor=required,
        )

    def __str__(self) -> str:
        cite = f" [{self.reference}]" if self.reference else ""
        return f"[{self.status.value.upper()}] {self.name}: {self.detail}{cite}"


class Scorecard(BaseModel):
    """A collection of check entries with a rolled-up overall status.

    The roll-up honours No-silent-green: the scorecard :attr:`status` is ``FAIL``
    if any check failed, else ``NOT_EVALUATED`` if any check could not run (or
    there are no checks at all), and only ``PASS`` when every check ran and
    passed. So :attr:`passed` is never true while a check is unevaluated.
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[ScorecardEntry, ...] = ()

    @property
    def status(self) -> CheckStatus:
        if any(e.status is CheckStatus.FAIL for e in self.entries):
            return CheckStatus.FAIL
        if not self.entries or any(e.status is CheckStatus.NOT_EVALUATED for e in self.entries):
            return CheckStatus.NOT_EVALUATED
        return CheckStatus.PASS

    @property
    def passed(self) -> bool:
        """True only when there is at least one check and every one ran and passed."""
        return self.status is CheckStatus.PASS

    def failures(self) -> tuple[ScorecardEntry, ...]:
        """The checks that ran and failed — the blocking issues."""
        return tuple(e for e in self.entries if e.status is CheckStatus.FAIL)

    def governing(self) -> ScorecardEntry | None:
        """The check running closest to (or furthest past) its limit.

        The entry with the largest :attr:`ScorecardEntry.utilization` — the one a
        reviewer reads first, and the one that has to move before anything else
        matters. ``None`` when no check carries a safety factor.
        """
        ranked = [e for e in self.entries if e.utilization is not None]
        if not ranked:
            return None
        return max(ranked, key=lambda e: e.utilization)

    def not_evaluated(self) -> tuple[ScorecardEntry, ...]:
        """The checks that could not run — the gaps, never silently passed."""
        return tuple(e for e in self.entries if e.status is CheckStatus.NOT_EVALUATED)

    def __str__(self) -> str:
        return f"scorecard {self.status.value.upper()} ({len(self.entries)} checks)"
