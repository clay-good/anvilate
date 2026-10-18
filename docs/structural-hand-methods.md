# Structural hand methods

**The lightweight-structures checks an aerospace stress report is built from, each read from
a public-domain primary document and pinned to it.** These are analysis-library functions:
they return numbers, and [margins of safety](margin-of-safety.md) turns them into a review
table under a cited factor set.

| Module | What it gives you | Function to start with |
| --- | --- | --- |
| `laminate` | A ply stack's ABD matrix, each ply's strains and stresses under running loads, and first-ply failure by maximum stress, maximum strain and Tsai-Wu | `laminate_response`, then `first_ply_failure` |
| `random_vibration` | A breakpoint spectrum's overall Grms, Miles' response at a mount's natural frequency, the 3σ load, and its combination with a quasi-static load | `random_vibration_load` |
| `preloaded_joint` | NASA-STD-5020B preload bounds from the tightening method, separation, ultimate and yield margins with separation-before-rupture decided, and slip | `preload_bounds`, then `preloaded_joint_margins` |
| `crippling` | Gerard's closed-form crippling stress of formed and extruded thin-walled sections, by their corners and flanges | `gerard_crippling_stress` |
| `plasticity` | A Ramberg-Osgood curve fitted at F_0.7 and F_0.85, and the plasticity-corrected column and plate buckling stresses | `RambergOsgood.from_secant_points`, then `plastic_plate_buckling_stress` |
| `shell_buckling` | The NASA SP-8007 knockdown for a thin cylinder in axial compression or bending, and the knocked-down buckling stress | `cylinder_design_buckling_stress` |

## What each one refuses, and why

- **A laminate with some strengths but not all five.** A criterion run on four would read
  the fifth as infinite. Strengths also need the basis they were declared on, and every
  verdict names it. A lamina with no strengths gives stresses and "not evaluated", never a
  pass.
- **A natural frequency outside the declared spectrum.** The spectrum states no level
  there, and extrapolating a slope past its last breakpoint is a guess. Q is required:
  the load grows with √Q, so a default would be an assumption about someone else's mount.
- **A default preload uncertainty for a separation-critical joint.** NASA-STD-5020B Table 3
  gives defaults only for joints that are not separation-critical. A separation-critical
  joint needs torque-tension tests, and gets the envelope of their 90/95 and measured
  variation. Friction above 0.2 on cleaned uncoated metal, or 0.1 on anything else, is
  refused too: the standard does not credit more without a test. There is no default
  load-introduction factor either, because the standard gives none.
- **A crippling ratio above its form's cutoff.** Above the cutoff the section fails at its
  elements' local buckling stress, which this screen does not compute, so it refuses
  rather than extrapolate. The cutoff for a Z or a channel rises with β, so hardened
  corners can bring a section back inside it.
- **A plastic Poisson ratio the caller did not declare.** The manual gives no formula for
  it, so when it is left out the result says it was taken equal to the elastic value.
- **r/t of 1500 or more for the SP-8007 knockdown.** The knockdown's φ is defined only
  below 1500. A wall too thick for shell buckling (r/t below 10) is refused by the
  classical formula first.

## Where each number was checked

Every source below was read on 2026-10-17 from the document itself.

| Check | Source | How it is pinned |
| --- | --- | --- |
| Lamina and laminate stiffness | [NASA RP-1351](https://ntrs.nasa.gov/citations/19950009349) (Nettles, 1994), Examples 1 and 2 | Q, Q̄ at +45°, A and Ex of [0/+45]s, and B and D of [0/+45]T, to the printed figures. RP-1351 rounds ν₂₁ to 0.02 where the reciprocal value is 0.0195, which moves Q₁₁ by 0.015%. |
| Laminate stiffness, a second source | [NASA TM X-73305](https://ntrs.nasa.gov/citations/19760071127) §F1, Example 1 | A and B exactly. D to the hand calculation. The manual prints D₁₁ as 65,220 where the exact figure is 65,500, because it rounds a coefficient. |
| Ply stresses | RP-1351 Examples 3 and 6 | Mid-plane strains, curvatures, and ply stresses, held against the exact recomputation. The printed stresses come from strains rounded to three figures. |
| Failure criteria | none worked in either source | Under a single stress component, each criterion has to fail at exactly that component's strength. For Tsai-Wu, that is the root of F₁σ + F₁₁σ² = 1. |
| Spectrum integration | [GSFC-STD-7000B](https://standards.nasa.gov/standard/GSFC/GSFC-STD-7000) Tables 2.4-3 and 2.4-4 | The overall levels the tables print for their own spectra: 14.1, 10.0, 6.8 and 4.4 Grms. |
| Preload uncertainty | [NASA-STD-5020B](https://standards.nasa.gov/standard/NASA/NASA-STD-5020), approved 2021-08-06 and revalidated without change 2026-01-05, Appendix A.2 | Its 30 measured preloads (Table 6) reduce to the printed 4,721 lb nominal, 1,097 lb σ and Γ90/95 0.498, and it chooses Γ 0.353 for a joint that is not separation-critical. Three slips in the standard are recorded in the module so nobody corrects toward them. |
| Joint margins | NASA-STD-5020B Eqs. 1–19 and 86 | The standard works no margin example. Each margin is a hand calculation with every intermediate stated. |
| Crippling | [NACA TN 3784](https://ntrs.nasa.gov/citations/19930084522) (Gerard, 1957), Tables 13–15 and eqs. A6, A7 and 61 | TN 3784 works no full example. It restates three of its general forms for a specific section, and the code reproduces each one: the formed angle (eq. 54), the square tube (eq. 51) and the two-corner cutoff (A8). The Astronautic Structures Manual's element method is not used, because its allowable exists only as a chart. |
| Plasticity correction | [NASA TM X-73306](https://ntrs.nasa.gov/citations/19760071126) §C2, Eq. 2 and Figs. C2-10, C2-11 | The manual prints its Ramberg-Osgood equation without the 3/7 its own definitions need: printed as is, the secant modulus at F_0.7 is 0.5E, not 0.7E. The curve here passes through both secant points exactly. The tangent modulus is checked against a numerical derivative, and each buckling stress against the equation it solves. |
| Thin-cylinder knockdown | [NASA SP-8007](https://ntrs.nasa.gov/citations/19690013955) (1968) Eqs. 4–6 and 9, retained in [NASA/SP-8007-2020/REV 2](https://ntrs.nasa.gov/citations/20205011530) as its Empirical Approach | Neither edition works an example. The printed equations are evaluated by hand, and checked against Rev 2's Figure 4-2 restatement. |

Not yet built from this change: lugs, fastener groups, sandwich panels, and the
fracture-control helper.
