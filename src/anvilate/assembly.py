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
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict

from ._assembly_declarations import (
    AccessRequirement,
    Adjustment,
    AssemblyState,
    InsertionDirection,
    Inspection,
    Part,
    SwingRequirement,
    ToolEnvelope,
    _degrees,
)
from ._models import Named, StatableModel, each_one
from .derivation import DerivationAbsence, Underived
from .scorecard import CheckStatus, Direction, RepairHint, Scorecard, ScorecardEntry
from .spec import DesignSpec

if TYPE_CHECKING:
    pass

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
    "SwingRequirement",
    "screen_swing_arc",
    "Inspection",
    "screen_inspectability",
]


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
                    addresses=("an adjustment sealed away by the part closed over it",),
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
                    addresses=("an adjustment sealed away by the part closed over it",),
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
                    addresses=("an adjustment sealed away by the part closed over it",),
                    status=CheckStatus.PASS,
                    detail=(
                        f"{adjustment.feature} is reachable in {adjustment.performed_in} via "
                        f"{', '.join(adjustment.access)}"
                    ),
                    underived=absence,
                )
            )
    return tuple(entries)


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
                    # A slimmer tool sweeps a subset of the space a wider one does, so its
                    # body diameter is a lever that can only help; the part's own hint, when
                    # the part is what intrudes, stands.
                    "repair_hint": verdict.repair_hint
                    or (
                        RepairHint.directional(
                            "body_diameter",
                            direction=Direction.DECREASE,
                            provenance="subset of space a slimmer tool sweeps",
                        )
                        if verdict.status is CheckStatus.FAIL
                        else None
                    ),
                }
            )
        )
    return tuple(entries)


# The swing is sampled at every degree: a handle placed at each angle and checked against the
# neighbours. The arc reported is a count of free samples, so it is stated to this resolution.
_SWING_STEP_DEGREES = 1


def screen_swing_arc(
    spec: DesignSpec,
    part: Any,
    *,
    states: Sequence[AssemblyState],
    bodies: Mapping[str, Any],
    requirement: SwingRequirement,
) -> ScorecardEntry:
    """Whether a wrench can turn through the arc it needs, in the state it is used in.

    The handle is placed at every degree around the feature's axis on ``face`` and checked
    for a common volume with each neighbour the state has installed (the part itself is
    what the wrench turns on, so it is not an obstruction). The largest run of free
    placements, wrapping round through 360°, is the arc achieved, reported to 1° and
    compared with the arc required; a shortfall names the bodies that bound it. There is no
    closed form for an arbitrary obstruction, so this samples the declared geometry and says
    so. States, missing geometry and an unknown state are treated as by
    :func:`screen_tool_access`.
    """
    from .keepouts import _kernel

    b = _kernel()
    if not isinstance(requirement, SwingRequirement):
        raise ValueError(f"requirement must be a SwingRequirement; got {requirement!r}")
    states = each_one(states, AssemblyState, named="states")
    order = [state.name for state in states]
    name = f"swing arc: {requirement.feature}" + (
        f" in {requirement.performed_in}" if requirement.performed_in else ""
    )
    if requirement.performed_in is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=f"the wrench on {requirement.feature} states no assembly state it is used in",
        )
    if requirement.performed_in not in order:
        raise ValueError(
            f"the swing on {requirement.feature} names the state '{requirement.performed_in}', "
            f"which the build does not define; its states are {order}"
        )
    installed = [
        installed_part
        for state in states[: order.index(requirement.performed_in) + 1]
        for installed_part in state.installs
    ]
    missing = [label for label in installed if label not in bodies]
    if missing:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"in {requirement.performed_in}, {', '.join(missing)} installed with no geometry "
                "given, and a swing is not measured against an assembly with a part missing"
            ),
        )
    faces = part.faces.get(str(requirement.face))
    if not faces:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"'{requirement.face}' is not a face this build tags; it tags {sorted(part.faces)}"
            ),
        )
    face = faces[0]
    centre = face.center()
    outward = face.normal_at(centre)
    mm = lambda value: value.to("mm").magnitude  # noqa: E731 - three uses, one line each
    plane = b.Plane(origin=centre + outward * mm(requirement.height), z_dir=outward)
    handle = b.Box(
        mm(requirement.handle_length),
        mm(requirement.handle_width),
        mm(requirement.handle_thickness),
        align=(b.Align.MIN, b.Align.CENTER, b.Align.CENTER),
    )
    neighbours = {label: bodies[label] for label in installed}
    free, blockers = [], {}
    for angle in range(0, 360, _SWING_STEP_DEGREES):
        placed = plane.location * b.Rot(0, 0, angle) * handle
        hit = [
            label
            for label, solid in neighbours.items()
            if (common := solid & placed) is not None and float(common.volume) > 1e-6
        ]
        free.append(not hit)
        blockers[angle] = hit
    required = _degrees(requirement.required_arc, "required_arc")
    if all(free):
        achieved, bounded_by = 360, []
    elif not any(free):
        achieved, bounded_by = 0, sorted({label for hit in blockers.values() for label in hit})
    else:
        start = free.index(False)  # rotate so the scan begins at a blocked sample
        rolled = free[start:] + free[:start]
        best = run = 0
        for is_free in rolled:
            run = run + 1 if is_free else 0
            best = max(best, run)
        achieved = best * _SWING_STEP_DEGREES
        bounded_by = sorted({label for hit in blockers.values() for label in hit})
    context = (
        f"in {requirement.performed_in}: a {mm(requirement.handle_length):g} mm handle on "
        f"{requirement.feature} swings {achieved}° free (sampled every "
        f"{_SWING_STEP_DEGREES}°) against {required:g}° required ({requirement.source})"
    )
    passes = achieved >= required
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if passes else CheckStatus.FAIL,
        detail=context + ("" if passes else f"; bounded by {', '.join(bounded_by)}"),
        # A shorter handle sweeps a subset of a longer one's disc, so it can only free arc.
        repair_hint=(
            None
            if passes
            else RepairHint.directional(
                "handle_length",
                direction=Direction.DECREASE,
                provenance="subset of the disc a shorter handle sweeps",
            )
        ),
        underived=Underived(
            kind=DerivationAbsence.NUMERIC_RESULT,
            reason="a B-Rep common-volume test of the handle at each sampled angle",
        ),
        addresses=("a fastener no tool reaches in the state it is driven",),
    )


