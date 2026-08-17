# Tasks: Weld fatigue screening

## 1. Contracts

- [~] 1.1 Detail-category input type — the detail category enters as a user-supplied
      `Quantity` (Δσ_C at 2M cycles) with its EN 1993-1-9 citation in the docstrings; a
      richer typed record (standard, edition, detail description, provenance) is a
      follow-up.
- [x] 1.2 Correction declaration types (thickness, mean stress) — both corrections now
      enter as declarations with their factor exposed: `weld_size_effect_factor` (k_s)
      and `weld_mean_stress_factor` (Δσ_eff/Δσ), each caller-tunable and each with its
      clause. A richer typed correction record travels with 1.1's detail-category record.

## 2. Implementation

- [x] 2.1 Standardized S-N curve construction from a declared category, cited —
      `weld_detail_endurance_cycles` (EN 1993-1-9 trilinear: m=3 to Δσ_D at 5M, m=5 to
      the cutoff Δσ_L at 100M), plus `weld_constant_amplitude_fatigue_limit` and
      `weld_cutoff_limit` for the knee points.
- [x] 2.2 Thickness and mean-stress corrections with visible factors — thickness
      size-effect (`weld_size_effect_factor` k_s = (t_ref/t)^n, EN 1993-1-9 §7.2.2, and
      `weld_size_corrected_detail_category` = k_s·Δσ_C) plus the mean-stress reduction
      (§7.2.1): `weld_effective_stress_range` discounts the compressive part of a cycle
      to 0.6 for a stress-relieved or non-welded detail only, and `weld_mean_stress_factor`
      surfaces the same correction as its factor. `stress_relieved` defaults to False —
      the bonus is a claim about fabrication, so the caller must make it.
- [x] 2.3 Spectrum damage via existing Miner summation — the per-range lives feed
      `miner_cumulative_damage` directly (demonstrated in the example + a test).
- [x] 2.4 Allowable-range design inverse — `weld_detail_allowable_stress_range`
      (the allowable Δσ for a target life, on the m=3 / m=5 / cutoff branch).

## 3. Tests

- [x] 3.1 Anchored against the curve's published points — Δσ_D ≈ 0.737·Δσ_C, Δσ_L ≈
      0.405·Δσ_C; N = 2M at Δσ_C, 5M at Δσ_D, and the m=5 branch between.
- [x] 3.2 Forward/inverse round-trip — the allowable range at a life feeds back through
      the endurance curve to the same life on each branch.
- [x] 3.3 Missing category → "not evaluated" — `weld_fatigue_scorecard` returns a
      `NOT_EVALUATED` entry when no detail category is supplied (No-silent-green: the
      category is the engineer's call), with the thickness correction applied when
      given. Mean-stress correction factors surfacing remains with 2.2.

## 4. Docs & examples

- [x] 4.1 Example: a welded attachment screened over a load spectrum
      (`examples/welded_bracket_fatigue.py`) — the same spectrum passes on a category-90
      detail and fails on a category-56 one, so the detail category is the decision.
- [x] 4.2 Explanation page: why Anvilate makes you choose the detail category —
      [`docs/weld-fatigue-screening.md`](../../../docs/weld-fatigue-screening.md), which
      shows the same 80 MPa range spanning a factor of 50 in life across categories 56 /
      90 / 160, the NOT_EVALUATED contract, both corrections, and the scope boundary.

## Follow-ups (recorded, not dropped)

- A richer typed detail-category record carrying standard/edition/detail description.
- Optional validation sampling against the open welded-joint S-N dataset, license
  verified before ingestion (3.4).
