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

## Examples

- [`examples/floor_joist_wet_service.py`](../examples/floor_joist_wet_service.py) — a
  joist that passes dry and fails wet; the wet-service factor C_M is the whole
  difference.
- [`examples/timber_header_bearing_governs.py`](../examples/timber_header_bearing_governs.py)
  — a 3.5 ft header whose bending (SF 1.25) and shear (1.14) both pass while the
  bearing on a 1.5 in wall plate crushes at 0.96. Landing it on a 3.5 in post takes
  bearing to 2.24 and leaves the other two untouched: the repair is the detail, not a
  deeper beam.
