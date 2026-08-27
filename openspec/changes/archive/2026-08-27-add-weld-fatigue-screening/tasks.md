# Tasks: Weld fatigue screening

## 1. Contracts

- [x] 1.1 Detail-category input type — `WeldDetailCategory` in
      `anvilate.standards.fatigue` carries the standard, edition, table, detail
      description and which stress family the category belongs to, and hands back the
      curve. The bare `Quantity` still works for the closed-form functions.
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

## Shipped 2026-08-25 — task 1.1, and a limit the curve does not know about

`WeldDetailCategory`, `WeldStressKind` and `EN1993_NORMAL_DETAIL_CATEGORIES` in
`anvilate.standards.fatigue`; `weld_nominal_stress_range_limit` and the `yield_strength`
guard on `weld_fatigue_scorecard`; the two new sections of
`docs/weld-fatigue-screening.md`.

**A detail category is a number that means nothing on its own.** EN 1993-1-9's category 90
and IIW's FAT 90 are the same number and a different curve (the knee at 5M against 10M),
and AASHTO's letters are a third construction — so the standard and edition are required
fields. So is the detail description and its table: a category is a verdict about a
geometry, and recording only the number is how a butt weld's category reaches a
fillet-welded attachment.

**A shear category refuses the direct-stress curve.** EN's Δτ family runs a single m = 5
with no knee at 5 million cycles, which the standard's own combined-stress interaction
repeats in its exponents. Δτ_C = 100 and Δσ_C = 100 are the same label and different
curves, and evaluating the first on the second's m = 3 branch over-states life. The shear
curve itself is *not* built: the m = 5 slope is confirmed by a published source and its
cut-off cycle count is not, so it refuses rather than guessing.

**The ladder is discrete and was read off a published figure**, not recalled: 36, 40, 45,
50, 56, 63, 71, 80, 90, 100, 112, 125, 140, 160, from the fatigue strength curve legend in
SCI's "Introduction to fatigue design to BS EN 1993-1-9" (New Steel Construction,
September 2018). A value between rungs is refused with the two nearest named; another
standard's category is not held to it. The same article supplies a worked endurance —
category 160 at a 250 MPa range gives 5.243e5 cycles — now pinned against the shipped
curve.

**EN 1993-1-9 §8 caps the nominal range at 1.5·f_y and nothing enforced it.** The guard-the-domain shape exactly: a 600 MPa range on a category-90 detail returns a
few thousand cycles, a finite ordinary-looking number from outside the elastic regime the
method is calibrated on. Optional, because the limit needs a yield strength the screen did
not previously ask for; supplied, a spectrum containing such a range is NOT_EVALUATED.

**Writing that guard found the module had no finiteness check at all.** `_require_stress`
in `analysis/fatigue.py` checked dimension only, so a NaN travelled to a NaN safety factor
— which the scorecard does catch. But `range > nan` is False for every range, so a NaN
yield strength turned the new §8 limit **off** rather than making it loud. A guard that
stops guarding is worse than a NaN answer, so the finiteness check now sits in the module's
own stress and length helpers and every entry point gets it.

## Follow-ups (recorded, not dropped)

- The shear-stress curve family (single m = 5) and the combined direct-plus-shear
  interaction (Δσ/Δσ_C)³ + (Δτ/Δτ_C)⁵ ≤ 1, once the shear cut-off cycle count is
  confirmed against a published source.
- Optional validation sampling against the open welded-joint S-N dataset, license
  verified before ingestion (3.4).
