# Tasks: Timber pack

## 1. Contracts

- [~] 1.1 User-supplied reference design value — the reference value enters as a
      caller-supplied `Quantity` (a design stress) into `nds_adjusted_design_value`; a
      richer typed record (species/grade label, provenance) is a follow-up.
- [x] 1.2 Adjustment-factor chain with per-factor visibility — `nds_adjusted_design_value`
      takes the factors as a name→value mapping (F' = F·∏Cᵢ) so every factor stays
      visible, and `nds_load_duration_factor` supplies the Table 2.3.2 C_D (the one
      short, republishable factor list).

## 2. Checks

- [~] 2.1 Bending — `nds_bending_scorecard` screens the applied stress against the
      adjusted bending value (No-silent-green NOT_EVALUATED without a reference value);
      the beam-stability C_L and size C_F factors enter through the caller's chain.
      Dedicated C_L/C_F derivations are a follow-up.
- [x] 2.2 Shear and bearing — `nds_shear_stress` (§3.4.2, f_v = 1.5·V/(b·d)) and
      `nds_bearing_stress` (§3.10.2, f_c⊥ = P/(b·l_b)) with `nds_shear_scorecard` and
      `nds_bearing_scorecard` screening each against its adjusted value (NOT_EVALUATED
      without one). `nds_bearing_area_factor` supplies the §3.10.4 C_b, now scoped to
      bearings under 6 in *and* at least 3 in from the member end (`end_distance`).
      `examples/timber_header_bearing_governs.py` is the anchor: a short header whose
      bending and shear pass while it crushes at its support.
- [x] 2.3 Compression with column stability factor — `nds_euler_buckling_stress`
      (F_cE = 0.822·E'_min/(l_e/d)²) and `nds_column_stability_factor` (the Ylinen C_P,
      §3.7.1) compose into the adjusted compression value F'_c = F*_c·C_P, screened by
      `nds_compression_scorecard` (NOT_EVALUATED without a reference value). The §3.7.1.4
      slenderness cap now refuses past l_e/d = 50 in service (75 with
      `during_construction=True`) rather than quoting the plausible small stress the
      formula still yields. `examples/timber_post_slenderness.py` is the anchor.
- [x] 2.4 Combined bending + axial interaction — `nds_combined_bending_compression`
      (§3.9.2: (f_c/F'_c)² + f_b/[F'_b(1−f_c/F_cE)] ≤ 1) with the moment-amplification
      denominator guarded against buckling (f_c ≥ F_cE).

## 3. Tests & examples

- [x] 3.1 Worked-example anchors from published NDS example problems — three textbook
      problems worked by hand and pinned end to end (`test_nds_worked_example_*` in
      `tests/test_analysis.py`): the 2x10/15 ft floor joist (bending SF 1.08 governs
      over shear 3.33), the 6x6/12 ft post (compression 1.40, bearing 1.58, and the
      2.52 that skipping C_P would invent), and the same post as a beam-column under
      wind (interaction 0.79, where C_D 1.6 lifts F*_c by 60% but F'_c by only 11%
      because a higher F*_c lowers C_P). The asserted values are the hand solution,
      not a re-derivation from the code.
- [x] 3.2 Example: floor joist screened wet vs. dry — the wet-service factor C_M flips
      the verdict (`examples/floor_joist_wet_service.py`).
- [x] 3.3 Not-evaluated behavior without reference values — `nds_bending_scorecard`
      returns NOT_EVALUATED when no adjusted value is supplied.

## 4. Docs

- [x] 4.1 Pack documentation: scope, where reference values legally come from, screening
      disclaimer — [`docs/timber-screening.md`](../../../docs/timber-screening.md) opens
      with a "Scope, and what it is not" section naming the five screened limit states,
      the excluded ones (connections, glulam/CLT, fire, serviceability, C_L/C_F
      derivations), the copyright position on the species/grade tables (C_D is the one
      republishable list), and the T1-screen disclaimer.
