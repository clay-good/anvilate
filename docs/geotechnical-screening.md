# Geotechnical screening (foundations, walls, and seepage)

The geotechnical pack carries the closed forms under almost every foundation and
retaining structure — the ones an engineer would otherwise run in a spreadsheet
before a settlement analysis or a slope-stability program. Every function is
dimension-checked and hand-verified; the soil parameters (friction angle, cohesion,
unit weight, permeability) are the caller's, from the site investigation.

## Lateral earth pressure

```python
from anvilate.analysis import rankine_earth_pressure_coefficient, rankine_lateral_thrust
from anvilate.units import Quantity

ka = rankine_earth_pressure_coefficient(friction_angle=30)          # 0.333 (active)
thrust = rankine_lateral_thrust(
    unit_weight=Quantity.parse("18 kN/m**3"),
    height=Quantity.parse("4 m"),
    friction_angle=30,
)                                                                    # 48 kN/m, acting at H/3
```

- **`rankine_earth_pressure_coefficient`** — the active `tan²(45−φ/2)` or passive
  `tan²(45+φ/2)` coefficient for level cohesionless backfill.
- **`rankine_lateral_thrust`** — the resultant `½·K·γ·H²` (plus a `K·q·H` surcharge
  rectangle) on a wall, per unit length.

## Bearing capacity — the general equation

The Terzaghi factors are the strip base; the Vesić shape/depth and Meyerhof
inclination factors correct them for a real rectangular, embedded, obliquely-loaded
footing (`q_ult = Σ term · N · s · d · i`).

- **`bearing_capacity_factors`** — `N_c`, `N_q`, `N_γ` from the friction angle
  (Reissner/Prandtl/Vesić, with the φ→0 limit `N_c = π+2`).
- **`terzaghi_bearing_capacity`** — `c·N_c + q·N_q + ½·γ·B·N_γ`, the strip ultimate
  pressure. Divide by ~3 for the allowable.
- **`bearing_shape_factors`** / **`bearing_depth_factors`** / **`bearing_inclination_factors`**
  — the corrections a square footing (stronger), embedment (stronger), and a horizontal
  thrust (weaker) apply to each term.

See [`examples/strip_footing_bearing.py`](../examples/strip_footing_bearing.py),
[`examples/square_footing_shape_depth.py`](../examples/square_footing_shape_depth.py),
and [`examples/inclined_load_footing.py`](../examples/inclined_load_footing.py).

## Settlement — the serviceability half

- **`vertical_stress_increase_2to1`** — the `q₀·B·L/[(B+z)(L+z)]` spread that gives the
  stress increment Δσ below a footing.
- **`consolidation_settlement`** — the primary settlement `(C·H/(1+e₀))·log₁₀(σ_f/σ₀)`,
  handling the normally-consolidated, recompression, and preconsolidation-crossing cases.
- **`consolidation_time_factor`** / **`consolidation_time`** — how long it takes, from the
  `T_v(U)` fit and `t = T_v·H_dr²/c_v`.

See [`examples/clay_layer_settlement.py`](../examples/clay_layer_settlement.py) — a
footing strong enough to bear that still settles 97 mm over years.

## Retaining-wall external stability

- **`retaining_wall_overturning_factor`** `(V·a)/(P·y)` and
  **`retaining_wall_sliding_factor`** `(μ·V + P_p)/P`.
- **`eccentric_base_pressure`** — the middle-third base pressures, switching to the
  heel-uplift form once the resultant leaves the kern.

See [`examples/retaining_wall_stability.py`](../examples/retaining_wall_stability.py) —
overturning (FS 5.00) and sliding (FS 2.08) both pass, but the resultant leaves the
middle third, so the heel lifts and the toe pressure climbs to 148 kPa. Whether bearing
*governs* depends on the allowable bearing pressure of the soil, which the example does
not assume and the screen does not supply.

## Slopes, deep foundations, and seepage

- **`infinite_slope_factor_of_safety`** — the long-slope FS, dropping with pore
  pressure ([`examples/slope_stability_rain.py`](../examples/slope_stability_rain.py)).
- **`pile_skin_friction_capacity`** / **`pile_end_bearing_capacity`** /
  **`pile_allowable_capacity`** — the α-method deep-foundation capacity
  ([`examples/friction_pile_capacity.py`](../examples/friction_pile_capacity.py)).
- **`darcy_seepage_flow`** / **`seepage_velocity`** / **`critical_hydraulic_gradient`** /
  **`piping_factor_of_safety`** — dewatering flow and the piping (boiling) check
  ([`examples/cofferdam_seepage_piping.py`](../examples/cofferdam_seepage_piping.py)).
