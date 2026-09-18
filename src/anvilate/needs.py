"""What the build needs next: every missing declaration in one report, ordered by leverage.

Every refusal in this library is right on its own — a screen that invents a value it was not
given is the silent green everything here exists to prevent. The cumulative effect is a first
run that answers with a wall of "not evaluated" and no obvious next move, which is the same
friction from the other side: rigor nobody can drive is not rigor.

So a check that could not run says what it needed. A :class:`~anvilate.scorecard.Need` — declared
beside the entry that carries it, so a check states its own gap — names the declaration, the
dimension and the units it takes, and where an acceptable value may come from.
:func:`needs_report` collects them off a scorecard and merges the ones naming the same
declaration, so eleven not-evaluated entries arising from four missing declarations are four
items, each naming the entries it would resolve.

The order is **leverage** — how many screens an item would unblock — and the count is printed
beside it so the ordering is checkable rather than asserted. Items unblocking equally many
screens are reported as tied. Leverage is not importance, risk or severity: a declaration
that unblocks one safety-governing check matters more than one unblocking six secondary
screens, and nothing here can tell which is which. Every rendering says so.

Nothing in this module infers a value, weakens a refusal, or changes a verdict.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field

from ._models import ItemCollection, Named, StatableModel
from .scorecard import CheckStatus, Need, Scorecard

__all__ = [
    "NeedItem",
    "DepthChange",
    "NeedsReport",
    "LEVERAGE_IS_NOT_IMPORTANCE",
    "needs_report",
    "deepening",
    "ScreenState",
    "ApplicableScreen",
    "WhatApplies",
    "what_applies",
]

#: Printed wherever the report is rendered. The ordering is a measure of how much work a
#: declaration unblocks, and reading it as a priority list is the one misreading that would
#: do harm — it would send an engineer to the item with the most entries behind it rather
#: than to the one their part fails on.
LEVERAGE_IS_NOT_IMPORTANCE = (
    "ordered by how many screens each item unblocks, which is leverage and not importance: "
    "a declaration unblocking one safety-governing check can matter more than one unblocking "
    "six secondary screens"
)


class NeedItem(StatableModel):
    """One need and the checks it would let run."""

    model_config = ConfigDict(frozen=True)

    need: Need
    unblocks: tuple[Named, ...] = Field(min_length=1)

    @property
    def leverage(self) -> int:
        """How many screens this item would unblock — the number the order follows."""
        return len(self.unblocks)

    def __str__(self) -> str:
        return f"{self.need} — unblocks {self.leverage}: {', '.join(self.unblocks)}"


class NeedsReport(ItemCollection, StatableModel):
    """Every missing declaration on one card, ordered by leverage."""

    model_config = ConfigDict(frozen=True)

    items: tuple[NeedItem, ...] = ()

    def tied(self) -> tuple[tuple[NeedItem, ...], ...]:
        """The items grouped by leverage, highest first — a group of two or more is a tie."""
        groups: dict[int, list[NeedItem]] = {}
        for item in self.items:
            groups.setdefault(item.leverage, []).append(item)
        return tuple(tuple(groups[key]) for key in sorted(groups, reverse=True))

    def __str__(self) -> str:
        if not self.items:
            return "needs: every declaration the screens reached for was supplied"
        lines = [f"needs {len(self.items)}: {LEVERAGE_IS_NOT_IMPORTANCE}"]
        for group in self.tied():
            tie = " (tied)" if len(group) > 1 else ""
            lines.extend(f"  {item}{tie}" for item in group)
        return "\n".join(lines)


def needs_report(card: Scorecard) -> NeedsReport:
    """The needs the card's unevaluated checks declared, merged by declaration.

    Two checks waiting on the same declaration are one item naming both, because the
    engineer's next action is one edit. Entries are read in card order, so the ordering
    within a tie is the order the screens ran and never an accident of a dictionary.

    A need on a check that *ran* is a contradiction — the check had what it needed — and
    :class:`~anvilate.scorecard.ScorecardEntry` refuses it at construction. This function
    therefore reads the unevaluated entries and does not have to judge.
    """
    merged: dict[str, tuple[Need, list[str]]] = {}
    for entry in card.entries:
        if entry.status is not CheckStatus.NOT_EVALUATED:
            continue
        for need in entry.needs:
            existing = merged.get(need.declaration)
            if existing is None:
                merged[need.declaration] = (need, [entry.name])
            elif entry.name not in existing[1]:
                existing[1].append(entry.name)
    items = [NeedItem(need=need, unblocks=tuple(names)) for need, names in merged.values()]
    items.sort(key=lambda item: -item.leverage)
    return NeedsReport(items=tuple(items))


class DepthChange(StatableModel):
    """What raising a document's screening depth would run, and what it would then need.

    Both halves, because a depth raise has a return and a price: the checks it newly runs,
    and the declarations those checks ask for that the shallower screen never mentioned.
    Reporting only the second is how a deeper screen reads as a new wall; reporting only the
    first is how it reads as free.
    """

    model_config = ConfigDict(frozen=True)

    from_depth: Named
    to_depth: Named
    newly_run: tuple[Named, ...] = ()
    newly_required: tuple[NeedItem, ...] = ()

    def __str__(self) -> str:
        if not self.newly_run and not self.newly_required:
            return (
                f"{self.from_depth} -> {self.to_depth}: no check this document supports runs "
                "deeper than it is already screened"
            )
        lines = [
            f"{self.from_depth} -> {self.to_depth}: runs {len(self.newly_run)} more "
            f"check(s), needs {len(self.newly_required)} more declaration(s)"
        ]
        lines += [f"  runs: {name}" for name in self.newly_run]
        lines += [f"  needs: {item}" for item in self.newly_required]
        return "\n".join(lines)


def deepening(spec: Any, to_depth: Any) -> DepthChange:
    """Screen ``spec`` again at ``to_depth`` and report what the raise costs and returns.

    A pure comparison of two screens of the same document: nothing is mutated, and the
    deeper card is thrown away once its names and needs are read. ``to_depth`` must be
    deeper than the document's own declaration — a raise to the depth already declared, or
    to a shallower one, is refused rather than reported as a change of nothing.

    Imported locally: this module describes a card, and the screen that builds one is a
    layer above it. Reaching up at call time keeps that direction one-way.
    """
    from .screening import DEPTH_ORDER, screen_spec

    declared = spec.acceptance.depth
    if DEPTH_ORDER.index(to_depth) <= DEPTH_ORDER.index(declared):
        raise ValueError(
            f"this document is screened at {declared.value} and {to_depth.value} is not "
            f"deeper than it; the depths from shallowest are "
            f"{', '.join(depth.value for depth in DEPTH_ORDER)}"
        )
    shallow = screen_spec(spec)
    deeper = screen_spec(
        spec.model_copy(
            update={"acceptance": spec.acceptance.model_copy(update={"depth": to_depth})}
        )
    )
    ran_before = {entry.name for entry in shallow.entries if entry.evaluated}
    newly_run = tuple(
        entry.name for entry in deeper.entries if entry.evaluated and entry.name not in ran_before
    )
    asked_before = {item.need.declaration for item in needs_report(shallow).items}
    newly_required = tuple(
        item for item in needs_report(deeper).items if item.need.declaration not in asked_before
    )
    return DepthChange(
        from_depth=declared.value,
        to_depth=to_depth.value,
        newly_run=newly_run,
        newly_required=newly_required,
    )


class ScreenState(StrEnum):
    """Where one screen on a card stands for this document."""

    RUNS_NOW = "runs_now"
    NEEDS = "needs"
    DEFERRED = "deferred"


class ApplicableScreen(StatableModel):
    """One screen the document reaches, and what, if anything, it waits on."""

    model_config = ConfigDict(frozen=True)

    name: Named
    state: ScreenState
    needs: tuple[Named, ...] = ()
    reason: str = ""

    def __str__(self) -> str:
        if self.state is ScreenState.RUNS_NOW:
            return f"{self.name}: runs now"
        if self.state is ScreenState.DEFERRED:
            return f"{self.name}: deferred by the declared screening depth"
        waiting = ", ".join(self.needs) if self.needs else self.reason
        return f"{self.name}: needs {waiting}"


class WhatApplies(ItemCollection, StatableModel):
    """Every screen that applies to a document: what runs now and what the rest need."""

    model_config = ConfigDict(frozen=True)

    screens: tuple[ApplicableScreen, ...] = ()

    def of(self, state: ScreenState) -> tuple[ApplicableScreen, ...]:
        return tuple(screen for screen in self.screens if screen.state is state)

    def __str__(self) -> str:
        counts = ", ".join(
            f"{len(self.of(state))} {state.value.replace('_', ' ')}" for state in ScreenState
        )
        return "\n".join(
            [f"{len(self.screens)} screens apply ({counts})"] + [f"  {s}" for s in self.screens]
        )


def what_applies(card: Scorecard) -> WhatApplies:
    """What applies to the document behind ``card``: each screen, and whether it can run.

    A screen that ran runs now. One the document deferred by depth is deferred. One that
    could not run names what it needs — the declarations its typed needs list, and failing
    those the reason the check itself gives — so a partly declared spec answers "what would
    it take" rather than only "what failed".
    """
    screens = []
    for entry in card.entries:
        if entry.status is CheckStatus.OUT_OF_DEPTH:
            state = ScreenState.DEFERRED
        elif entry.status is CheckStatus.NOT_EVALUATED:
            state = ScreenState.NEEDS
        else:
            state = ScreenState.RUNS_NOW
        screens.append(
            ApplicableScreen(
                name=entry.name,
                state=state,
                needs=tuple(dict.fromkeys(need.declaration for need in entry.needs))
                if state is ScreenState.NEEDS
                else (),
                reason=entry.detail if state is ScreenState.NEEDS and not entry.needs else "",
            )
        )
    return WhatApplies(screens=tuple(screens))
