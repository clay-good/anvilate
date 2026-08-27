# Fitness-for-service fracture screening (SIF, reference stress, FAD)

**What this produces is a screening margin, not a fitness-for-service disposition.**
Deciding that a flawed component may stay in service is a qualified assessor's call under
the full assessment code, with the residual stresses, weld metal properties and
inspection uncertainty this screen does not have. Nothing here says "fit for continued
service" and nothing here should be quoted as though it did.

With that said: crack-like flaw assessment is split between expensive seat-licensed
suites and field spreadsheets, and there is no maintained open-source implementation in
Python. The math is license-clean when framed correctly — the handbook stress-intensity
solutions are NASA public-domain reports, and the Level-2 failure assessment curve is the
BS 7910 / R6 expression that is everywhere in the open literature.

## Why a toughness check alone is not enough

A flawed component fails by brittle fracture at one extreme and by plastic collapse of
the remaining ligament at the other. Near the middle it fails by an interaction that
neither limit predicts on its own. The failure assessment diagram combines them:

- **K_r = K_I / K_mat** — how much of the toughness the flaw uses.
- **L_r = σ_ref / σ_y** — how much of the collapse load the ligament uses.

One curve separates acceptable from not. The number that matters is the **load-line
margin**: the factor by which the primary load can be scaled before the point reaches the
curve. It is *not* 1/K_r, because scaling the load raises L_r as well and the curve bends
down. In the worked example K_r = 0.367 would suggest 2.73 in hand; the real margin
is 1.71.

## What you get

| Function | Source | What it gives |
| --- | --- | --- |
| `SurfaceFlaw` | Newman & Raju | The flaw geometry, plus `outside_validity()` naming every limit it breaks |
| `newman_raju_surface_flaw_sif` | NASA TM 85793 (1984) | K_I for a semi-elliptical surface flaw in a plate, tension and bending, at any point on the flaw front |
| `surface_flaw_reference_stress` | BS 7910 Annex P | The local-collapse reference stress of the remaining ligament |
| `fad_option1_curve` | BS 7910 / R6 Option 1 | f(L_r), the acceptable K_r at a given L_r |
| `fad_limit_load_ratio` | BS 7910 | L_r,max = (σ_y + σ_u)/(2σ_y), where the diagram stops |
| `charpy_toughness_estimate` | Rolfe-Novak-Barsom | An **estimate** of K_IC from upper-shelf Charpy energy |
| `fad_assessment` / `fad_scorecard` | all of the above | The assessment point, the load-line margin, and a verdict that says it is a screen |

## The validity range is enforced, not noted

The Newman & Raju equations are a fit to finite-element results over a stated range, and
past a/c = 1 the published solution uses a **different coefficient set** — not an
extrapolation of this one. So a flaw longer than it is deep raises, naming the limit,
rather than returning a plausible number off the wrong fit:

```python
long_flaw = SurfaceFlaw(depth=q("4 mm"), half_length=q("2 mm"), thickness=q("20 mm"))
long_flaw.outside_validity()
# ('a/c = 2 outside (0, 1]; a flaw longer than it is deep takes the a/c > 1 ...',)
```

The library's tests anchor the solution against its own limiting case: for a semi-circular
flaw in a wide plate it must land within about 0.1% of 1.04·(2/π)·σ√(πa) at the deepest
point — the embedded penny-shaped crack times the free-surface magnification — and of
0.728·σ√(πa) at the surface point. Both are approximations to the Newman–Raju fit rather
than identities it satisfies exactly (0.66254 against 0.66208, and 0.72880), which is why
the suite asserts them at 2e-3 and this page says "about".

The reference stress is checked the same way: strip the bending term and it must be the
plain net-section stress; strip the flaw and apply pure bending and it must give
two-thirds of the elastic bending stress, which is first yield over a fully plastic hinge.

## An estimated toughness never reports a plain pass

`charpy_toughness_estimate` is a correlation, and it scatters. A `fad_scorecard` built on
one is downgraded from PASS to NOT_EVALUATED:

```
service pressure, measured K_IC      pass           margin 1.71
overpressure, measured K_IC          fail           margin 0.79
service pressure, Charpy estimate    not_evaluated  margin   —
```

Same numbers in the third row as the first — only the provenance differs. A pass built on
a correlation is a reason to commission a toughness test, not a result. See
[`examples/vessel_surface_flaw_fad.py`](../examples/vessel_surface_flaw_fad.py).

## Explicitly out of scope

API 579 Part 9 Level-1 screening curves and the brittle-fracture exemption curves are
figures inside a copyrighted standard and are not reproduced. Weld residual stress
profiles beyond user-supplied values, and any plasticity correction ρ, are not applied.
