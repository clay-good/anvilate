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

## Running a chain

`run_chain(graph, run_check)` evaluates the checks in dependency order, calling `run_check`
with each check's declared parameters already bound to the upstream values:

```python
from anvilate.dependency import run_chain

run = run_chain(graph, run_check)
run.order                          # the realized order, recorded rather than recomputed
run.card()                         # the entries as a scorecard, in that order
run.inherited_margins("shock")     # its own conservatism and every upstream check's
run.stale_after("modal")           # what a change to modal invalidates: the whole closure
```

| Rule | What it means |
| --- | --- |
| A gap propagates, and the blocked check is never called | A check downstream of one that did not run is `not_evaluated`, naming the upstream output it takes and the check at the head of the broken chain. It is not handed a default: a verdict computed from a value nobody produced is the silent green this library exists to refuse. |
| A check that did not run hands nothing on | A `ChainResult` carrying outputs with an unevaluated entry is refused at construction. |
| Conservatism is inherited | A downstream result's margins are its own plus every upstream check's, read off the graph — a factor on a temperature is still in force on the displacement computed from it. A check that merely ran earlier is not upstream and its factors are not inherited. |
| Staleness is the whole closure | `stale_after` returns the changed check and every transitive consumer. Recomputing the first hop and leaving the rest on the old value is a card mixing two evaluations of one chain. |
| The run records the order it ran in | `order` is read off the results, not recomputed by a reader who might order them differently. |

[`examples/heat_to_clearance_chain.py`](../examples/heat_to_clearance_chain.py) runs a real
six-link chain — a motor's dissipation through a rail's thermal growth to a running
clearance — with the library's own closed-form functions at each link, and shows the same
chain refusing to compute anything downstream of an unmeasured heat source.

## Status

This is the graph, its ordering and the chain runner
(`openspec/changes/add-check-dependency-graph`, groups 1.1, 1.2, 2.1, 2.2, 3.1, 3.2 and 3.3).
No screen in the library declares its consumptions yet, so nothing in `screen_spec` runs
along a graph today: wiring the screens, recording the realized order in the evidence bundle,
rendering the chain in a derivation, and the CI gate on undeclared consumption are what
remain.
