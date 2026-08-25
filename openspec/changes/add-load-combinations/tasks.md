# Tasks: Load combinations

## 1. Contracts

- [x] 1.1 Load-nature classification — `LoadNature` (D, L, Lr, S, R, W, E by ASCE 7
      symbol) in `src/anvilate/loads.py`, and an optional `LoadCase.nature` on the Spec
      IR (schema 1.1.0, additive) so a spec's load cases can be classified for factoring.
- [x] 1.2 Combination and combination-set types — `LoadCombination` (factors × natures,
      citation) and `CombinationSet` (basis label + combinations).

## 2. Implementation

- [x] 2.1 ASCE 7-22 LRFD/ASD generators — basic `asce7_lrfd_basic()` (§2.3.1) /
      `asce7_asd_basic()` (§2.4.1) with the roof companion expanded, and seismic
      `asce7_lrfd_seismic(s_ds=, redundancy=)` (§2.3.6) / `asce7_asd_seismic(...)`
      (§2.4.5) with E split into Ev (folded into the dead factor) and Eh = ρ·Q_E, both
      ±Eh directions generated. S_DS and ρ are typed user inputs.
- [x] 2.2 Evaluate per combination, envelope, name governing — `evaluate_all`,
      `envelope`, `governing(loads, minimize=...)` (max for strength, min for uplift).
      A spec declares its basis via `DesignSpec.combination_basis` and resolves it with
      `DesignSpec.combination_set()`, so the full flow is
      `spec.combination_set().governing(spec.combination_loads())`.
- [x] 2.3 Scorecard and evidence-bundle surfacing of the governing combination —
      `combination_scorecard` names the governing combination in the entry detail +
      reference, and `CombinationEvidence` carries basis, combination, clause, demand and
      the unclassified cases into `BundleSections.combinations`. Both select through one
      shared rule, so the bundle cannot cite a clause the check never used.

## 3. Tests

- [x] 3.1 Generated sets match the published combination lists — LRFD (14 expanded) and
      ASD (13 expanded) re-derived, spot-checked factors + citations.
- [x] 3.2 Counteracting-combination governs in an uplift fixture — 0.9D + 1.0W with a
      negative (uplift) wind is the minimizing governing combination.
- [x] 3.3 Subset evaluation → "not evaluated"; undeclared case → surfaced by name —
      `DesignSpec.unclassified_force_cases()`, the `unclassified=` guard on
      `combination_scorecard`, and the same list on `CombinationEvidence`.

## 4. Docs & examples

- [x] 4.1 Example: the governing combination is not the obvious one
      (`examples/canopy_beam_load_combinations.py`) — roof-live-principal governs
      bending, wind uplift governs the hold-down.
- [x] 4.2 Explanation page (`docs/load-combinations.md`): LRFD vs ASD sets and the
      factoring-not-derivation boundary.

## Shipped 2026-08-25 — the rest of 2.3 and 3.3

`CombinationEvidence` / `combination_evidence` in `anvilate.loads`,
`DesignSpec.unclassified_force_cases()` and `DesignSpec.combination_evidence()`, the
`combinations` section on `BundleSections`, `docs/load-combinations.md`, and the extended
`examples/spec_load_combination_check.py`.

**A load case nobody classified made the demand smaller, and nothing said so.**
`combination_loads()` skips a case that carries a force and no `nature`, and every
combination treats a nature nobody supplied as zero. Those two together turn a forgotten
classification into a smaller demand and a comfortable pass: in the worked example a 130 kN
girder passes at 1.52 on a demand of 85.6 kN, and the same girder with the 25 kN conveyor
reaction classified fails at 1.04 on 125.6 kN. The guard fires **before a number is
computed**, and fires even when the subset demand would have failed — a FAIL that is right
by accident goes on being reported after the missing case turns it into a pass.

**A case with no force is not listed.** A remote-mass case has nothing to contribute to a
factored sum, so leaving it unclassified costs nothing, and listing it would train a reader
to ignore the list.

**The safe path is the short one.** `DesignSpec.combination_evidence()` passes the
unclassified list for you; building the record from the mapping directly leaves that to the
caller, which is the step it exists so nobody has to remember. Both are asserted, including
the mistake the short path removes.

**One selection rule, not two.** The check picks the governing combination by magnitude
(a safety factor is `capacity / |demand|`) and the bundle would have been free to pick by
sign. On an uplift set those name different combinations, so the bundle would have cited a
clause the check never used. `_governing_for_check` is shared, and the drift test asserts
its own premise — that sign and magnitude genuinely disagree on the case it uses.

**The bundle's roll-up sees it.** The combinations section is a verdict about the part, not
information about the design space, so a green scorecard under a partially classified load
set is a `NOT_EVALUATED` bundle.

## Deferred to later slices (recorded, not dropped)

- The gauntlet expansion that evaluates a declared combination set as part of a full
  screening run. The spec-to-scorecard-to-bundle flow is wired; what is left is the
  gauntlet driving it rather than the caller.
