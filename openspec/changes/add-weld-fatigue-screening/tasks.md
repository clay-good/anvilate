# Tasks: Weld fatigue screening

## 1. Contracts

- [~] 1.1 Detail-category input type — the detail category enters as a user-supplied
      `Quantity` (Δσ_C at 2M cycles) with its EN 1993-1-9 citation in the docstrings; a
      richer typed record (standard, edition, detail description, provenance) is a
      follow-up.
- [ ] 1.2 Correction declaration types (thickness, mean stress) — next slice.

## 2. Implementation

- [x] 2.1 Standardized S-N curve construction from a declared category, cited —
      `weld_detail_endurance_cycles` (EN 1993-1-9 trilinear: m=3 to Δσ_D at 5M, m=5 to
      the cutoff Δσ_L at 100M), plus `weld_constant_amplitude_fatigue_limit` and
      `weld_cutoff_limit` for the knee points.
- [~] 2.2 Thickness and mean-stress corrections with visible factors — thickness
      size-effect done (`weld_size_effect_factor` k_s = (t_ref/t)^n, EN 1993-1-9 §7.2.2,
      and `weld_size_corrected_detail_category` = k_s·Δσ_C); the mean-stress reduction
      is the remaining correction.
- [x] 2.3 Spectrum damage via existing Miner summation — the per-range lives feed
      `miner_cumulative_damage` directly (demonstrated in the example + a test).
- [x] 2.4 Allowable-range design inverse — `weld_detail_allowable_stress_range`
      (the allowable Δσ for a target life, on the m=3 / m=5 / cutoff branch).

## 3. Tests

- [x] 3.1 Anchored against the curve's published points — Δσ_D ≈ 0.737·Δσ_C, Δσ_L ≈
      0.405·Δσ_C; N = 2M at Δσ_C, 5M at Δσ_D, and the m=5 branch between.
- [x] 3.2 Forward/inverse round-trip — the allowable range at a life feeds back through
      the endurance curve to the same life on each branch.
- [~] 3.3 Missing category → "not evaluated"; corrections appear in results — bad-input
      guards covered; a scorecard-level "not evaluated" for an absent category and the
      correction factors belong with the corrections slice (2.2 / 1.2).

## 4. Docs & examples

- [x] 4.1 Example: a welded attachment screened over a load spectrum
      (`examples/welded_bracket_fatigue.py`) — the same spectrum passes on a category-90
      detail and fails on a category-56 one, so the detail category is the decision.
- [ ] 4.2 Explanation page: why Anvilate makes you choose the detail category — follow-up.

## Follow-ups (recorded, not dropped)

- Thickness (size-effect) and mean-stress corrections with the factors shown explicitly
  (1.2 / 2.2), and a scorecard "not evaluated" when no category is supplied (3.3).
- A richer typed detail-category record carrying standard/edition/detail description.
- Optional validation sampling against the open welded-joint S-N dataset, license
  verified before ingestion (3.4).
