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

from collections.abc import Sequence

from pydantic import ConfigDict, Field, model_validator

from ._models import ItemCollection, Named, StatableModel, each_one

__all__ = [
    "Output",
    "Consumes",
    "CheckNode",
    "DependencyGraph",
    "find_cycles",
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
