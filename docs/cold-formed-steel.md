# AISI cold-formed steel (effective width)

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
