# AISI cold-formed steel (effective width, and the Direct Strength Method)

A cold-formed steel member is thin enough that its wide flat elements buckle
locally, well before the steel yields, and shed load from the middle to the stiff
edges. The AISI S100 effective-width method (Winter's formula) replaces the full
flat width with a reduced *effective* width that carries the edge stress uniformly.
That reduction is the calculation that sets cold-formed design apart from
hot-rolled: section properties must be computed on the effective section, not the
gross one.

## What you get

```python
from anvilate.analysis import aisi_effective_width, aisi_plate_slenderness
from anvilate.units import Quantity

lam = aisi_plate_slenderness(              # λ = (1.052/√k)·(w/t)·√(f/E)
    flat_width=Quantity.parse("100 mm"),
    thickness=Quantity.parse("1.5 mm"),
    stress=Quantity.parse("345 MPa"),      # the edge stress (at yield here)
    elastic_modulus=Quantity.parse("203000 MPa"),
)
b = aisi_effective_width(...)              # b = w if λ ≤ 0.673, else ρ·w, ρ = (1 − 0.22/λ)/λ
```

- **`aisi_plate_slenderness`** = λ, the dimensionless slenderness that decides whether
  an element is fully effective (λ ≤ 0.673) or sheds load.
- **`aisi_effective_width`** = the effective width b: the full width below the limit,
  and ρ·w above it. The plate-buckling coefficient k is caller-supplied — 4.0 for a
  stiffened element, 0.43 for an unstiffened one.

The yield strength and modulus are the caller's material inputs; Anvilate evaluates
Winter's formula. See
[`examples/cold_formed_stud_flange.py`](../examples/cold_formed_stud_flange.py) for a
flange that is 59% effective at 1.5 mm and fully effective at 3.5 mm.

## The Direct Strength Method (AISI S100 Appendix 1)

The effective-width method above reduces each element and rebuilds the section. DSM takes
the opposite route: it works from the *whole section's* elastic buckling loads — local,
distortional and global — and maps each to a strength with its own empirical curve. No
effective section at all, which is why it is the method for shapes the effective-width
rules do not cover.

### The elastic buckling values are not ours to invent

DSM's inputs are the section's elastic critical loads, and for a real cold-formed shape
they come from a finite-strip analysis (CUFSM and its kin) — not from a closed form.
Anvilate does not compute them and will not guess them:

```python
from anvilate.analysis import ElasticBuckling, dsm_compression_strength, dsm_scorecard

buckling = ElasticBuckling(
    local=Quantity.parse("120 kN"), distortional=Quantity.parse("155 kN"),
    global_=Quantity.parse("900 kN"),
    source="CUFSM v5.04 finite-strip signature curve, run 2026-08-17",
)
```

`source` is required and cannot be blank. A screen handed `strength=None` reports
`NOT_EVALUATED`, because a plausible capacity resting on a buckling load nobody ran is the
worst kind of silent green.

`distortional` may be `None` for a section with no distortional mode (an unlipped angle, a
round tube). That is a declaration, and it removes the mode from the governing set rather
than treating it as infinitely strong by accident.

### Three modes, three repairs

The reason `dsm_scorecard` reports the governing mode beside the number: they respond to
opposite changes. Here is one 200 × 75 × 20 × 2.0 lipped channel (P_y = 245 kN, P_crl =
120 kN, P_crd = 155 kN) at three unbraced lengths. Only P_cre moves with length — the
cross-section modes do not.

| Length | P_cre | Global | Local | Distortional | Nominal | Governs |
| --- | --- | --- | --- | --- | --- | --- |
| 1 m | 900 kN | 218.6 | 151.7 | 150.8 | **150.8 kN** | distortional |
| 3 m | 100 kN | 87.7 | 82.5 | 150.8 | **82.5 kN** | local |
| 6 m | 25 kN | 21.9 | 21.9 | 150.8 | **21.9 kN** | global |

A thicker web fixes the 1 m case and does nothing for the 6 m one; bracing fixes the 6 m
case and does nothing for the 1 m one. A bare capacity cannot tell a reader which.

**Why local strength falls with length when P_crl never moved:** the DSM local curve is
anchored on P_ne, the *global* strength, not on P_y. Local buckling interacts with the
global mode, so a longer column's local strength is measured against the load global
buckling already left it. The distortional curve is anchored on P_y instead, because that
mode does not interact — which is why its column above is constant. Getting those two
anchors the wrong way round is the classic DSM implementation error.

### Prequalified geometry is a third state, not a pass or a fail

DSM's curves were fitted to tested sections, and §1.1.1.1 lists the geometry each was
fitted over. A section outside those limits is not forbidden — AISI permits it with a more
conservative resistance factor. So `dsm_scorecard` **downgrades a PASS to
`NOT_EVALUATED`** and names which dimension took the section out:

```
[NOT_EVALUATED] outside the AISI S100 §1.1.1.1 prequalified geometry
(web h/t = 600 exceeds 472; lip/flange d/b = 0.05 outside [0.14, 0.87]) — the DSM
curves are not calibrated here and a more conservative resistance factor is required.
```

The downgrade only ever removes a green. A section that fails stays failed whether it is
prequalified or not.

### Scope

Screened: DSM compression (§1.2.1) and flexure (§1.2.2), all three modes each, plus the
prequalification check. Not screened: shear, web crippling, combined actions, connections,
and the elastic buckling analysis itself.

See [`examples/lipped_channel_dsm.py`](../examples/lipped_channel_dsm.py).
