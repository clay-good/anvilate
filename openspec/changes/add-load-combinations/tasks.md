# Tasks: Load combinations

## 1. Contracts

- [x] 1.1 Load-nature classification — `LoadNature` (D, L, Lr, S, R, W, E by ASCE 7
      symbol) in `src/anvilate/loads.py`.
- [x] 1.2 Combination and combination-set types — `LoadCombination` (factors × natures,
      citation) and `CombinationSet` (basis label + combinations).

## 2. Implementation

- [~] 2.1 ASCE 7-22 LRFD/ASD generators — `asce7_lrfd_basic()` (§2.3.1) and
      `asce7_asd_basic()` (§2.4.1), roof companion "(Lr or S or R)" expanded. Seismic
      (§2.3.6 / §2.4.5, E split into Ev/Eh from S_DS) is the next slice — the natures
      vocabulary already carries `E`.
- [x] 2.2 Evaluate per combination, envelope, name governing — `evaluate_all`,
      `envelope`, `governing(loads, minimize=...)` (max for strength, min for uplift).
- [ ] 2.3 Scorecard and evidence-bundle surfacing of the governing combination — the
      next slice (wire the governing combination into a `ScorecardEntry` and the
      evidence roll-up).

## 3. Tests

- [x] 3.1 Generated sets match the published combination lists — LRFD (14 expanded) and
      ASD (13 expanded) re-derived, spot-checked factors + citations.
- [x] 3.2 Counteracting-combination governs in an uplift fixture — 0.9D + 1.0W with a
      negative (uplift) wind is the minimizing governing combination.
- [ ] 3.3 Subset evaluation → "not evaluated"; undeclared case → rejection — belongs
      with the gauntlet/spec-ir integration slice (2.3), not the standalone generator.

## 4. Docs & examples

- [x] 4.1 Example: the governing combination is not the obvious one
      (`examples/canopy_beam_load_combinations.py`) — roof-live-principal governs
      bending, wind uplift governs the hold-down.
- [x] 4.2 Explanation page (`docs/load-combinations.md`): LRFD vs ASD sets and the
      factoring-not-derivation boundary.

## Deferred to later slices (recorded, not dropped)

- Seismic combinations (§2.3.6 / §2.4.5) with E split into Ev/Eh from S_DS taken as
  typed user inputs (rest of 2.1).
- spec-ir load-nature classification on the Spec IR's load cases, and the gauntlet
  expansion that evaluates a declared combination set and surfaces the governing
  combination on the scorecard + evidence bundle (2.3, 3.3). This first slice is the
  standalone combination engine, mirroring how `uncertainty.py` shipped before its
  scorecard wiring.
