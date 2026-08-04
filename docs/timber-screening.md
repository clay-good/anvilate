# NDS timber screening (the adjusted design value)

An NDS timber check screens a member's stress not against the raw tabulated
strength but against the *adjusted* design value: the reference value from the
species/grade tables, multiplied by a chain of adjustment factors for the real
service conditions. Anvilate composes the chain and keeps every factor visible; the
reference design values are the caller's, from the copyrighted NDS tables.

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

See [`examples/floor_joist_wet_service.py`](../examples/floor_joist_wet_service.py) for
a joist that passes dry and fails wet — the wet-service factor C_M is the whole
difference.
