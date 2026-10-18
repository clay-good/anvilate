# Change: Design optimization — search, on the user's machine, for the lightest design that passes

## Why

`design-space-exploration` sweeps a grid and returns the exact front. That was the right
default for closed-form checks, which run in microseconds: a seeded exhaustive sweep is
faster than any clever search and small enough to keep whole. Two things this session's
request asks for break that assumption:

- **Products have too many variables to sweep.** A two-stage reducer has a ratio split,
  a module and a face width per stage, tooth counts, shaft diameters and bearing
  choices. Ten variables at ten levels is ten billion points. The sweep's honest budget
  rule would report a provisional front over almost none of the space.
- **FEA-backed objectives cost a minute each.** Once `add-local-fea` runs CalculiX, a
  housing's stress is a solver run, not a formula. A sweep of a few hundred points is an
  afternoon; an optimizer that spends its runs where they matter is minutes.

The rest of the market answers this in the cloud. Fusion's generative design solves on
Autodesk's servers; SOLIDWORKS' new AI companions need design data in the cloud for some
skills. Academic results say why checking matters more than generating: on a May 2026
benchmark, frontier coding agents writing multi-part STEP assemblies validated by FEA
produced no strict-passing artifact on the first attempt, and an ICML 2026 benchmark
scored agents at about 4% on functional gearbox checks even when the gearbox looked
right (`design.md` has the sources). An optimizer whose feasibility is Anvilate's own
cited scorecard, running locally with permissive libraries, is the gap.

The doctrine does not change. A design that did not pass is never the answer, every
number comes from the deterministic engine, and nothing is called optimal.

## What Changes

| Area | Change |
| --- | --- |
| Search strategies | A study may declare a search instead of a sweep: a seeded evolutionary search for mixed variables and several objectives, and a derivative-free local refinement for continuous ones. Both run serially or with an ordered commit, so the same study, seed and versions give the same evaluated points in the same order. |
| Variables from catalogs | A variable may be continuous, integer, or a choice from a bundled table (preferred gear modules, stock plate thicknesses, a bearing series, a motor frame). A choice can only take a value the table holds, so a search cannot invent a stock size. |
| Cheapest evaluation first | Each candidate is screened tier by tier: T1 and drive-train checks first, FEA only for candidates that pass them. Evaluations are cached by content digest, so a repeated candidate costs nothing. The budget is stated in evaluations, solver runs and wall-clock. |
| Inverse-seeded starts | Starting points are the declared design and its inverse repairs, so a search begins from feasible designs where an inverse exists. |
| An honest result | The result is the best feasible design found under the budget, with its governing checks and margins, the improvement history, and a neighborhood check: each continuous variable perturbed both ways and re-evaluated. A result whose neighborhood holds a better feasible point says so. |
| A proposal, not an edit | The result is a spec diff. The spec changes only when the agent applies it, and the change is recorded in iteration provenance as study-derived. |
| Topology seeds (later phase) | A material-layout study on a declared design space may return a density field and a picture as a *seed* for the engineer, never as a buildable part, because turning a density field into CAD is an unsolved problem. |
| Agent surface | Studies are reachable over MCP as one tool that runs as a task with progress and cancellation. |

## Impact

- Affected specs: `design-space-exploration` (ADDED), `headless-automation` (ADDED).
  On archive, the capability's purpose line ("a sweep, not an optimiser") becomes "a
  sweep or a search"; its rule that nothing is called optimal stays.
- Builds on: `agent-repair-loop` (inverse-first repair, provenance), `add-local-fea` (FEA
  objectives and constraints), `add-drive-trains` (the reducer's variables and checks),
  `add-product-structure` (a study over a product), `add-margin-of-safety-reporting`
  (margins on the result).
- New optional dependency: pymoo (Apache-2.0) for the evolutionary search. SciPy (BSD-3)
  is already available for local refinement. Both stay in-process. Nothing GPL or LGPL is
  imported.
- Explicitly out:
  - Surrogate or learned models that produce any reported value (D2 and "every number
    comes from the deterministic engine"). A search may use whatever it likes to *choose*
    the next candidate.
  - Gradient-based shape optimization through the CAD kernel.
  - Turning a topology result into a B-rep part.
  - Any cloud solve.
