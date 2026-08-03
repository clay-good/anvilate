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
from .uncertainty import MarginUncertainty

__all__ = [
    "CheckStatus",
    "Direction",
    "RepairHint",
    "GoverningChange",
    "ScorecardEntry",
    "Scorecard",
]


class CheckStatus(StrEnum):
    """A check's outcome.

    ``NOT_EVALUATED`` is never silently treated as a pass — a check that could
    not run is reported as such. ``OVER_MARGIN`` is a passing check whose margin
    ran past a declared upper band: acceptable, never blocking, but flagged so an
    over-engineered candidate is as visible as a failing one.
    """

    PASS = "pass"
    FAIL = "fail"
    OVER_MARGIN = "over_margin"
    NOT_EVALUATED = "not_evaluated"


class Direction(StrEnum):
    """Which way a parameter has to move to improve a check's margin."""

    INCREASE = "increase"
    DECREASE = "decrease"


class RepairHint(BaseModel):
    """How to move a failing check back into bounds.

    A failed check computes this deterministically — never an LLM guess. It names
    the governing spec ``parameter`` by its stable name and the ``direction`` that
    improves the margin. When a paired design inverse exists, ``corrective_value``
    (in ``unit``) is the value of that parameter which satisfies the check at the
    required margin — turning repair from a search into a single solve. Without an
    inverse the value is ``None``: a direction is still honest, an invented number
    is not. ``provenance`` records where the hint came from (the inverse function,
    or a monotonicity declaration).
    """

    model_config = ConfigDict(frozen=True)

    parameter: str
    direction: Direction
    corrective_value: float | None = None
    unit: str | None = None
    provenance: str | None = None

    @classmethod
    def solved(
        cls,
        parameter: str,
        *,
        direction: Direction,
        value: float,
        unit: str | None = None,
        provenance: str | None = None,
    ) -> RepairHint:
        """A hint whose corrective value a design inverse supplied."""
        return cls(
            parameter=parameter,
            direction=direction,
            corrective_value=value,
            unit=unit,
            provenance=provenance,
        )

    @classmethod
    def directional(
        cls,
        parameter: str,
        *,
        direction: Direction,
        provenance: str | None = None,
    ) -> RepairHint:
        """A hint that names the parameter and direction but not a value.

        For a check that is monotonic in a parameter but has no paired inverse to
        solve for the corrective value.
        """
        return cls(parameter=parameter, direction=direction, provenance=provenance)

    def __str__(self) -> str:
        if self.corrective_value is None:
            return f"{self.direction.value} {self.parameter}"
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.direction.value} {self.parameter} to {self.corrective_value:.4g}{unit}"


class GoverningChange(BaseModel):
    """A shift in which check governs, reported across a revalidation.

    When a revision moves the tightest check from one to another — a thicker
    flange handing governance from bending to bolt bearing — the reviewer needs
    to know the reference point moved, not just that the numbers changed.
    """

    model_config = ConfigDict(frozen=True)

    previous: str
    current: str
    previous_utilization: float
    current_utilization: float

    def __str__(self) -> str:
        return (
            f"governing check changed: '{self.previous}' "
            f"(util {self.previous_utilization:.2f}) → '{self.current}' "
            f"(util {self.current_utilization:.2f})"
        )


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
    # The top of the target safety-factor band, when the spec declares one. A
    # check that runs above it is OVER_MARGIN — passing, but flagged as
    # over-engineered. ``None`` leaves the check one-sided (a minimum only).
    upper_safety_factor: float | None = None
    # How to move a failing check back into bounds, when the check can say. Set
    # only on FAIL entries; ``None`` otherwise.
    repair_hint: RepairHint | None = None
    # The worked calculation behind the verdict, when the check declares one. It
    # travels with the entry so a report renders the real formula and values
    # rather than a reconstruction.
    derivation: Derivation | None = None
    # An opt-in probabilistic view of the same check: the margin distribution under
    # input scatter. The deterministic status stays primary; this annotation, when
    # present, lets a nominal pass carry a fragility warning. ``None`` leaves the
    # check purely deterministic.
    uncertainty: MarginUncertainty | None = None

    def is_fragile(self, threshold: float = 0.05) -> bool:
        """Whether an attached margin distribution shows a material shortfall.

        ``True`` only when the check carries an uncertainty annotation whose
        shortfall probability exceeds ``threshold`` (default 5%) — a nominal pass
        that input scatter would fail materially often. ``False`` when no
        distribution is attached, so a check without one is never flagged.
        """
        return self.uncertainty is not None and self.uncertainty.is_fragile(threshold)

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
        """True when the check ran and met its minimum requirement.

        Covers both a clean ``PASS`` and an ``OVER_MARGIN`` check — over-margin
        met the minimum, it simply ran past the target band. Never true for a
        ``FAIL`` or a check that could not be evaluated."""
        return self.status in (CheckStatus.PASS, CheckStatus.OVER_MARGIN)

    @property
    def over_margin(self) -> bool:
        """Whether the check passed but ran past its declared upper band."""
        return self.status is CheckStatus.OVER_MARGIN

    @property
    def evaluated(self) -> bool:
        """Whether the check ran at all (pass, fail, or over-margin — not
        ``NOT_EVALUATED``)."""
        return self.status is not CheckStatus.NOT_EVALUATED

    @classmethod
    def from_safety_factor(
        cls,
        name: str,
        *,
        computed: float | None,
        required: float,
        upper: float | None = None,
        repair_hint: RepairHint | None = None,
    ) -> ScorecardEntry:
        """Build an entry from a computed safety factor against a required minimum.

        ``computed`` is ``None`` when the safety factor could not be found (e.g. a
        material property was missing) — the entry is ``NOT_EVALUATED``, never a
        silent pass. Otherwise it is ``PASS`` when ``computed >= required`` and
        ``FAIL`` below.

        ``upper`` opts the check into a two-sided band: a computed factor above it
        is ``OVER_MARGIN`` — still a pass, but flagged as over-engineered with the
        excess stated. Omit it and high margins pass silently, as before.

        ``repair_hint`` travels with a ``FAIL`` entry to say which parameter to
        move and, when a design inverse supplied it, to what value. It is dropped
        on a passing entry — a hint only belongs on a check that needs one.
        """
        if computed is None:
            return cls(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail="not evaluated — safety factor unavailable",
            )
        if computed < required:
            status = CheckStatus.FAIL
            detail = f"safety factor {computed:.2f} vs required minimum {required:.2f}"
        elif upper is not None and computed > upper:
            status = CheckStatus.OVER_MARGIN
            detail = (
                f"safety factor {computed:.2f} exceeds target band "
                f"{required:.2f}–{upper:.2f} by {computed - upper:.2f} — over-engineered"
            )
        else:
            status = CheckStatus.PASS
            detail = f"safety factor {computed:.2f} vs required minimum {required:.2f}"
        return cls(
            name=name,
            status=status,
            detail=detail,
            safety_factor=computed,
            required_safety_factor=required,
            upper_safety_factor=upper,
            repair_hint=repair_hint if status is CheckStatus.FAIL else None,
        )

    def __str__(self) -> str:
        cite = f" [{self.reference}]" if self.reference else ""
        return f"[{self.status.value.upper()}] {self.name}: {self.detail}{cite}"


