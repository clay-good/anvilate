# Hydraulics screening (pipes, channels, and pumps)

The hydraulics pack sizes the fluid systems mechanical and civil engineers design —
a pressurized pipe run, an open drainage channel, the pump that drives them, a flow
meter, or the static load on a submerged surface. Every function is dimension-checked
and hand-verified against textbook values; fluid properties (density, viscosity,
vapor pressure) and roughness coefficients are the caller's.

## Pressurized pipe flow

```python
from anvilate.analysis import (
    reynolds_number, darcy_friction_factor, darcy_weisbach_head_loss, pipe_pressure_drop,
)
from anvilate.units import Quantity

re = reynolds_number(
    velocity=Quantity.parse("2 m/s"),
    diameter=Quantity.parse("0.1 m"),
    kinematic_viscosity=Quantity.parse("1e-6 m**2/s"),
)                                                                    # 200,000 (turbulent)
f = darcy_friction_factor(reynolds=re, relative_roughness=4.5e-4)    # 0.0187 (Swamee-Jain)
head = darcy_weisbach_head_loss(
    friction_factor=f, length=Quantity.parse("100 m"),
    diameter=Quantity.parse("0.1 m"), velocity=Quantity.parse("2 m/s"),
)                                                                    # 3.8 m
```

- **`reynolds_number`** → **`darcy_friction_factor`** (laminar `64/Re`, turbulent
  Swamee-Jain) → **`darcy_weisbach_head_loss`** `f·(L/D)·V²/(2g)`, plus
  **`minor_loss_head`** `K·V²/(2g)` for fittings and **`pipe_pressure_drop`** `ρ·g·h`.
- **`hazen_williams_head_loss`** / **`hazen_williams_flow_capacity`** — the empirical
  water-distribution shortcut, needing only a roughness coefficient C.

See [`examples/pump_line_pressure_drop.py`](../examples/pump_line_pressure_drop.py) and
[`examples/water_main_hazen_williams.py`](../examples/water_main_hazen_williams.py).

## Open-channel (free-surface) flow

- **`hydraulic_radius`** `A/P` → **`manning_flow_velocity`** / **`manning_flow_rate`**
  `(1/n)·R^(2/3)·S^(1/2)`.
- **`froude_number`** `V/√(g·y)` and **`critical_depth_rectangular`** `(q²/g)^(1/3)` —
  the pair that classifies the flow as sub- or supercritical.

See [`examples/drainage_channel_capacity.py`](../examples/drainage_channel_capacity.py) —
a channel that passes the design storm *and* runs subcritical.

## Pump sizing

- **`pump_hydraulic_power`** `ρ·g·Q·H` and **`pump_shaft_power`** `P/η`.
- **`pump_specific_speed`** `ω·√Q/(g·H)^(3/4)` — picks the impeller type.
- **`affinity_flow_rate`** / **`affinity_head`** / **`affinity_power`** — scale the
  operating point with speed (∝ N, N², N³); the cube on power is the VFD energy case.
- **`npsh_available`** `(p_atm − p_v)/(ρg) + h_s − h_f` and **`npsh_margin`** — the
  cavitation check a power calculation never sees.

See [`examples/pump_selection_from_line.py`](../examples/pump_selection_from_line.py),
[`examples/vfd_pump_energy_saving.py`](../examples/vfd_pump_energy_saving.py), and
[`examples/pump_npsh_cavitation.py`](../examples/pump_npsh_cavitation.py).

## Flow measurement and fluid statics

- **`obstruction_meter_flow_rate`** `C_d·A/√(1−β⁴)·√(2Δp/ρ)` (orifice, venturi, nozzle),
  its **`differential_pressure_for_flow`** inverse, and **`pitot_velocity`** `√(2Δp/ρ)`
  ([`examples/orifice_meter_sizing.py`](../examples/orifice_meter_sizing.py)).
- **`hydrostatic_pressure`** `ρ·g·h`, **`hydrostatic_force_on_plane`** `ρ·g·h_c·A`,
  **`center_of_pressure_depth`** (below the centroid), and **`buoyant_force`** `ρ·g·V`
  ([`examples/submerged_gate_hinge.py`](../examples/submerged_gate_hinge.py)).
