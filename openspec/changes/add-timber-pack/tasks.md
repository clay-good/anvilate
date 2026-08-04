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
- [ ] 2.2 Shear and bearing
- [~] 2.3 Compression with column stability factor — `nds_euler_buckling_stress`
      (F_cE = 0.822·E'_min/(l_e/d)²) and `nds_column_stability_factor` (the Ylinen C_P,
      §3.7.1) compose into the adjusted compression value F'_c = F*_c·C_P. The l_e/d
      slenderness limit (≤ 50) guard and a compression scorecard are follow-ups.
- [x] 2.4 Combined bending + axial interaction — `nds_combined_bending_compression`
      (§3.9.2: (f_c/F'_c)² + f_b/[F'_b(1−f_c/F_cE)] ≤ 1) with the moment-amplification
      denominator guarded against buckling (f_c ≥ F_cE).

## 3. Tests & examples

- [ ] 3.1 Worked-example anchors from published NDS example problems
- [x] 3.2 Example: floor joist screened wet vs. dry — the wet-service factor C_M flips
      the verdict (`examples/floor_joist_wet_service.py`).
- [x] 3.3 Not-evaluated behavior without reference values — `nds_bending_scorecard`
      returns NOT_EVALUATED when no adjusted value is supplied.

## 4. Docs

- [ ] 4.1 Pack documentation: scope, where reference values legally come from, screening
      disclaimer