class Scorecard(BaseModel):
    """A collection of check entries with a rolled-up overall status.

    The roll-up honours No-silent-green: the scorecard :attr:`status` is ``FAIL``
    if any check failed, else ``NOT_EVALUATED`` if any check could not run (or
    there are no checks at all), else ``OVER_MARGIN`` if any check passed above
    its band, and only ``PASS`` when every check ran and passed cleanly. So
    :attr:`passed` is never true while a check is unevaluated, and an
    over-engineered card is visible without being blocked.
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[ScorecardEntry, ...] = ()

    @property
    def status(self) -> CheckStatus:
        if any(e.status is CheckStatus.FAIL for e in self.entries):
            return CheckStatus.FAIL
        if not self.entries or any(e.status is CheckStatus.NOT_EVALUATED for e in self.entries):
            return CheckStatus.NOT_EVALUATED
        if any(e.status is CheckStatus.OVER_MARGIN for e in self.entries):
            return CheckStatus.OVER_MARGIN
        return CheckStatus.PASS

    @property
    def passed(self) -> bool:
        """True when there is at least one check and every one met its minimum.

        Includes a card whose only blemish is over-margin checks — over-margin is
        a warning, not a blocker. Never true while a check failed or could not run.
        """
        return self.status in (CheckStatus.PASS, CheckStatus.OVER_MARGIN)

    def failures(self) -> tuple[ScorecardEntry, ...]:
        """The checks that ran and failed — the blocking issues."""
        return tuple(e for e in self.entries if e.status is CheckStatus.FAIL)

    def over_margin(self) -> tuple[ScorecardEntry, ...]:
        """The checks that passed but ran past their band — the over-engineered."""
        return tuple(e for e in self.entries if e.status is CheckStatus.OVER_MARGIN)

    def repair_hints(self) -> tuple[RepairHint, ...]:
        """The repair hints carried by failing checks — the actionable feedback."""
        return tuple(e.repair_hint for e in self.entries if e.repair_hint is not None)

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

    def governing_shift(self, previous: Scorecard) -> GoverningChange | None:
        """How the governing check moved since ``previous``, or ``None``.

        ``None`` when either card has no check carrying a safety factor, or when
        the same check still governs. Otherwise a :class:`GoverningChange` naming
        both — so a revalidation states that the reference point moved rather than
        leaving the reviewer to notice.
        """
        before = previous.governing()
        after = self.governing()
        if before is None or after is None or before.name == after.name:
            return None
        return GoverningChange(
            previous=before.name,
            current=after.name,
            previous_utilization=before.utilization,
            current_utilization=after.utilization,
        )

    def not_evaluated(self) -> tuple[ScorecardEntry, ...]:
        """The checks that could not run — the gaps, never silently passed."""
        return tuple(e for e in self.entries if e.status is CheckStatus.NOT_EVALUATED)

    def fragile(self, threshold: float = 0.05) -> tuple[ScorecardEntry, ...]:
        """The checks whose attached margin distribution shows a material shortfall.

        A nominal pass can still be fragile: its deterministic verdict stays as it
        is, but this surfaces the checks where the asserted input scatter fails the
        margin more than ``threshold`` of the time — no silent green under
        uncertainty. Empty when no check carries a distribution.
        """
        return tuple(e for e in self.entries if e.is_fragile(threshold))

    def __str__(self) -> str:
        return f"scorecard {self.status.value.upper()} ({len(self.entries)} checks)"
