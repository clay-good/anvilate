# Tasks: Timber pack

## 1. Contracts

- [x] 1.1 User-supplied reference design value — `TimberDesignValue` in
      `anvilate.standards.timber` carries the standard, edition, table, species, grade,
      size classification and *which property* the number is, and enforces NDS Table
      4.3.1 on the factor chain. The bare `Quantity` still works for
      `nds_adjusted_design_value`.
- [x] 1.2 Adjustment-factor chain with per-factor visibility — `nds_adjusted_design_value`
      takes the factors as a name→value mapping (F' = F·∏Cᵢ) so every factor stays
      visible, and `nds_load_duration_factor` supplies the Table 2.3.2 C_D (the one
      short, republishable factor list).

## 2. Checks

- [x] 2.1 Bending — `nds_bending_scorecard` screens the applied stress against the
      adjusted bending value (no-silent-green NOT_EVALUATED without a reference value),
      and the beam stability factor C_L is derived: `nds_beam_slenderness_ratio` (R_B),
      `nds_bending_buckling_stress` (F_bE) and `nds_beam_stability_factor` (C_L). The
      size factor C_F stays a caller-supplied factor — it is a species/grade *table*, not
      a formula, and belongs with 1.1's typed reference record.
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

## Shipped 2026-08-25 — the C_L half of task 2.1

`nds_beam_slenderness_ratio`, `nds_bending_buckling_stress` and
`nds_beam_stability_factor` in `analysis/nds_timber.py`,
`examples/timber_beam_lateral_stability.py`, and the bending section of
`docs/timber-screening.md`.

**Anchored on one fully self-consistent published worked example** before a line was
written: l_e 213 in, d 28.5 in, b 6.75 in, E'_min 850,000 psi → R_B 11.54, F_bE 7,659 psi,
and F_bE/F_b* = 2.77 → C_L 0.974. Every constant in the chain is fixed by it. A second
source's geometry checks R_B independently (17.60) and its C_L end to end (0.96); that
page's own F_bE does *not* reconcile with the E'_min it displays, so it anchors C_L and
not the coefficient.

**1.20, not 0.822.** The beam's F_bE and the column's F_cE have the same shape and the
same symbols, and the coefficients differ by 46%. Likewise the Ylinen constants: the beam
uses a fixed 1.9 and 0.95 where the column uses 2c and c with c varying by product. A test
asserts the ratio of the two buckling stresses is exactly 1.20/0.822, so the confusion
cannot be introduced quietly.

**C_L takes F_b*, not F'_b**, and getting that wrong is unconservative. On the worked
rafter, passing the fully adjusted value returns 0.830 where the rafter has 0.402 — more
than double, and nothing about the number looks wrong. Pinned by direction rather than by
value.

**The R_B cap has no construction-stage relief**, unlike the column's §3.7.1.4 which
tolerates 75 while a frame goes up. The asymmetry is the standard's; the docstring says so
in the place a reader would otherwise take it for an omission.

**One dead guard removed rather than left in.** The first draft clamped the square root at
zero. The discriminant [(1+x)/1.9]² − x/0.95 has its minimum at x = 0.9 where it is exactly
1/19, so the clamp could never fire and read as though the expression could go negative.
Removed, with the minimum swept and pinned instead — a guard that cannot fire is a claim
about the formula that is not true of it.

**Monotonicity swept before it was declared**: C_L rises with F_bE/F_b* and stays under 1
across 5,000 ratios, rather than being argued from the shape of the formula.

## 2026-08-25 — task 1.1, and a table the docstring described and nothing enforced

`TimberDesignValue`, `TimberProperty`, `SizeClassification` and `NDS_APPLICABLE_FACTORS`
in `anvilate.standards.timber`; the reference-value section of `docs/timber-screening.md`.

**A reference design value is a number with four things attached.** Which property it is
(F_b, F_t, F_v, F_c, F_c⊥, E, E_min are seven different numbers for the same wood, and a
stress and a modulus are both `[pressure]`, so the unit cannot tell them apart), the
species and grade, the size classification (dimension lumber and timbers are graded to
different rules and take different size factors), and the standard's edition.

**NDS Table 4.3.1 was in the docstring and enforced by nobody.** The module has always
said the caller "simply omits" the factors that do not apply to a value; `adjusted()`
refuses them instead. The two absences that catch people are **C_D on either modulus or on
F_c⊥** and **C_F on either modulus or on F_v**. Neither is a conservative extra: applying
C_D to a modulus at a snow load makes the beam 15% stiffer than the standard allows, on
exactly the deflection check that usually governs a timber beam — the mistake shows up as a
member passing the check it was about to fail.

**The applicability table was read off the published per-property equations**, not
recalled: F'_b, F'_t, F'_v, F'_c⊥, F'_c, E' and E'_min each written out with their own
chain. A gate asserts the table is the published one and not an empty set — an emptied
table refuses every factor, and every refusal test in the file would still pass.

**The safe path is the record's.** `nds_adjusted_design_value` still multiplies whatever it
is handed, which is right for a caller composing a chain by hand and wrong for one who has
a record that says what the number is a value of.
