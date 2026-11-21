"""The next step: what a result says to do, derived from the result alone.

An agent that has just screened a part has a card and no plan. Left to itself it stops at
the first green line, or retries the same call, or asks the person what to do about a
failure the card already knows how to repair. :func:`next_steps` turns a card into an
ordered list of typed steps, each naming the tool to call, what to pass it, and why, by
one fixed precedence:

1. a refusal's own remedies;
2. failed checks whose design inverse solved a corrective value (re-validate with it);
3. failed checks with no solved value (re-validate after moving the named parameter);
4. tiers the document demands that did not run (build the solid; run the FEA);
5. checks held back by a value nobody declared, one step per missing declaration;
6. when nothing holds the result back, the export of the evidence for review.

The list is a function of the result: the same card gives the same steps, and it is never
empty, because a result short of review always has something left to do, even if that is
exporting a draft. Every tool it names is one the server publishes, which a test holds
against the live catalog.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ConfigDict, Field

from ._models import EMPTY_MAP, FrozenMap, ItemCollection, Named, StatableModel, each_one
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard

__all__ = [
    "NEXT_STEP_TOOLS",
    "NextStep",
    "NextSteps",
    "next_steps",
]

#: Every tool a step may name. A test holds each against the server's published catalog.
NEXT_STEP_TOOLS = ("run_validation", "build_part", "run_fea_validation", "export_artifact")

# A tier the card reports as an entry of its own when the document demands it and it did
# not run, and the tool that runs it.
_TIER_TOOLS = {"T0 geometry": "build_part", "T3 FEA": "run_fea_validation"}


class _JourneyInputError(RefusalError, ValueError):
    """A next-step input that cannot be used without correction."""


class NextStep(StatableModel):
    """One step: the tool to call, what to pass it beyond the subject, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Named
    arguments: FrozenMap[str, str] = Field(default_factory=lambda: EMPTY_MAP)
    reason: Named

    def __str__(self) -> str:
        passed = ", ".join(f"{k}={v}" for k, v in self.arguments.items())
        return f"{self.tool}({passed}): {self.reason}"


class NextSteps(ItemCollection, StatableModel):
    """The ordered steps a result names, first the one that matters most."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    steps: tuple[NextStep, ...] = Field(min_length=1)


def _value(value: float, unit: str | None) -> str:
    return f"{value:.4g} {unit}".strip() if unit else f"{value:.4g}"


def next_steps(
    card: Scorecard, *, remedies: Sequence[str] = (), tool: str = "run_validation"
) -> tuple[NextStep, ...]:
    """The steps ``card`` calls for, by the precedence in this module's docstring.

    ``remedies`` are a refusal's own remedies, when the call that produced the result was
    refused; each becomes a step re-calling ``tool`` with that correction, ahead of
    everything else.
    """
    if not isinstance(card, Scorecard):
        raise _JourneyInputError(
            "card must be a Scorecard",
            remedies=(Remedy(action="replace", subject="card", source="the tool result"),),
        )
    if tool not in NEXT_STEP_TOOLS:
        raise _JourneyInputError(
            f"tool {tool!r} is not one a step may name ({list(NEXT_STEP_TOOLS)})",
            remedies=(Remedy(action="replace", subject="tool", source="the tool result"),),
        )
    remedies = each_one(remedies, str, named="remedies")
    steps = [NextStep(tool=tool, reason=f"the call was refused: {remedy}") for remedy in remedies]
    failed = [e for e in card.entries if e.status is CheckStatus.FAIL]
    for entry in failed:
        hint = entry.repair_hint
        if hint is not None and hint.corrective_value is not None:
            value = _value(hint.corrective_value, hint.unit)
            steps.append(NextStep(
                tool="run_validation", arguments={"set": hint.parameter, "to": value},
                reason=f"{entry.name} fails; its inverse solves {hint.parameter} = {value}",
            ))  # fmt: skip
    for entry in failed:
        hint = entry.repair_hint
        if hint is None or hint.corrective_value is None:
            move = (f"{hint.direction.value} {hint.parameter}" if hint is not None
                    else "revise the design")  # fmt: skip
            reason = f"{entry.name} fails; {move}, then re-validate"
            steps.append(NextStep(tool="run_validation", arguments={"change": move},
                                  reason=reason))  # fmt: skip
    unrun = [e for e in card.entries if e.status is CheckStatus.NOT_EVALUATED]
    for entry in unrun:
        if entry.name in _TIER_TOOLS and not entry.needs:
            steps.append(NextStep(tool=_TIER_TOOLS[entry.name],
                                  reason=f"the document demands {entry.name}, which did not "
                                         "run"))  # fmt: skip
    declared: dict[str, list[str]] = {}
    for entry in unrun:
        for need in entry.needs:
            declared.setdefault(need.declaration, []).append(entry.name)
    first = {}
    for entry in unrun:
        for need in entry.needs:
            first.setdefault(need.declaration, need.takes)
    for declaration, held in declared.items():
        steps.append(NextStep(
            tool="run_validation", arguments={"declare": declaration},
            reason=f"declare {declaration} ({first[declaration]}); it holds back "
                   f"{', '.join(dict.fromkeys(held))}",
        ))  # fmt: skip
    if not steps:
        silent = [e.name for e in unrun]
        reason = ("every check has a verdict; export the evidence for review" if not silent
                  else f"nothing here can supply what {', '.join(silent)} need; export the "
                       "evidence as a draft, with those checks marked not evaluated")  # fmt: skip
        steps.append(NextStep(tool="export_artifact", arguments={"format": "evidence_bundle"},
                              reason=reason))  # fmt: skip
    return tuple(steps)
