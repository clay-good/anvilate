# Change: Uncertainty-aware margins — input scatter to margin distributions

## Why

A nominal PASS computed from a load the user only knows to ±20% can hide a one-in-five
chance of failure — exactly the class of silent green Anvilate exists to eliminate.
Research shows the practical uncertainty methods engineers actually adopt are (a) Monte
Carlo on inputs with tolerance-like distributions and (b) sensitivity ranking of which
input moves the margin most; full FORM/SORM treatment stays niche (PySTRA,
https://github.com/pystra/pystra, 2025 SoftwareX paper). pyLife frames fatigue results as
failure probability rather than bare pass/fail (https://pylife.readthedocs.io/). No calc
tool surveyed — commercial or OSS — offers per-check margin distributions.

Anvilate is uniquely positioned: it already has typed inputs and seeded Monte Carlo
machinery in the tolerance stack-up module. Generalizing that machinery to any analysis
check is a differentiator with modest new surface.

## What Changes

- New capability spec `uncertainty-quantification`: inputs may carry typed distributions,
  any check can report a margin distribution with probability of exceeding the allowable,
  a sensitivity ranking, and a no-silent-green interaction rule (a nominal PASS with a
  material failure probability gets a warning).
- Deterministic seeding, screening labels, and method citations follow existing doctrine;
  FORM/SORM-class methods are roadmap-gated behind the same contract.

## Impact

- Affected specs: new `uncertainty-quantification` capability; interacts with
  `tolerance-management` (shared distribution vocabulary) and `validation-gauntlet`
  (warning status semantics), both unchanged in their existing requirements.
- Affected code (when implemented): a sampling wrapper over analysis functions; scorecard
  annotation type; reuse of the stack-up Monte Carlo core.
- Additive: deterministic verdicts remain the primary result; probabilistic results are
  opt-in annotations.
