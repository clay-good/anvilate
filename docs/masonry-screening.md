# Masonry screening (TMS 402 allowable stress)

A masonry wall or pier — concrete block or clay brick, grouted and often reinforced —
is designed to TMS 402 by allowable-stress rules, and its compression members are
governed as much by *slenderness* as by strength: a wall buckles, so the allowable
axial stress carries a reduction on the height-to-radius-of-gyration ratio h/r. The
masonry pack computes those allowables and the combined-stress check; the specified
masonry strength f'm (from the unit-strength or prism method) is the caller's.

## What you get

```python
from anvilate.analysis import (
    masonry_allowable_axial_stress, masonry_allowable_flexural_stress,
    masonry_combined_stress_ratio,
)
from anvilate.units import Quantity

fa = masonry_allowable_axial_stress(
    masonry_strength=Quantity.parse("10 MPa"), slenderness_ratio=40,   # h/r
)                                                                       # F_a, derated
fb = masonry_allowable_flexural_stress(masonry_strength=Quantity.parse("10 MPa"))  # 0.45*f'm
unity = masonry_combined_stress_ratio(
    axial_stress=Quantity.parse("1.2 MPa"), allowable_axial_stress=fa,
    flexural_stress=Quantity.parse("2.2 MPa"), allowable_flexural_stress=fb,
)                                                                       # f_a/F_a + f_b/F_b
```

- **`masonry_allowable_axial_stress`** — the TMS 402 §8.2.4 allowable axial stress,
  `0.25·f'm·[1 − (h/140r)²]` up to h/r = 99 and `0.25·f'm·(70r/h)²` beyond, the two
  branches meeting at 99. Multiply by the net (grouted) area for the allowable force.
- **`masonry_column_axial_capacity`** — the reinforced-column allowable load
  `(0.25·f'm·A_n + 0.65·A_st·F_s)` times the slenderness factor.
- **`masonry_allowable_flexural_stress`** — the flexural compressive allowable `0.45·f'm`.
- **`masonry_combined_stress_ratio`** — the unity check `f_a/F_a + f_b/F_b ≤ 1` that
  governs a wall under simultaneous gravity and out-of-plane wind, not either stress alone.

See [`examples/masonry_wall_slenderness.py`](../examples/masonry_wall_slenderness.py) —
a wall whose gravity utilization is a comfortable 0.52 but whose combined ratio climbs
past 1.0 once the wind bending is added.
