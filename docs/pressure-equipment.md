# Pressure equipment screening (ASME VIII Div 1)

**Screening scope, not Code design.** These are UG-27, UG-32, UG-37 and the Appendix 2
bolt loads and ring-flange stress. They are not a U-stamp calculation: there is no
hub-flange stress analysis (see [below](#the-flange-stress-that-ships-and-the-one-that-does-not)), no
MDMT or impact-test assessment, no external-pressure or nozzle-load check, no fatigue
screening, and no fabrication or NDE requirements. A green scorecard means the pressure
arithmetic screens clean; it does not mean the vessel is Code-compliant, and it is not a
substitute for a Certified Individual.

With that said: the best open-source prior art for this is an Excel/VBA workbook. Formed
heads, opening reinforcement and flange bolt loads are closed-form, citable, and
recomputed in spreadsheets every day by the audience this library is for.

## The wall passes and the hole in it does not

The point of covering openings at all is that they fail on a different schedule from the
wall. The same 800 mm ID vessel at 2 MPa, at two shell thicknesses:

| Component | Built at 14 mm | Built at 8 mm |
| --- | --- | --- |
| Shell wall (UG-27) | PASS, SF 2.14 | PASS, SF 1.11 |
| 2:1 ellipsoidal head (UG-32) | PASS, SF 2.15 | PASS, SF 1.12 |
| 6 in nozzle opening (UG-37) | PASS, SF 1.66 | **FAIL, SF 0.49** |

The shell got 1.9× thinner and the opening got 3.4× worse. UG-37 credits the shell's
*excess* wall as reinforcement (A₁), and excess falls away far faster than thickness
does. A vessel trimmed to its pressure minimum has nothing left to reinforce its
openings with — and the opening is the component nobody re-checks after trimming a wall.
See [`examples/pressure_vessel_nozzle_and_flange.py`](../examples/pressure_vessel_nozzle_and_flange.py).

## What you get

| Function | Clause | What it gives |
| --- | --- | --- |
| `asme_cylinder_thickness` / `_mawp` | UG-27 | Shell wall and MAWP |
| `asme_ellipsoidal_head_thickness` / `_mawp` | UG-32(d) | Ellipsoidal head, with the K factor |
| `asme_torispherical_head_thickness` / `_mawp` | UG-32(e) | Torispherical head, with the M factor |
| `asme_conical_head_thickness` / `_mawp` | UG-32(g) | Conical section by half-apex angle |
| `asme_spherical_shell_thickness` / `_mawp` | UG-27(d) | Spherical shell |
| `asme_ug37_nozzle_reinforcement` | UG-37 | The opening area accounting, and the deficit a pad must supply |
| `asme_ug37_reinforcement_scorecard` | UG-37 | The same as a PASS/FAIL entry |
| `asme_appendix_2_gasket_geometry` | App. 2, Table 2-5.2 | Effective seating width `b` and diameter `G` |
| `asme_appendix_2_required_bolt_area` | App. 2 | `A_m = max(W_m1/S_b, W_m2/S_a)` |
| `gasket_seating_load` / `gasket_operating_load` | App. 2 | `W_m2` and `W_m1` from `m` and `y` |
| `asme_appendix_2_shape_factors` | App. 2-7.1 | `T`, `U`, `Y`, `Z` from `K = A/B` |
| `asme_appendix_2_flange_moments` | App. 2, Table 2-6 | Loose-type `M_o` and `M_a`, with every load and arm |
| `asme_appendix_2_ring_flange_stress` | App. 2-7(b) | `S_T = Y·M/(t²·B)` in both conditions |
| `asme_appendix_2_flange_stress_scorecard` | App. 2-7(b) | The same as a PASS/FAIL entry |

### The two Appendix 2 traps

**The effective seating width is not the basic one.** `b = b₀` only up to b₀ = 6.35 mm
(¼ in); above that `b = 2.52·√b₀`, because a wide gasket does not seat evenly across its
face. The diameter `G` moves with it — the gasket's mean diameter for a narrow gasket,
`OD − 2b` for a wide one, since the load has migrated to the outer edge. Using b₀ above
the limit overstates both bolt loads, and both stay plausible.

**The two loads are checked against two different allowables, and comparing the loads
alone gets the answer wrong.** The operating load is carried at temperature against
`S_b`; the seating load is applied cold against the ambient `S_a`.

In the worked example the seating load is 400.0 kN and the operating load 218.7 kN, so
the *loads* say seating governs. Divide each by its own allowable — 172 MPa cold,
60 MPa at 400 °C — and the required areas are 2,326 mm² and **3,645 mm²**: operating
governs, by 57%. The one-number form (larger load ÷ one allowable) returns 2,326 mm²,
**36% short of what Appendix 2 requires**, and names the wrong condition while doing it.

`asme_appendix_2_required_bolt_area` is the correct consumer.
`governing_gasket_bolt_load` takes the larger load with no allowables at all, and is
only equivalent when `S_a == S_b`.

## The flange stress that ships, and the one that does not

**Loose-type flanges without a hub are screened. Hub-credited flanges are not.** For the
no-hub case (Figure 2-4 sketches 1, 1a, 2, 2a, 3, 3a, 4, 4a, 4b, 4c, and optional-type
flanges calculated as loose) Appendix 2-7(b) sets `S_H = 0` and `S_R = 0`, so the single
tangential stress `S_T = Y·M_o/(t²·B)` is the whole check — closed-form, and shipped.

A welding-neck or any hub-credited flange runs on the `F`, `V` and `f` factors, which are
*figures* inside the Code, not equations. Implementing them from memory is exactly the
guess this library's citation contract exists to prevent, so
`asme_appendix_2_flange_stress_scorecard(..., stress=None, missing=...)` reports
NOT_EVALUATED naming what is missing, rather than reporting the no-hub number — which
would be unconservative, since a hub flange's moment arms come off the hub too. The
bolt-spacing correction `B_sc` and the Appendix 2 rigidity index are also out of scope,
and a flange can fail either while its stresses pass.

The `T`, `U`, `Y`, `Z` equations were **anchored before they were shipped**: a published
worked calculation at `K = 1.41939` reports `T = 1.74578` and `Z = 2.97106`, and these
give 1.745783 and 2.971062 — both round to the published figures exactly. `Y` and `U`
are tied by an identity that falls out of the published constants (`U = Y/0.910` at
every `K`), so reproducing one reproduces the other. All of it is asserted in the test suite.

### The flange sized by the bolt-up, not the pressure

A 200 mm bore ring flange at 2 MPa and 400 °C, on a 290 mm bolt circle with 16 M20 studs:

| Ring thickness | Operating `S_T` (vs 138 MPa hot) | Seating `S_T` (vs 172 MPa cold) | Verdict |
| --- | --- | --- | --- |
| 30 mm | 115 MPa — PASS, SF 1.20 | 235 MPa — **FAIL, SF 0.73** | FAIL |
| 40 mm | 65 MPa — PASS, SF 2.13 | 132 MPa — PASS, SF 1.30 | PASS |

Checked on pressure alone the 30 mm ring looks comfortable. It fails on a load with no
pressure in it: the joint needs 1,873 mm² of bolt and sixteen M20 studs supply 3,920 mm²,
and Appendix 2 charges the flange for that over-bolting through `W = (A_m + A_b)·S_a/2`.
The seating moment comes out double the operating one and loses even against the *higher*
ambient allowable. Choosing bolts by rounding the required area up is correct for the
bolts and pushes the flange the wrong way. See
[`examples/loose_ring_flange_stress.py`](../examples/loose_ring_flange_stress.py).

## What UG-37 here does not credit

The screen covers the **radial nozzle in a cylinder**, the case UG-37's F factor makes
1.0. It sums A₁ (excess shell), A₂ (excess nozzle) and A₄₁ (the attachment fillet). It
does **not** credit an inward-projecting nozzle (A₃) or a reinforcing pad (A₅) — supply
those separately if the design has them. A hillside or oblique nozzle opens a longer hole
and takes a different F, and is out of scope.

Allowable stresses follow the user-supplied-allowables doctrine: `S` at design
temperature, the gasket factors `m` and `y` from Table 2-5.1, and the bolt allowables are
all the caller's, read from the Code and recorded with their provenance. None of the
Code's tables are reproduced here.
