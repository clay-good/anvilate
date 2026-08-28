# Screening a Design Spec, and the tier it has to name rather than run

**Every discipline pack screens a typed element you build by hand. Nothing screened the
spec document itself, so the pipeline had a hole in the middle: a spec compiled to the IR
and stopped, and the scorecard came from a separate object the caller assembled.**
`screen_spec` closes the part of that hole the IR can support today and is explicit about
the part it cannot.

```python
from anvilate.screening import screen_spec

card = screen_spec(spec)
```

It is also what `run_validation` dispatches to over the
[MCP surface](mcp-tool-contracts.md), which makes it the second operation an agent can call
over the wire and get an answer to.

## What the document supports

| Check | Source | Verdict |
| --- | --- | --- |
| tolerance achievability, one per toleranced dimension | the declared process's finest achievable band | FAIL when the demanded band is tighter than the floor, with the capability record cited |
| stack-up, one per declared chain | the chain's own worst-case analysis | judged on the **worst case**, never the RSS spread |
| load classification | every force-carrying load case | NOT_EVALUATED, naming the cases, when any carries no declared nature |

Tolerance achievability runs when the spec's acceptance criteria demand T2. Chains and load
cases are screened whatever tiers the spec names — a declared chain is the document asking
for it.

**The worst case is the gate.** The two answers differ over a real band: two ±0.05 mm
dimensions on a 0.2 mm nominal gap span 0.1..0.3 mm worst-case and about 0.129..0.271 mm on
RSS, so a requirement of 0.12..0.28 mm passes statistically and fails in the worst case. A
part that can be built out of tolerance is one that will be.

## What it cannot do, and why that is not a missing feature

**A `DesignSpec` does not say what kind of structural element the part is.** It states a
material, a process, interfaces, dimensions, tolerances, loads and acceptance criteria — and
nothing that lets a screen choose between a lifting lug, a beam and a shallow footing. So no
discipline-pack screen can be selected from a spec, and **the T1 analytical tier reports
`NOT_EVALUATED` on every spec**, with that reason.

That is a gap in the IR, not in the screen, and closing it means giving the IR an element
declaration — a change to a published schema with a version bump and a story for clients
pinned to the old one. It is stated here rather than papered over by matching on a part's
name, which would be a guess that reads exactly like a fact once it is in a scorecard.

T0 reports the same way: it checks a built solid, and no geometry is generated from a spec
today. T3 is bounded by a convergence criterion rather than by the size of its input, so it
is not part of a synchronous screen at all.

## The rule that makes the card safe to read

**A tier the spec demanded always produces an entry.** Including — especially — when the
document carries nothing to run it against: a spec that demands T2 and declares no
toleranced dimension gets one `NOT_EVALUATED` entry saying so.

The alternative is what makes this worth writing down. A demanded tier that quietly produced
no entries would leave `Scorecard.passed` green on the strength of whatever checks happened
to exist, and a part screened on zero checks would be indistinguishable from a part that
passed. Every tier the caller asked about is answered, and a tier the spec did not demand is
not screened and not reported — the acceptance criteria are the contract for which tiers
must run.

## What is not screened

Geometric tolerances declared on the spec are legal at construction — the
[semantic GD&T layer](semantic-gdt.md) enforces Y14.5's grammar in the constructor — so
there is nothing left for a screen to catch, and a section that only ever passes is a
section a reader learns to skip. Interfaces resolve at reference validation, which is
`validate_references`, not a check with a verdict.
