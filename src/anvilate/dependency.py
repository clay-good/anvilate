"""The check dependency graph: what a check consumes, declared, ordered, and cycle-free.

A shock screen that reads the fundamental frequency a modal screen computed has a
dependency, and until it is written down it is an implementation detail: nothing can order
the two, nothing can propagate a gap from the first to the second, and nothing can tell a
reader that the second number rests on the first.

A :class:`CheckNode` declares what a check *produces* and what it *consumes*, each with a
dimension. A :class:`DependencyGraph` holds the nodes and refuses, at construction:

- a consumption of a check the graph does not carry, or of an output that check does not
  produce — named, rather than discovered when a spec first exercises the chain;
- a dimension disagreement between the produced output and the consuming parameter;
- a cycle, naming **every** member of it rather than the edge that happened to close it,
  because the edge that closed it is an artifact of declaration order and the cycle is not.

:meth:`DependencyGraph.order` returns the evaluation order: consistent with every declared
consumption, and stable — checks with no ordering relation between them keep their
declaration order, so the same graph evaluates the same way on every run.

Nothing here runs a check. This is the shape of the chain, which is what has to be right
before anything is evaluated along it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from ._models import EMPTY_MAP, FrozenMap, ItemCollection, Named, StatableModel, each_one
from .margin import MarginEntry
from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .units import Quantity

__all__ = [
    "Output",
    "Consumes",
    "CheckNode",
    "DependencyGraph",
    "find_cycles",
    "ChainResult",
    "ChainRun",
    "run_chain",
]


class Output(StatableModel):
    """One value a check produces, and the dimension it is in.

    ``dimension`` is written the way the unit layer writes one — ``[length]``, ``[time]``,
    ``dimensionless`` — and is compared textually against the consuming parameter's. A
    produced value with no dimension is not describable here: what a downstream check can
    rely on is a quantity, and a quantity has a dimension.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    dimension: Named


class Consumes(StatableModel):
    """One upstream output a check reads, and the dimension its own parameter takes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    upstream: Named
    output: Named
    parameter: Named
    dimension: Named


class CheckNode(StatableModel):
    """One check in the graph: its id, what it produces, and what it consumes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    produces: tuple[Output, ...] = ()
    consumes: tuple[Consumes, ...] = ()

    @model_validator(mode="after")
    def _well_formed(self) -> CheckNode:
        produced = [output.name for output in self.produces]
        if len(set(produced)) != len(produced):
            raise ValueError(f"check '{self.id}' produces one output twice: {sorted(produced)}")
        parameters = [consumed.parameter for consumed in self.consumes]
        if len(set(parameters)) != len(parameters):
            raise ValueError(
                f"check '{self.id}' binds one parameter twice: {sorted(parameters)}; a "
                "parameter fed from two upstream outputs is a question about which wins"
            )
        for consumed in self.consumes:
            if consumed.upstream == self.id:
                raise ValueError(
                    f"check '{self.id}' consumes its own output '{consumed.output}'; a check "
                    "cannot be upstream of itself"
                )
        return self


