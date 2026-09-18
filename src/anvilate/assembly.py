"""Assembly order: can the parts go in, and in what order.

A part that fits in the finished assembly may still have no way in. It is inserted along a
direction, and on the way it sweeps through space that another part may already occupy. If
that part went in first, this one is blocked. Put every such relation down and the question
is a graph: a valid assembly order is a topological order of the "must go in before"
relation, and when none exists the parts that block one another form a cycle — every member
of which is named, because the finding is only actionable when the engineer sees which parts
compete.

Nothing here reads geometry. A :class:`Part` declares its insertion direction, the features it
occupies once installed, and the features its insertion sweeps through, and the order is
computed from those declarations — so the verdict moves when the declaration does, and a part
with no declared insertion direction is ``not_evaluated`` rather than treated as insertable
from anywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import ConfigDict, model_validator

from ._models import Named, StatableModel, each_one
from .derivation import DerivationAbsence, Underived
from .scorecard import CheckStatus, ScorecardEntry

__all__ = [
    "InsertionDirection",
    "Part",
    "Blocking",
    "AssemblyOrder",
    "assembly_order",
]


class InsertionDirection(StrEnum):
    """The axis and sense a part travels along on its way into the assembly."""

    PLUS_X = "+x"
    MINUS_X = "-x"
    PLUS_Y = "+y"
    MINUS_Y = "-y"
    PLUS_Z = "+z"
    MINUS_Z = "-z"


class Part(StatableModel):
    """One part: how it goes in, what it takes up, and what it passes through on the way."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    insertion: InsertionDirection | None = None
    occupies: tuple[Named, ...] = ()
    sweeps: tuple[Named, ...] = ()

    @model_validator(mode="after")
    def _distinct(self) -> Part:
        for field, values in (("occupies", self.occupies), ("sweeps", self.sweeps)):
            if len(set(values)) != len(values):
                raise ValueError(f"part '{self.name}' names one feature twice in {field}")
        return self

    def __str__(self) -> str:
        how = f"inserted {self.insertion.value}" if self.insertion else "no insertion direction"
        return f"{self.name} ({how})"


class Blocking(StatableModel):
    """``blocked`` must go in before ``by``, because ``by`` occupies what ``blocked`` sweeps."""

    model_config = ConfigDict(frozen=True)

    blocked: Named
    by: Named
    feature: Named

    def __str__(self) -> str:
        return f"{self.blocked} sweeps {self.feature}, which {self.by} occupies"


class AssemblyOrder(StatableModel):
    """The order the parts can go in, or what stops every order."""

    model_config = ConfigDict(frozen=True)

    parts: tuple[Part, ...]
    blockings: tuple[Blocking, ...] = ()
    order: tuple[Named, ...] = ()
    cycles: tuple[tuple[Named, ...], ...] = ()
    interferences: tuple[tuple[Named, Named, Named], ...] = ()

    @property
    def undirected(self) -> tuple[Named, ...]:
        """Parts that declare no insertion direction, which nothing can be said about."""
        return tuple(part.name for part in self.parts if part.insertion is None)

    @property
    def feasible(self) -> bool:
        return bool(self.order) and not self.cycles and not self.interferences

    def entry(self) -> ScorecardEntry:
        """The order as one check: PASS with the order, FAIL naming what blocks it."""
        name = "assembly order"
        absence = Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "an ordering of declared insertion paths against declared occupied features; "
                "there is no arithmetic between two numbers to substitute"
            ),
        )
        if self.undirected:
            verb = "declares" if len(self.undirected) == 1 else "declare"
            return ScorecardEntry(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"not evaluated — {', '.join(self.undirected)} {verb} no insertion "
                    "direction, and a part is never treated as insertable from anywhere"
                ),
            )
        findings = []
        for first, second, feature in self.interferences:
            findings.append(f"{first} and {second} both occupy {feature}")
        for cycle in self.cycles:
            members = set(cycle)
            conflicts = "; ".join(
                str(b) for b in self.blockings if b.blocked in members and b.by in members
            )
            findings.append(
                f"no order exists for {', '.join(cycle)}: each must go in before another "
                f"({conflicts})"
            )
        if findings:
            return ScorecardEntry(
                name=name,
                status=CheckStatus.FAIL,
                detail="; ".join(findings),
                underived=absence,
            )
        return ScorecardEntry(
            name=name,
            status=CheckStatus.PASS,
            detail=f"a valid order exists: {' -> '.join(self.order)}",
            underived=absence,
        )

    def __str__(self) -> str:
        return str(self.entry())


def assembly_order(parts: Sequence[Part]) -> AssemblyOrder:
    """Find an order the ``parts`` can be inserted in, or name what prevents every order.

    A part must go in before any part occupying a feature its insertion sweeps. The order
    returned respects every such relation and is otherwise the declaration order, so the same
    declaration always yields the same order. Parts that block one another are returned as
    cycles, every member named; two parts occupying one feature are an interference, which no
    order resolves.
    """
    parts = each_one(parts, Part, named="parts")
    names = [part.name for part in parts]
    if len(set(names)) != len(names):
        doubled = sorted({n for n in names if names.count(n) > 1})
        raise ValueError(f"two parts share a name: {doubled}; an order of them is ambiguous")
    owner: dict[str, str] = {}
    interferences = []
    for part in parts:
        for feature in part.occupies:
            if feature in owner:
                interferences.append((owner[feature], part.name, feature))
            else:
                owner[feature] = part.name
    blockings = tuple(
        Blocking(blocked=part.name, by=owner[feature], feature=feature)
        for part in parts
        for feature in part.sweeps
        if feature in owner and owner[feature] != part.name
    )
    before = {name: {b.by for b in blockings if b.blocked == name} for name in names}
    # "blocked must precede by": an edge blocked -> by. Kahn's algorithm, taking the first
    # ready part in declaration order each time, so the order is deterministic.
    indegree = {name: sum(1 for b in blockings if b.by == name) for name in names}
    remaining = list(names)
    order: list[str] = []
    while True:
        ready = [name for name in remaining if indegree[name] == 0]
        if not ready:
            break
        chosen = ready[0]
        order.append(chosen)
        remaining.remove(chosen)
        for successor in before[chosen]:
            indegree[successor] -= 1
    cycles = _cycles(remaining, before) if remaining else ()
    return AssemblyOrder(
        parts=parts,
        blockings=blockings,
        order=tuple(order) if not remaining else (),
        cycles=cycles,
        interferences=tuple(interferences),
    )


def _cycles(names: list[str], edges: dict[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    """Every strongly connected group of mutually blocking parts, members in declaration order."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[tuple[str, ...]] = []
    counter = [0]

    def visit(name: str) -> None:
        index[name] = low[name] = counter[0]
        counter[0] += 1
        stack.append(name)
        on_stack.add(name)
        for successor in sorted(edges[name] & set(names)):
            if successor not in index:
                visit(successor)
                low[name] = min(low[name], low[successor])
            elif successor in on_stack:
                low[name] = min(low[name], index[successor])
        if low[name] == index[name]:
            component = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == name:
                    break
            if len(component) > 1:
                found.append(tuple(n for n in names if n in component))

    for name in names:
        if name not in index:
            visit(name)
    return tuple(sorted(found, key=lambda cycle: names.index(cycle[0])))