# Why an inspectability finding carries no worked calculation, stated once.
_ROUTE_CHECKED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="the route checked against the parts each state has installed",
)


def screen_inspectability(
    states: Sequence[AssemblyState],
    parts: Sequence[Part],
    inspections: Sequence[Inspection],
) -> tuple[ScorecardEntry, ...]:
    """Whether each toleranced dimension can be measured in some state the build passes through.

    A dimension is measurable in a state when no part installed by then occupies a feature
    its instrument's route passes through. One measurable in no state fails, naming the
    dimension and every state examined: a tolerance nobody can verify on the built article is
    a drawing note, not a control, whatever the dimensional screens say about it. One with
    no route declared is not evaluated. A summary states how many dimensions and states were
    examined, so a clean result is distinguishable from an unrun one.
    """
    states = each_one(states, AssemblyState, named="states")
    parts = each_one(parts, Part, named="parts")
    inspections = each_one(inspections, Inspection, named="inspections")
    by_name = {part.name: part for part in parts}
    order = [state.name for state in states]
    entries = []
    unmeasurable = 0
    for inspection in inspections:
        name = f"inspectability: {inspection.dimension}"
        if not inspection.access:
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"{inspection.dimension} by {inspection.method} declares no route for "
                        "the instrument, and an undeclared route is not a clear one"
                    ),
                )
            )
            continue
        measurable, installed = [], []
        for state in states:
            installed.extend(state.installs)
            blocked = [
                part
                for part in installed
                if part in by_name
                and any(feature in by_name[part].occupies for feature in inspection.access)
            ]
            if not blocked:
                measurable.append(state.name)
        if measurable:
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.PASS,
                    detail=(
                        f"{inspection.dimension} is measurable by {inspection.method} in "
                        f"{', '.join(measurable)}, of {len(order)} states examined"
                    ),
                    underived=_ROUTE_CHECKED,
                    addresses=("a tolerance nobody can measure on the built article",),
                )
            )
        else:
            unmeasurable += 1
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.FAIL,
                    detail=(
                        f"{inspection.dimension} cannot be measured by {inspection.method} in "
                        f"any of the {len(order)} states examined ({', '.join(order)}): its "
                        "route is occupied in every one, so the tolerance is a drawing note "
                        "rather than a control"
                    ),
                    underived=_ROUTE_CHECKED,
                    addresses=("a tolerance nobody can measure on the built article",),
                )
            )
    entries.insert(
        0,
        ScorecardEntry(
            name="inspectability",
            status=Scorecard(entries=tuple(entries)).status
            if entries
            else CheckStatus.NOT_EVALUATED,
            detail=(
                f"{len(inspections)} toleranced dimension{'s' if len(inspections) != 1 else ''} "
                f"examined across {len(order)} state{'s' if len(order) != 1 else ''}; "
                f"{unmeasurable} measurable in none"
            ),
            underived=Underived(
                kind=DerivationAbsence.LOOKUP,
                reason="the governing value of the per-dimension findings below",
            ),
        ),
    )
    return tuple(entries)
