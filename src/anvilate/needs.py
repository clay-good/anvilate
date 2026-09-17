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

from pydantic import ConfigDict, Field

from ._models import ItemCollection, Named, StatableModel
from .scorecard import CheckStatus, Need, Scorecard

__all__ = [
    "NeedItem",
    "NeedsReport",
    "LEVERAGE_IS_NOT_IMPORTANCE",
    "needs_report",
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