class DependencyGraph(ItemCollection, StatableModel):
    """Every declared check and the edges between them, refused unless it is a DAG."""

    model_config = ConfigDict(frozen=True)

    nodes: tuple[CheckNode, ...] = Field(default=())

    @model_validator(mode="after")
    def _resolvable_and_acyclic(self) -> DependencyGraph:
        ids = [node.id for node in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError(f"the graph carries one check id twice: {sorted(ids)}")
        by_id = {node.id: node for node in self.nodes}
        for node in self.nodes:
            for consumed in node.consumes:
                upstream = by_id.get(consumed.upstream)
                if upstream is None:
                    raise ValueError(
                        f"check '{node.id}' consumes '{consumed.output}' from "
                        f"'{consumed.upstream}', which this graph does not carry; a "
                        "dependency on a check nobody registered cannot be ordered or "
                        "propagated along"
                    )
                produced = {output.name: output for output in upstream.produces}
                output = produced.get(consumed.output)
                if output is None:
                    raise ValueError(
                        f"check '{node.id}' consumes '{consumed.output}' from "
                        f"'{consumed.upstream}', which produces "
                        f"{sorted(produced) or 'nothing'}"
                    )
                if output.dimension != consumed.dimension:
                    raise ValueError(
                        f"check '{node.id}' takes '{consumed.parameter}' in "
                        f"{consumed.dimension} and '{consumed.upstream}.{consumed.output}' is "
                        f"{output.dimension}; a chain across two dimensions is caught here, "
                        "at registration, rather than on the first spec that runs it"
                    )
        cycles = find_cycles(self.nodes)
        if cycles:
            described = "; ".join(" -> ".join(cycle) for cycle in cycles)
            raise ValueError(
                f"declared consumptions form {len(cycles)} cycle(s): {described}. Every member "
                "is named because the edge that closed the loop is an artifact of declaration "
                "order, and breaking a cycle by choosing a starting point would make the "
                "result depend on it"
            )
        return self

    def order(self) -> tuple[str, ...]:
        """The evaluation order: dependencies first, declaration order among equals.

        Kahn's algorithm over a queue kept in declaration order, so two checks with no
        ordering relation between them come out in the order the graph declares them. A run
        that reordered them would produce a different recorded order for the same document,
        and the bundle records this.
        """
        by_id = {node.id: node for node in self.nodes}
        waiting_on = {
            node.id: {consumed.upstream for consumed in node.consumes} for node in self.nodes
        }
        ordered: list[str] = []
        remaining = [node.id for node in self.nodes]
        while remaining:
            ready = [name for name in remaining if not waiting_on[name] - set(ordered)]
            # The graph is acyclic by construction, so something is always ready; `ready`
            # keeps `remaining`'s order, which is the declaration order.
            assert ready, "an acyclic graph always has a ready node"
            ordered.extend(ready)
            remaining = [name for name in remaining if name not in set(ready)]
        assert set(ordered) == set(by_id)
        return tuple(ordered)

    def downstream_of(self, check: str) -> tuple[str, ...]:
        """Every check that reads ``check``, directly or through others, in evaluation order.

        The transitive closure rather than the direct consumers: a gap in one check reaches
        everything beyond it, and a propagation that stopped at the first hop would leave a
        number resting on a value nobody produced.
        """
        if check not in {node.id for node in self.nodes}:
            raise ValueError(f"this graph carries no check '{check}'")
        reached: set[str] = set()
        frontier = {check}
        while frontier:
            frontier = {
                node.id
                for node in self.nodes
                if node.id not in reached
                and any(consumed.upstream in frontier for consumed in node.consumes)
            }
            reached |= frontier
        return tuple(name for name in self.order() if name in reached)

    def upstream_of(self, check: str) -> tuple[str, ...]:
        """Every check ``check`` reads from, directly or through others, in evaluation order.

        The mirror of :meth:`downstream_of`, and the set whose conservatism a downstream
        result inherits: a factor applied to a temperature is still in force on the
        displacement computed from it.
        """
        by_id = {node.id: node for node in self.nodes}
        if check not in by_id:
            raise ValueError(f"this graph carries no check '{check}'")
        reached: set[str] = set()
        frontier = {check}
        while frontier:
            frontier = {
                consumed.upstream
                for name in frontier
                for consumed in by_id[name].consumes
                if consumed.upstream not in reached
            }
            reached |= frontier
        return tuple(name for name in self.order() if name in reached)

    def __str__(self) -> str:
        if not self.nodes:
            return "dependency graph: no checks declared"
        lines = [f"dependency graph: {len(self.nodes)} checks in order"]
        by_id = {node.id: node for node in self.nodes}
        for name in self.order():
            reads = ", ".join(
                f"{consumed.upstream}.{consumed.output} -> {consumed.parameter}"
                for consumed in by_id[name].consumes
            )
            lines.append(f"  {name}" + (f" [reads {reads}]" if reads else ""))
        return "\n".join(lines)


def find_cycles(nodes: Sequence[CheckNode]) -> tuple[tuple[str, ...], ...]:
    """Every cycle's full membership, by strongly connected components (Tarjan).

    A component of more than one check is a cycle, and every member of it is named. Found
    by components rather than by the back edge a depth-first walk happens to close on:
    naming that edge tells a reader which declaration was written last, not which checks
    are tangled.

    Public and separate from the graph, because a :class:`DependencyGraph` that exists is
    acyclic — its constructor refuses otherwise, and pydantic reports that refusal as a
    validation error. A caller assembling nodes can ask this first and get the cycles as
    data rather than as a message to parse.
    """
    # Through `each_one`, for the mistake this shape invites: a pydantic model iterates its
    # own (field, value) pairs, so ONE node passed where a sequence belongs would be read as
    # its parts and answered with `'str' object has no attribute 'id'`.
    by_id = {node.id: node for node in each_one(nodes, CheckNode, named="nodes")}
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[tuple[str, ...]] = []
    counter = 0

    def strongconnect(name: str) -> None:
        nonlocal counter
        index[name] = low[name] = counter
        counter += 1
        stack.append(name)
        on_stack.add(name)
        for consumed in by_id[name].consumes:
            upstream = consumed.upstream
            if upstream not in by_id:
                continue  # reported as an unresolvable consumption, not as a cycle
            if upstream not in index:
                strongconnect(upstream)
                low[name] = min(low[name], low[upstream])
            elif upstream in on_stack:
                low[name] = min(low[name], index[upstream])
        if low[name] == index[name]:
            component = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == name:
                    break
            if len(component) > 1:
                # In declaration order, and closed back to its first member, so the cycle
                # reads as the loop it is rather than as a set.
                ring = tuple(sorted(component, key=list(by_id).index))
                found.append((*ring, ring[0]))

    for name in by_id:
        if name not in index:
            strongconnect(name)
    return tuple(found)


class ChainResult(StatableModel):
    """One check's contribution to a chain run: its entry, its outputs, and its margins.

    ``outputs`` are the values downstream checks consume, keyed by the output name this node
    declared. ``margins`` are the conservatism this check applied; every downstream result
    inherits them, because a factor on a temperature is still in force on the displacement
    computed from it and a cumulative factor that stopped at the last link would understate
    the chain.
    """

    model_config = ConfigDict(frozen=True)

    check: Named
    entry: ScorecardEntry
    # `EMPTY_MAP`, not `dict`: a default_factory's value does not go through the
    # annotation's validator, so the empty default was a writable dict on a frozen model.
    outputs: FrozenMap[str, Quantity] = Field(default_factory=lambda: EMPTY_MAP)
    margins: tuple[MarginEntry, ...] = ()

    @model_validator(mode="after")
    def _a_result(self) -> ChainResult:
        if self.outputs and not self.entry.evaluated:
            raise ValueError(
                f"check '{self.check}' is {self.entry.status.value} and hands "
                f"{sorted(self.outputs)} downstream; a check that did not run produced no "
                "value, and passing one on is how a number nobody computed reaches a verdict"
            )
        return self


class ChainRun(StatableModel):
    """A whole chain evaluated: the realized order, each result, and what each inherited."""

    model_config = ConfigDict(frozen=True)

    graph: DependencyGraph
    results: tuple[ChainResult, ...]

    @property
    def order(self) -> tuple[str, ...]:
        """The order the checks actually ran in — recorded, not recomputed by a reader."""
        return tuple(result.check for result in self.results)

    def card(self) -> Scorecard:
        """The entries as a scorecard, in the realized evaluation order."""
        return Scorecard(entries=tuple(result.entry for result in self.results))

    def result(self, check: str) -> ChainResult:
        for result in self.results:
            if result.check == check:
                return result
        raise ValueError(f"this run carries no check '{check}'")

    def inherited_margins(self, check: str) -> tuple[MarginEntry, ...]:
        """Every margin in force on ``check``: its own and every upstream one, upstream first.

        Read off the graph rather than off position in the run: a check that happened to run
        earlier is not upstream of this one, and inheriting its conservatism would attribute
        a factor to a chain it is not in.
        """
        self.result(check)  # refuses an unknown check by name
        in_force = (*self.graph.upstream_of(check), check)
        return tuple(margin for name in in_force for margin in self.result(name).margins)

    def stale_after(self, changed: str) -> tuple[str, ...]:
        """What a change to ``changed`` invalidates: itself and its transitive consumers.

        The whole closure, never the first hop: recomputing the immediate consumer and
        leaving its consumers on the old value is a card mixing two evaluations of one
        chain, which reads as current and is not.
        """
        return (changed, *self.graph.downstream_of(changed))

    def __str__(self) -> str:
        lines = [f"chain of {len(self.results)} checks, in evaluation order"]
        lines += [f"  {result.entry.status.value:<14} {result.check}" for result in self.results]
        return "\n".join(lines)


def run_chain(
    graph: DependencyGraph,
    run_check: Callable[[str, Mapping[str, Quantity]], ChainResult],
) -> ChainRun:
    """Evaluate every check in dependency order, feeding each the inputs it declared.

    ``run_check`` is called with a check id and the mapping of its declared parameters to
    the upstream values they were bound to, and returns that check's :class:`ChainResult`.
    It is only called for a check whose inputs are all present.

    **A check downstream of one that did not run is NOT_EVALUATED, naming what it waited
    on, and is never called.** That is the whole point of ordering the chain: a screen given
    a default in place of a missing upstream value would compute a verdict from a number
    nobody produced, which is the silent green this library exists to refuse. The refusal
    names the immediate upstream and the check at the head of the chain, so a reader is sent
    to the one thing to fix rather than to the last link that broke.
    """
    by_id = {node.id: node for node in graph.nodes}
    results: list[ChainResult] = []
    produced: dict[str, dict[str, Quantity]] = {}
    blocked: dict[str, str] = {}  # check -> the check at the head of its broken chain
    for name in graph.order():
        node = by_id[name]
        upstream_gap = next(
            (
                consumed
                for consumed in node.consumes
                if consumed.upstream in blocked
                or consumed.output not in produced.get(consumed.upstream, {})
            ),
            None,
        )
        if upstream_gap is not None:
            head = blocked.get(upstream_gap.upstream, upstream_gap.upstream)
            blocked[name] = head
            through = (
                "" if head == upstream_gap.upstream else f", which is waiting on '{head}' in turn"
            )
            results.append(
                ChainResult(
                    check=name,
                    entry=ScorecardEntry(
                        name=name,
                        status=CheckStatus.NOT_EVALUATED,
                        detail=(
                            f"this check takes '{upstream_gap.parameter}' from "
                            f"'{upstream_gap.upstream}.{upstream_gap.output}', which was not "
                            f"produced{through}. A value nobody computed is not a value to "
                            "screen against"
                        ),
                    ),
                )
            )
            continue
        inputs = {
            consumed.parameter: produced[consumed.upstream][consumed.output]
            for consumed in node.consumes
        }
        result = run_check(name, inputs)
        if result.check != name:
            raise ValueError(
                f"run_check was asked for '{name}' and returned a result for "
                f"'{result.check}'; a chain assembled from mislabelled results would record "
                "an order it did not run in"
            )
        if not result.entry.evaluated:
            blocked[name] = name
        produced[name] = dict(result.outputs)
        results.append(result)
    return ChainRun(graph=graph, results=tuple(results))
