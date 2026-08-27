# NDS timber screening (the adjusted design value)

An NDS timber check screens a member's stress not against the raw tabulated
strength but against the *adjusted* design value: the reference value from the
species/grade tables, multiplied by a chain of adjustment factors for the real
service conditions. Anvilate composes the chain and keeps every factor visible; the
reference design values are the caller's, from the copyrighted NDS tables.

## Scope, and what it is not

**What is screened.** Sawn-lumber members under the allowable-stress design of the
NDS: bending (§3.3), horizontal shear (§3.4), compression parallel to grain with the
column stability factor (§3.7), bearing perpendicular to grain (§3.10), and the
combined bending-plus-axial interaction (§3.9.2). Each is a closed-form screen against
an adjusted design value you supply the reference for.

**What is not.** Connections (bolts, nails, screws, shear plates — NDS Chapters 11-13),
glulam and cross-laminated timber specifics, fire design, deflection and vibration
serviceability, the size factor C_F and the glulam volume factor C_V as derivations, and
any diaphragm or shear-wall system behaviour. Those factors can still enter through the
caller's chain; Anvilate just does not derive them. **The beam stability factor C_L is
derived now** (§3.3.3) — see below; the Table 3.3.3 conversion from an unbraced length to
an effective length l_e stays the caller's, because it depends on where the load acts and
how the compression edge is held, neither of which a section knows.

**Where the reference values come from.** The NDS species/grade design value tables are
copyrighted, and Anvilate does not republish them. Every reference value — F_b, F_v,
F_c, F_c⊥, E, E_min — enters as a `Quantity` you pass in, from your copy of the NDS
Supplement or the grading agency's published values. The one exception is the load
duration factor C_D (Table 2.3.2), a six-value list republished everywhere, which
`nds_load_duration_factor` provides. Adjustment factors that depend on the member's
size, moisture, temperature, or treatment are likewise yours to look up and pass in by
name, which is why the factor chain is a name→value mapping rather than a black box.

**Screening disclaimer.** These are T1 analytical screens for early design, not a
substitute for a full code check by a licensed engineer. A screen that passes has
passed the limit states listed above with the values you supplied; it says nothing
about the ones not listed, and nothing about whether the values were the right ones.
Anvilate is built so a green is never silent — an unsupplied reference value returns
`NOT_EVALUATED`, and a member past a documented limit (the §3.7.1.4 slenderness cap,
for one) raises rather than quoting a plausible number — but the responsible-charge
review is still a person's.

## What you get

```python
from anvilate.analysis import (
    LoadDuration, nds_adjusted_design_value, nds_bending_scorecard, nds_load_duration_factor,
)
from anvilate.units import Quantity

adjusted = nds_adjusted_design_value(
    reference_value=Quantity.parse("900 psi"),          # F_b for the species/grade (yours)
    factors={
        "C_D": nds_load_duration_factor(LoadDuration.TEN_YEAR),  # load duration
        "C_F": 1.1,                                             # size factor
        "C_r": 1.15,                                            # repetitive member
        "C_M": 0.85,                                            # wet service
    },
)
entry = nds_bending_scorecard("joist bending",
                              bending_stress=Quantity.parse("1000 psi"),
                              adjusted_bending_value=adjusted)
```

- **`nds_load_duration_factor`** returns the NDS Table 2.3.2 factor C_D — the one
  factor with a short, universally-republished set of values (0.9 permanent, 1.0
  ten-year, 1.15 snow, 1.25 construction, 1.6 wind/earthquake, 2.0 impact). Every
  other factor is caller-supplied from the NDS tables.
- **`nds_adjusted_design_value`** = F · ∏ Cᵢ, with the factors keyed by name so the
  record shows which factor moved the value.
- **`nds_bending_scorecard`** screens the applied bending stress against the adjusted
  value. With no reference value it is `NOT_EVALUATED`, never a silent pass — the
  species/grade value is yours to provide.

## Shear and bearing — the checks short spans fail

Bending demand falls with L², shear with L, and the bearing stress at the support does
not fall at all: the reaction still passes through the same contact patch. Sizing a
short, heavily loaded member by bending alone misses both.

```python
from anvilate.analysis import (
    nds_bearing_area_factor, nds_bearing_scorecard, nds_bearing_stress,
    nds_shear_scorecard, nds_shear_stress,
)

f_v = nds_shear_stress(shear_force=reaction, width=b, depth=d)     # 1.5*V/(b*d)
f_c = nds_bearing_stress(bearing_force=reaction, width=b, bearing_length=l_b)  # P/(b*l_b)
```

