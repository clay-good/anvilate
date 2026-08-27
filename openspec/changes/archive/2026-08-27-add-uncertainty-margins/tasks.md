# Tasks: Uncertainty-aware margins

## 1. Contracts

- [x] 1.1 Distribution types (±, uniform, normal) shared with tolerance vocabulary —
      `Normal`, `Uniform`, `Symmetric` (the ± form, half-width read as `sigma_level`
      sigmas, matching the stack-up convention) in `src/anvilate/uncertainty.py`.
- [x] 1.2 Uncertainty-annotation type (probability, band, seed, samples, method,
      citation) — `MarginUncertainty`, now carried on `ScorecardEntry.uncertainty` and
      round-tripped through the calc record (schema 1.1).

## 2. Implementation

- [x] 2.1 Seeded sampling wrapper applicable to any analysis function — `sample_margin`
      takes a caller-supplied `response(mapping) -> float`, so it wraps any analysis
      function without importing the analysis layer; reuses the stack-up's stdlib
      `Random` pattern; sorts input names so a run is order-independent.
- [x] 2.2 Shortfall-probability and percentile-band computation.
- [x] 2.3 Variance-based sensitivity ranking with citation — first-order (Taylor)
      variance shares, `MONTE_CARLO_CITATION`.
- [x] 2.4 Uncertainty warning integration with scorecard rendering (default 5% threshold,
      configurable) — `ScorecardEntry.uncertainty` + `is_fragile(threshold=0.05)`,
      `Scorecard.fragile(threshold)`, and a report warning line (FRAGILE, styled) that
      leaves the deterministic verdict primary.

## 3. Tests

- [x] 3.1 Analytic agreement: linear check with normal inputs matches closed-form
      propagation (mean, std, shortfall vs the normal CDF) within Monte Carlo tolerance.
- [x] 3.2 Determinism: identical seed → identical statistics; order-independence.
- [x] 3.3 Warning threshold behavior, including the no-distributions no-op — an
      unannotated check is never fragile; the threshold is configurable; a fragile
      annotation never changes the deterministic roll-up.

## 4. Docs & examples

- [x] 4.1 Example: nominally passing bracket flagged fragile under load scatter
      (`examples/bracket_load_scatter_fragility.py`).
- [x] 4.2 Documentation: what the probability means, what it does not
      (`docs/uncertainty-margins.md`).

## Follow-ups (recorded, not dropped)

- A pack-level convenience that samples a screen's governing check directly (today
  the caller wires their own `response`), and wiring `sample_margin` into the
  discipline packs' worked examples beyond the standalone bracket example.
- FORM/SORM-class methods remain roadmap-gated behind the same contract.
