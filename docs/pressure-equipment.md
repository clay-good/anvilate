# Pressure equipment screening (ASME VIII Div 1)

**Screening scope, not Code design.** These are UG-27, UG-32, UG-37 and the Appendix 2
bolt loads. They are not a U-stamp calculation: there is no flange stress analysis, no
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
