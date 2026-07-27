# Change: Design-space exploration — deterministic sweeps and honest Pareto fronts

## Why

Anvilate answers "does this design pass?" It cannot answer "what is the lightest one that
passes?" — the question engineers actually have. The pieces are already in place: checks
are closed-form and evaluate in microseconds, design inverses exist for many of them, and
cost (and, with the carbon change, kgCO2e) are already screening objectives. What is
missing is the contract for sweeping parameters and reporting a front.

The 2025-2026 literature on LLM-driven design-space exploration converges on exactly
Anvilate's architecture: the model proposes parameters, bounds, and interpretations while
a deterministic evaluator produces every number and an exact optimizer maintains the
front (iDSE, https://arxiv.org/pdf/2505.22086; multi-agent DSE reporting more
Pareto-optimal solutions than a GA baseline at equal budget,
https://arxiv.org/abs/2512.08476). No open-source tool couples a citation-carrying
closed-form check library to a sweep engine; OpenMDAO and pymoo are frameworks, and the
commercial options are FEA-coupled and expensive.

Because closed-form evaluations are cheap, the right default is not Bayesian
optimization: a seeded, exhaustive-or-Sobol sweep with exact non-dominated sorting is
faster, fully reproducible, and lets the entire sweep live in the evidence bundle.

## What Changes

- New capability spec `design-space-exploration`: typed study declarations (parameters,
  bounds, objectives, constraints), deterministic seeded sampling with the full sweep
  recorded, exact Pareto extraction with the governing constraint named per point,
  a hard rule that every objective and constraint value comes from the deterministic
  engine and never from a model, and budget/termination honesty when a study is truncated.

## Impact

- Affected specs: new `design-space-exploration`. Interacts with `agent-repair-loop`
  (which already owes Pareto alternatives on non-convergence — this gives that
  requirement a real engine), `validation-gauntlet`, and `cost-estimation`; none change.
- Affected code (when implemented): a study runner over existing check functions; exact
  non-dominated sorting; optional pymoo backend for large spaces.
- Out of scope: topology optimization, FEA-in-the-loop optimization, and surrogate models.