- **`nds_shear_stress`** is the NDS §3.4.2 horizontal shear f_v = 1.5·V/(b·d) — the
  neutral-axis peak, 1.5× the average V/A, parallel to the grain.
- **`nds_bearing_stress`** is the NDS §3.10.2 compression perpendicular to grain
  f_c⊥ = P/(b·l_b). Wood is far weaker across the grain than along it, so a member
  that passes bending and shear can still crush where it lands.
- **`nds_bearing_area_factor`** is the §3.10.4 C_b = (l_b + 0.375 in)/l_b, the bonus a
  short bearing gets from the fibres just past its ends. It applies only below 6 in of
  bearing and at least 3 in from the member end — pass `end_distance` and a bearing
  nearer the end correctly gets C_b = 1.0. Note the bearing chain omits C_D: NDS §2.3.2
  does not apply load duration to compression perpendicular to grain.
- **`nds_shear_scorecard`** and **`nds_bearing_scorecard`** screen those stresses
  against their adjusted values, and return `NOT_EVALUATED` without one, like bending.

## The reference value is a record, and the chain it takes is the standard's

`TimberDesignValue` ([`anvilate.standards.timber`](../src/anvilate/standards/timber.py))
carries the number with the four things that decide whether it applies here:

```python
TimberDesignValue(
    standard="NDS", edition="2018", table="Table 4A",
    species="Douglas Fir-Larch", grade="No. 2",
    size_classification=SizeClassification.DIMENSION_LUMBER,
    property=TimberProperty.BENDING, value=Quantity.parse("900 psi"),
).adjusted({"C_D": 1.15, "C_F": 1.1})
```

- **Which property it is.** F_b, F_t, F_v, F_c, F_c⊥, E and E_min are seven different
  numbers for the same piece of wood, and a stress and a modulus are both `[pressure]` —
  which is exactly why the property is declared rather than inferred from the unit.
- **Species and grade**, because Southern Pine No. 2 and Douglas Fir-Larch No. 2 are
  different values from different tables.
- **The size classification.** Dimension lumber, beams and stringers, and posts and
  timbers are graded to different rules and the size factor works differently for each.
- **The standard and edition**, because reference values move between them.

**`adjusted()` enforces NDS Table 4.3.1.** The page above has always said the caller
"simply omits" the factors that do not apply — a rule stated in prose and enforced by
nobody. Now a factor the table does not list for that property is refused, naming both:

| Value | Factors NDS Table 4.3.1 lists |
| --- | --- |
| F_b | C_D, C_M, C_t, C_L, C_F, C_fu, C_i, C_r |
| F_t | C_D, C_M, C_t, C_F, C_i |
| F_v | C_D, C_M, C_t, C_i |
| F_c⊥ | C_M, C_t, C_i, C_b |
| F_c | C_D, C_M, C_t, C_F, C_i, C_P |
| E | C_M, C_t, C_i |
| E_min | C_M, C_t, C_i, C_T |

The two absences that catch people: **C_D applies to neither modulus nor to F_c⊥**, and
**C_F applies to neither modulus nor to F_v**. Applying C_D to a modulus at a snow load is
a beam 15% stiffer than the standard allows, on exactly the deflection check that usually
governs a timber beam — so the mistake shows up as a member passing the check it was about
to fail.

`nds_adjusted_design_value` still multiplies whatever it is handed, which is right for a
caller composing a chain by hand. The record is the path that checks.

## Bending — the beam stability factor, and the coefficient that is not the column's

```python
from anvilate.analysis import (
    nds_beam_slenderness_ratio, nds_bending_buckling_stress, nds_beam_stability_factor,
)

r_b = nds_beam_slenderness_ratio(effective_length=l_e, depth=d, breadth=b)
f_bE = nds_bending_buckling_stress(min_modulus=e_min, slenderness_ratio=r_b)
c_l = nds_beam_stability_factor(buckling_stress=f_bE, reference_bending_value=f_b_star)
```

- **`nds_beam_slenderness_ratio`** is R_B = √(l_e·d/b²) (§3.3.3.6). It refuses past the
  §3.3.3.7 cap of 50. There is **no construction-stage relief** here, unlike the column's
  §3.7.1.4 cap which tolerates 75 while a frame goes up — the asymmetry is the standard's,
  not an omission.
- **`nds_bending_buckling_stress`** is F_bE = **1.20**·E'_min/R_B². The column's Euler
  stress uses **0.822** in the identical shape, and swapping them understates the beam's
  buckling stress by a third.
