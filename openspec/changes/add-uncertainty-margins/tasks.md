# Tasks: Uncertainty-aware margins

## 1. Contracts

- [x] 1.1 Distribution types (±, uniform, normal) shared with tolerance vocabulary —
      `Normal`, `Uniform`, `Symmetric` (the ± form, half-width read as `sigma_level`
      sigmas, matching the stack-up convention) in `src/anvilate/uncertainty.py`.
- [x] 1.2 Uncertainty-annotation type (probability, band, seed, samples, method,
      citation) — `MarginUncertainty`. Attaching it to a scorecard entry as a rendered
      annotation is the follow-up slice (see 2.4).

## 2. Implementation

- [x] 2.1 Seeded sampling wrapper applicable to any analysis function — `sample_margin`
      takes a caller-supplied `response(mapping) -> float`, so it wraps any analysis
      function without importing the analysis layer; reuses the stack-up's stdlib
      `Random` pattern; sorts input names so a run is order-independent.
- [x] 2.2 Shortfall-probability and percentile-band computation.
- [x] 2.3 Variance-based sensitivity ranking with citation — first-order (Taylor)
      variance shares, `MONTE_CARLO_CITATION`.
- [ ] 2.4 Uncertainty warning integration with scorecard rendering (default 5% threshold,
      configurable) — `MarginUncertainty.is_fragile(threshold=0.05)` computes the trigger;
      wiring it onto `ScorecardEntry`/report rendering is the next slice.

## 3. Tests

- [x] 3.1 Analytic agreement: linear check with normal inputs matches closed-form
      propagation (mean, std, shortfall vs the normal CDF) within Monte Carlo tolerance.
- [x] 3.2 Determinism: identical seed → identical statistics; order-independence.
- [~] 3.3 Warning threshold behavior — `is_fragile` threshold covered; the
      no-distributions no-op belongs with the scorecard integration slice (2.4).

## 4. Docs & examples

- [x] 4.1 Example: nominally passing bracket flagged fragile under load scatter
      (`examples/bracket_load_scatter_fragility.py`).
- [x] 4.2 Documentation: what the probability means, what it does not
      (`docs/uncertainty-margins.md`).

## Deferred to the next slice (recorded, not dropped)

- Scorecard-entry annotation + report rendering of the uncertainty warning (2.4),
  and its no-distributions no-op (3.3) — the deterministic verdict stays primary;
  the probabilistic result becomes an opt-in annotation on the entry.
