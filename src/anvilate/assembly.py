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

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, model_validator

from ._models import Named, Provenance, StatableModel, each_one
from .derivation import DerivationAbsence, Underived
from .scorecard import CheckStatus, ScorecardEntry
from .spec import DesignSpec
from .units import Quantity

if TYPE_CHECKING:
    from .spec import Keepout

__all__ = [
    "InsertionDirection",
    "Part",
    "Blocking",
    "AssemblyOrder",
    "assembly_order",
    "AssemblyState",
    "Adjustment",
    "screen_adjustment_access",
    "ToolEnvelope",
    "AccessRequirement",
    "screen_tool_access",
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


class AssemblyState(StatableModel):
    """One state a build passes through, and the parts installed on reaching it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    installs: tuple[Named, ...] = ()

    def __str__(self) -> str:
        parts = ", ".join(self.installs) if self.installs else "nothing new"
        return f"{self.name}: installs {parts}"


class Adjustment(StatableModel):
    """Something done to a feature in a given state, and the route a tool takes to it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: Named
    performed_in: Named
    access: tuple[Named, ...] = ()

    def __str__(self) -> str:
        route = " via " + ", ".join(self.access) if self.access else " with no access route"
        return f"adjust {self.feature} in {self.performed_in}{route}"


def screen_adjustment_access(
    states: Sequence[AssemblyState],
    parts: Sequence[Part],
    adjustments: Sequence[Adjustment],
) -> tuple[ScorecardEntry, ...]:
    """Whether each ``adjustment`` can still be reached in the state it is performed in.

    ``states`` are the build's states in order; a part installed in one stays installed in
    every later one. An adjustment is blocked when a part installed by its state occupies a
    feature its access route passes through — the housing closed over the screw you set after
    closing it. Each finding names the adjustment, the state, the blocking part and the
    feature it occupies.

    An adjustment declared in a state the build does not define is refused by name, so access
    is never evaluated against a configuration nobody described; one with no access route is
    ``not_evaluated``, naming the missing route, because an undeclared route is not a clear
    one.
    """
    states = each_one(states, AssemblyState, named="states")
    parts = each_one(parts, Part, named="parts")
    adjustments = each_one(adjustments, Adjustment, named="adjustments")
    order = [state.name for state in states]
    if len(set(order)) != len(order):
        raise ValueError(f"two assembly states share a name: {order}")
    by_name = {part.name: part for part in parts}
    installed_in: dict[str, str] = {}
    for state in states:
        for part in state.installs:
            if part not in by_name:
                raise ValueError(
                    f"state '{state.name}' installs '{part}', which is no declared part"
                )
            if part in installed_in:
                raise ValueError(
                    f"'{part}' is installed in both '{installed_in[part]}' and '{state.name}'"
                )
            installed_in[part] = state.name
    entries = []
    for adjustment in adjustments:
        if adjustment.performed_in not in order:
            raise ValueError(
                f"{adjustment} names the state '{adjustment.performed_in}', which the build "
                f"does not define; its states are {order}"
            )
        name = f"access: {adjustment.feature} in {adjustment.performed_in}"
        if not adjustment.access:
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"not evaluated — adjusting {adjustment.feature} in "
                        f"{adjustment.performed_in} declares no access route: no port, window "
                        "or tool path, and an undeclared route is not a clear one"
                    ),
                )
            )
            continue
        reached = order[: order.index(adjustment.performed_in) + 1]
        blockers = sorted(
            (part, feature)
            for part, state in installed_in.items()
            if state in reached
            for feature in by_name[part].occupies
            if feature in adjustment.access
        )
        absence = Underived(
            kind=DerivationAbsence.LOOKUP,
            reason="declared access routes checked against the parts installed by that state",
        )
        if blockers:
            closed = "; ".join(
                f"{part} (installed in {installed_in[part]}) occupies {feature}"
                for part, feature in blockers
            )
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.FAIL,
                    detail=(
                        f"{adjustment.feature} cannot be reached in {adjustment.performed_in}: "
                        f"{closed}"
                    ),
                    underived=absence,
                )
            )
        else:
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.PASS,
                    detail=(
                        f"{adjustment.feature} is reachable in {adjustment.performed_in} via "
                        f"{', '.join(adjustment.access)}"
                    ),
                    underived=absence,
                )
            )
    return tuple(entries)


