# Reinforced-concrete flexure (ACI 318)

A reinforced-concrete beam carries bending as a composite: the concrete takes
compression in a rectangular stress block of intensity 0.85·f'c, and the steel takes
tension at yield. The whole of flexural RC design turns on the nominal moment
M_n = A_s·f_y·(d − a/2) and its inverse.

## What you get

```python
from anvilate.analysis import rc_beam_nominal_moment, rc_tension_steel_for_moment
from anvilate.units import Quantity

mn = rc_beam_nominal_moment(
    steel_area=Quantity.parse("1500 mm**2"),
    steel_yield=Quantity.parse("420 MPa"),
    concrete_strength=Quantity.parse("30 MPa"),
    beam_width=Quantity.parse("300 mm"),
    effective_depth=Quantity.parse("550 mm"),
)                                              # 320.6 kN·m
As = rc_tension_steel_for_moment(
    required_moment=Quantity.parse("400 kN*m"),
    steel_yield=Quantity.parse("420 MPa"),
    concrete_strength=Quantity.parse("30 MPa"),
    beam_width=Quantity.parse("300 mm"),
    effective_depth=Quantity.parse("550 mm"),
)                                              # 1915 mm²
```

- **`rc_stress_block_depth`** = A_s·f_y/(0.85·f'c·b), the Whitney block depth from
  force balance.
- **`rc_beam_nominal_moment`** = A_s·f_y·(d − a/2), the ACI 318 §22.3 nominal flexural
  strength of a singly-reinforced section. The design strength is φ·M_n (φ = 0.90 for
  a tension-controlled section).
- **`rc_tension_steel_for_moment`** — the design inverse: the least (under-reinforced)
  steel a required moment needs, rejecting a demand beyond the section's capacity.

The concrete and steel strengths are your inputs; Anvilate evaluates the closed form.
The tension-controlled ductility check and the φ factor are yours to apply. See
[`examples/rc_floor_beam.py`](../examples/rc_floor_beam.py).