- **`nds_beam_stability_factor`** is C_L = (1+x)/1.9 − √([(1+x)/1.9]² − x/0.95) with
  x = F_bE/F_b*. The 1.9 and 0.95 are fixed; the column's C_P uses 2c and c, where c
  varies by product (0.8 sawn, 0.9 glulam). Not interchangeable.

**Pass F_b*, not F'_b.** F_b* is the reference bending value with every adjustment applied
*except* C_L itself (and except C_V for glulam). Passing the fully adjusted value — the
number a design summary reports — inflates the denominator's job, and because C_L rises
with x that returns a stability factor **larger** than the beam has. The unconservative
direction, and pinned as such.

C_L rises monotonically with x and approaches but never reaches 1. Both are swept in the
tests over 5,000 ratios rather than argued from the shape of the formula.

## Compression — where the column stability factor enters

```python
from anvilate.analysis import (
    nds_column_stability_factor, nds_compression_scorecard, nds_euler_buckling_stress,
)

f_cE = nds_euler_buckling_stress(min_modulus=e_min, slenderness_ratio=le_over_d)
c_p = nds_column_stability_factor(euler_buckling_stress=f_cE, reference_compression=f_star_c)
```

- **`nds_euler_buckling_stress`** is F_cE = 0.822·E'_min/(l_e/d)². It refuses past the
  NDS §3.7.1.4 slenderness cap — 50 in service, or 75 with `during_construction=True` —
  because the formula would otherwise return a small, entirely plausible stress for a
  column the standard does not permit.
- **`nds_column_stability_factor`** is the Ylinen C_P of §3.7.1, taking F*_c (every
  factor except C_P) to F'_c = F*_c·C_P. It falls fast: an 8 ft 4x4 sits at 0.41, the
  same post at 12 ft at 0.20.
- **`nds_compression_scorecard`** screens the applied f_c against F'_c, `NOT_EVALUATED`
  without a reference value.
- **`nds_combined_bending_compression`** is the §3.9.2 beam-column interaction
  (f_c/F'_c)² + f_b/[F'_b(1 − f_c/F_cE)] ≤ 1, with the moment-amplification denominator
  guarded against a member that has already buckled.

## Examples

- [`examples/timber_beam_lateral_stability.py`](../examples/timber_beam_lateral_stability.py)
  — a 2x12 rafter with 42% in hand on bending stress and C_L = 0.402 unbraced: it
  fails at 0.57, still fails at 0.97 with one strut at midspan, and passes at 1.18
  braced at the third points. Handing C_L the fully adjusted F'_b instead of F_b*
  returns 0.830 on that same rafter.

- [`examples/timber_post_slenderness.py`](../examples/timber_post_slenderness.py) — the
  same 4x4 under the same 4,000 lb passes at 8 ft (SF 1.70) and fails at 12 ft (0.82);
  at 16 ft the §3.7.1.4 cap makes the screen refuse outright.
- [`examples/floor_joist_wet_service.py`](../examples/floor_joist_wet_service.py) — a
  joist that passes dry and fails wet; the wet-service factor C_M is the whole
  difference.
- [`examples/timber_header_bearing_governs.py`](../examples/timber_header_bearing_governs.py)
  — a 3.5 ft header whose bending (SF 1.25) and shear (1.14) both pass while the
  bearing on a 1.5 in wall plate crushes at 0.96. Landing it on a 3.5 in post takes
  bearing to 2.24 and leaves the other two untouched: the repair is the detail, not a
  deeper beam.

## Worked-example anchors

Four textbook problems are pinned end to end in `tests/test_analysis.py` against numbers
worked by hand, not re-derived from the code — three of them as `test_nds_worked_example_*`
and the beam-stability chain across the `test_nds_beam_*` tests. They are the pack's
regression floor, and each carries a lesson:

| Anchor | Problem | Result | What it pins |
| --- | --- | --- | --- |
| Floor joist | 2x10, 15 ft, 16 in o.c., 50 psf | bending SF 1.08, shear SF 3.33 | On a long span bending governs, and tightly — the "passing" joist has 8% in hand. |
| Post | 6x6, 12 ft, 12,000 lb | compression SF 1.40, bearing SF 1.58 | C_P is the design: skipping it reports 2.52 on the same post. |
| Beam stability | l_e 213 in, 28.5 x 6.75 in, E'_min 850,000 psi | R_B 11.54, F_bE 7,659 psi, C_L 0.974 | One self-consistent published example fixes every constant in the chain, including the 1.20 that is not the column's 0.822. |
| Beam-column | the same post plus 30 plf of wind | interaction 0.79 | Wind's C_D 1.6 lifts F*_c by 60% but F'_c by only 11% — a higher F*_c lowers C_P, so the duration bonus does not arrive intact. |
