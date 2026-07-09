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

__all__ = [
    "CheckStatus",
    "ScorecardEntry",
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
        )

    def __str__(self) -> str:
        return f"[{self.status.value.upper()}] {self.name}: {self.detail}"
