# The check dependency graph

A shock screen that reads the fundamental frequency a modal screen computed has a
dependency on it. Until that is written down it is an implementation detail: nothing can
order the two, nothing can carry a gap in the first through to the second, and nothing can
tell a reader that the second number rests on the first.

## What you get

```python
from anvilate.dependency import CheckNode, Consumes, DependencyGraph, Output

graph = DependencyGraph(nodes=(
    CheckNode(id="shock",
              consumes=(Consumes(upstream="modal", output="f_n",
                                 parameter="frequency", dimension="[frequency]"),)),
    CheckNode(id="modal", produces=(Output(name="f_n", dimension="[frequency]"),)),
))

graph.order()                # ("modal", "shock") — dependencies first, whatever the declaration order
graph.downstream_of("modal") # ("shock",) — the transitive closure, in evaluation order
print(graph)                 # the chain, with what each check reads
```

## The rules

| Rule | What it means |
| --- | --- |
| A consumption is declared, with its dimension | Each `Consumes` names the upstream check, the output it reads, the parameter it feeds and the dimension that parameter takes. The dependency is data, readable without opening the check's body. |
| Dimensions agree at registration | A parameter in `[frequency]` fed by an output in `[time]` is refused when the graph is built, not on the first spec that exercises the chain. |
| A consumption must resolve | Reading an output from a check the graph does not carry, or an output that check does not produce, is refused naming both. |
| Order follows dependencies, ties follow declaration | Nothing runs before an input it consumes; checks with no ordering relation keep the order they were declared in, so the same graph evaluates the same way every run. |
| A cycle names every member | `find_cycles` returns each cycle whole, by strongly connected component, and the graph refuses to exist. The edge that closed the loop is an artifact of declaration order, and breaking a cycle by choosing a starting point would make the result depend on it. |
| One parameter, one source | A parameter fed from two upstream outputs is refused: which one wins is a question, not a default. |
| A check is not upstream of itself | Refused at the node, before the graph is assembled. |

## Status

This is the graph's contract and its ordering (`openspec/changes/add-check-dependency-graph`,
groups 1.1, 1.2 and 2.1, 2.2). No screen declares its consumptions yet, so nothing is
evaluated along a graph today: propagation of a not-evaluated verdict downstream, staleness
invalidating the transitive closure, the realized order recorded in the evidence bundle, and
the CI gate on undeclared consumption are the remaining groups of that change.