class ToolEnvelope(StatableModel):
    """The space a tool occupies while it works: the widest body along its reach.

    A socket, a hex key or a driver sweeps a cylinder from the fastener outward: the
    ``body_diameter`` is its widest section there and ``reach`` how far that section runs.
    No tool dimensions ship with the library; the numbers are the user's, from their tool
    catalogue or measured, and ``source`` records which, the same doctrine as a glass
    allowable (ISO 2936 and ISO 2725 state them, and neither is redistributable).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Named
    body_diameter: Quantity
    reach: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _an_envelope(self) -> ToolEnvelope:
        for label, value in (("body_diameter", self.body_diameter), ("reach", self.reach)):
            if not value.has_dimension("[length]"):
                raise ValueError(f"'{self.tool}': {label} must be a length; got {value}")
            if not value.to("mm").magnitude > 0:
                raise ValueError(f"'{self.tool}': {label} must be positive; got {value}")
        return self


class AccessRequirement(StatableModel):
    """A feature a tool must reach, from the face it approaches, and the clearance it needs.

    The tool's envelope is generated as a keepout standing in front of ``face``, the tagged
    face the feature sits on, out to the tool's reach, and it is checked by the same
    intrusion mechanism as any other keepout (:func:`anvilate.keepouts.screen_keepouts`),
    against the part and every neighbouring body. There is no second collision check.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: Named
    face: Named
    tool: ToolEnvelope
    clearance_margin: Quantity = Quantity(magnitude=0.0, unit="mm")
    # The assembly state the tool is used in: access is judged against the parts installed
    # by then, never against the bare part alone.
    performed_in: Named | None = None

    def keepout(self) -> Keepout:
        """The tool's working envelope as a cylinder keepout in front of the face."""
        from .spec import CylinderKeepout, Keepout

        return Keepout(
            tag=f"access {self.feature} by {self.tool.tool}",
            anchor=self.face,
            rule=CylinderKeepout(diameter=self.tool.body_diameter, height=self.tool.reach),
            clearance_margin=self.clearance_margin,
            reason=(
                f"{self.tool.tool} must reach {self.feature} from {self.face} ({self.tool.source})"
            ),
            owner="assembly access",
            offset=Quantity(magnitude=-self.tool.reach.to("mm").magnitude, unit="mm"),
        )


def screen_tool_access(
    spec: DesignSpec,
    part: Any,
    *,
    states: Sequence[AssemblyState],
    bodies: Mapping[str, Any],
    requirements: Sequence[AccessRequirement],
) -> tuple[ScorecardEntry, ...]:
    """Whether each tool reaches its feature in the assembly state it is used in.

    ``part`` is the built part the features sit on (a :class:`~anvilate.geometry.BuiltGeometry`)
    and ``bodies`` the solids of the other parts, by name. For each requirement the neighbours
    are the parts ``states`` has installed up to and including its ``performed_in`` state, so
    a screw driven before the cover goes on is judged without the cover and one driven after
    is judged against it. Each sweep is screened by :func:`anvilate.keepouts.screen_keepouts`;
    the entry names the feature, the tool, the state and the body that blocks it.

    A requirement with no state is not evaluated, naming what it needs: access on the bare
    part answers a question nobody asked. A state the build does not define is refused. An
    installed part with no solid in ``bodies`` is not evaluated, naming it, because leaving it
    out would measure against a configuration with a part missing.
    """
    from .keepouts import screen_keepouts

    states = each_one(states, AssemblyState, named="states")
    requirements = each_one(requirements, AccessRequirement, named="requirements")
    order = [state.name for state in states]
    entries = []
    for requirement in requirements:
        name = f"tool access: {requirement.feature} by {requirement.tool.tool}" + (
            f" in {requirement.performed_in}" if requirement.performed_in else ""
        )
        if requirement.performed_in is None:
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"{requirement.tool.tool} reaching {requirement.feature} states no "
                        "assembly state it is used in, so which parts are in the way is unknown"
                    ),
                )
            )
            continue
        if requirement.performed_in not in order:
            raise ValueError(
                f"the access to {requirement.feature} names the state "
                f"'{requirement.performed_in}', which the build does not define; its states "
                f"are {order}"
            )
        installed = [
            installed_part
            for state in states[: order.index(requirement.performed_in) + 1]
            for installed_part in state.installs
        ]
        missing = [name_ for name_ in installed if name_ not in bodies]
        if missing:
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"in {requirement.performed_in}, {', '.join(missing)} "
                        f"{'is' if len(missing) == 1 else 'are'} installed with no geometry "
                        "given, and access is not measured against an assembly with a part "
                        "missing"
                    ),
                )
            )
            continue
        screened, _ = screen_keepouts(
            spec,
            part,
            neighbours={name_: bodies[name_] for name_ in installed},
            keepouts=(requirement.keepout(),),
        )
        verdict = screened[1]
        entries.append(
            verdict.model_copy(
                update={
                    "name": name,
                    "detail": f"in {requirement.performed_in}: {verdict.detail}",
                    "addresses": ("a fastener no tool reaches in the state it is driven",),
                }
            )
        )
    return tuple(entries)
