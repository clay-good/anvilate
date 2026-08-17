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
from math import isnan

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


def _blocking_rank(status: CheckStatus) -> int:
    """How much a status blocks, for ordering: failed > could-not-run > passed.

    Mirrors the precedence :attr:`Scorecard.status` rolls up with, so a ranking
    built on it can never place a passing check above a blocking one.
    """
    if status is CheckStatus.FAIL:
        return 2
    if status is CheckStatus.NOT_EVALUATED:
        return 1
    return 0


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


def _format_utilization(value: float | None) -> str:
    """A utilization for display, or the no-safety-factor case said out loud."""
    return "util —" if value is None else f"util {value:.2f}"


class GoverningChange(BaseModel):
    """A shift in which check governs, reported across a revalidation.

    When a revision moves the tightest check from one to another — a thicker
    flange handing governance from bending to bolt bearing — the reviewer needs
    to know the reference point moved, not just that the numbers changed.
    """

    model_config = ConfigDict(frozen=True)

    previous: str
    current: str
    # `None` where the governing check carries no safety factor. `governing()` is
    # deliberately widened to let a blocking check without one govern — every deflection
    # and serviceability check is built that way — so these must admit the same absence
    # its own `ScorecardEntry.utilization` does. Declared `float`, they raised a pydantic
    # ValidationError on exactly the revision a shift report exists to describe.
    previous_utilization: float | None = None
    current_utilization: float | None = None

    def __str__(self) -> str:
        previous = _format_utilization(self.previous_utilization)
        current = _format_utilization(self.current_utilization)
        return (
            f"governing check changed: '{self.previous}' "
            f"({previous}) → '{self.current}' ({current})"
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
        # A zero factor was already infinitely utilized; a NEGATIVE one is strictly worse
        # (capacity exceeded, or a sign-flipped interaction ratio) and used to divide out to a
        # negative utilization, which ranked BELOW every passing check. governing() then named
        # a passing check as governing in a report whose overall status was FAIL.
        if self.safety_factor <= 0:
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
        # NaN compares False against every operand, so it used to fall past both the FAIL and
        # the OVER_MARGIN branch and land on the PASS else -- a silent green for a check that
        # never produced a number. This is the single funnel every screen puts its float
        # through, so one NaN upstream turned into a clean pass anywhere in the library.
        if isnan(computed):
            return cls(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail="not evaluated — safety factor came out NaN",
                required_safety_factor=required,
                upper_safety_factor=upper,
            )
        # The same NaN trap on the other operands. A NaN *requirement* makes `computed <
        # required` False and `computed > upper` False, so control fell through to the PASS
        # else-branch: a check judged against an unknown minimum reported as green. An
        # unknown requirement is a check that could not run, not one that passed.
        if isnan(required):
            return cls(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail="not evaluated — the required safety factor came out NaN",
                safety_factor=computed,
                upper_safety_factor=upper,
            )
        if upper is not None and isnan(upper):
            return cls(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail="not evaluated — the upper safety-factor band came out NaN",
                safety_factor=computed,
                required_safety_factor=required,
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

        Blocking status outranks utilization, so the governing check honours the
        same precedence as the roll-up in :attr:`status` — a failing check, then
        one that could not run, then the largest
        :attr:`ScorecardEntry.utilization`. Without that ordering a card can fail
        on a check carrying no safety factor (every deflection and serviceability
        check is built that way) and still name a *passing* check as governing,
        pointing the reviewer away from the one thing that blocks.

        ``None`` only when nothing blocks and no check carries a safety factor.
        """
        ranked = [e for e in self.entries if e.utilization is not None or _blocking_rank(e.status)]
        if not ranked:
            return None
        return max(ranked, key=lambda e: (_blocking_rank(e.status), e.utilization or 0.0))

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
