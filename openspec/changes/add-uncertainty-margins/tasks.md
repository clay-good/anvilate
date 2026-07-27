# Tasks: Uncertainty-aware margins

## 1. Contracts

- [ ] 1.1 Distribution types (±, uniform, normal) shared with tolerance vocabulary
- [ ] 1.2 Uncertainty-annotation type on scorecard entries (probability, band, seed,
      samples, method, citation)

## 2. Implementation

- [ ] 2.1 Seeded sampling wrapper applicable to any analysis function (reuse stack-up
      Monte Carlo core)
- [ ] 2.2 Shortfall-probability and percentile-band computation
- [ ] 2.3 Variance-based sensitivity ranking with citation
- [ ] 2.4 Uncertainty warning integration with scorecard rendering (default 5% threshold,
      configurable)

## 3. Tests

- [ ] 3.1 Analytic agreement: linear check with normal inputs matches closed-form
      propagation within tolerance
- [ ] 3.2 Determinism: identical seed → identical statistics
- [ ] 3.3 Warning threshold behavior, including the no-distributions no-op

## 4. Docs & examples

- [ ] 4.1 Example: nominally passing bracket flagged fragile under load scatter
- [ ] 4.2 Documentation: what the probability means, what it does not (screening, not
      certified reliability)
