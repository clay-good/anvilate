# AISC 360 hot-rolled steel design

Anvilate screens a hot-rolled steel member and its connections against the AISC 360
limit states — the same checks a steel design spreadsheet runs, each as a small,
unit-checked function you compose yourself. Strengths are *nominal* (`R_n`, `M_n`,
`V_n`, `P_n`); apply your own LRFD φ or ASD Ω. Material and section properties
(F_y, F_u, Z, S, r_y, J, …) are your inputs, the way a code allowable always is.

## Members

**Flexure** — the moment a beam carries, by section and axis:

- I-shape strong-axis: the plastic-bracing limit `aisc_plastic_bracing_limit` (L_p),
  the inelastic-LTB limit `aisc_inelastic_ltb_limit` (L_r), the inelastic-LTB moment
  `aisc_inelastic_ltb_moment` between them, and the elastic
  `lateral_torsional_buckling_moment` beyond — the whole L_p → L_r → elastic curve.
- I-shape minor-axis: `aisc_minor_axis_flexural_strength` (§F6).
- Round HSS / pipe: `aisc_round_hss_flexural_strength` (§F8).
- Rectangular HSS / box: `aisc_rectangular_hss_flexural_strength` (§F7).
- Slender-web plate girders: `aisc_plate_girder_bending_factor` (§F5 R_pg) and
  `aisc_plate_girder_flange_stress` (F_cr) give M_n = R_pg·F_cr·S_xc.

**Shear** — the web check for each section:
`aisc_web_shear_strength` (I-shape §G2.1), `aisc_round_hss_shear_strength` (§G4),
`aisc_rectangular_hss_shear_strength` (§G5), and `aisc_tension_field_shear_strength`
(§G2.2 stiffened-web tension-field action).

**Concentrated loads** — the web under a bearing reaction:
`aisc_web_local_yielding_strength` (§J10.2), `aisc_web_crippling_strength` (§J10.3),
and `aisc_web_compression_buckling_strength` (§J10.5), with the sizing inverse
`aisc_bearing_length_for_web_yielding`.

**Combined** — `aisc_beam_column_interaction` (§H1.1, uniaxial or biaxial), and the
column curve `aisc_flexural_buckling_stress` (§E3).

## Connections

**Bolts**: `bolt_shear_strength` (§J3.6), `bolt_bearing_strength` (§J3.10 bearing /
tear-out), `slip_critical_resistance` (§J3.8), and `block_shear_strength` (§J4.3).
For a tension member's effective net area, `net_width_staggered_holes` (§B4.3b s²/4g)
and `shear_lag_factor` (§D3 U).

**Welds**: `fillet_weld_design_strength` (§J2.4 weld metal),
`fillet_weld_directional_strength` (the sin θ increase), and
`weld_base_metal_shear_strength` (§J4.2) — a weld is the lesser of the two.

**Base plates**: `base_plate_thickness_for_bearing` (Design Guide 1).

## Worked examples

- [`beam_bearing_web_checks.py`](../examples/beam_bearing_web_checks.py) — web yielding
  vs crippling at an end bearing; the lesser governs.
- [`hss_beam_flexure_shear.py`](../examples/hss_beam_flexure_shear.py) — a noncompact
  HSS flange voids the naive plastic moment.
- [`bolted_tension_splice.py`](../examples/bolted_tension_splice.py) — block shear
  governs a splice the member checks pass.
- [`plate_girder_design.py`](../examples/plate_girder_design.py) — the slender web docks
  bending yet, stiffened, nearly doubles the shear.
