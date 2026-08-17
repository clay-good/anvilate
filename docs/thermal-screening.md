# Thermal screening (heat-transfer resistance networks)

Enclosure and electronics thermal design starts with a resistance network — the
same series/parallel algebra as a circuit, with temperature difference playing the
role of voltage and heat flow the current. Anvilate does the network algebra and the
temperature rise; the convection coefficient is your input (from a correlation, a
datasheet, or the fan curve), not something a screen invents.

## What you get

```python
from anvilate.analysis import (
    conduction_thermal_resistance,
    convection_thermal_resistance,
    series_thermal_resistance,
    temperature_rise,
)
from anvilate.units import Quantity

r_pad = conduction_thermal_resistance(          # R = L/(k·A)
    thickness=Quantity.parse("0.3 mm"),
    area=Quantity.parse("400 mm**2"),
    conductivity=Quantity.parse("5 W/(m*K)"),
)
r_sink = convection_thermal_resistance(          # R = 1/(h·A)
    area=Quantity.parse("0.03 m**2"),
    heat_transfer_coefficient=Quantity.parse("40 W/(m**2*K)"),
)
total = series_thermal_resistance(r_pad, r_sink)              # ΣR
rise = temperature_rise(power=Quantity.parse("30 W"), thermal_resistance=total)  # ΔT = Q·R
```

- **`conduction_thermal_resistance`** = L/(k·A), **`convection_thermal_resistance`** =
  1/(h·A) — the two path types, both in K/W.
- **`series_thermal_resistance`** (ΣR — paths the heat flows through in turn) and
  **`parallel_thermal_resistance`** (1/R = Σ1/R — paths that share the load).
- **`temperature_rise`** = Q·R, the junction-to-ambient rise; add it to the ambient and
  compare against the rated limit.
- **`fin_efficiency`** = tanh(mL)/(mL) with m = √(h·P/(k·A_c)) — the fraction of the
  ideal (isothermal) fin heat a real fin moves.
- **`junction_temperature_scorecard`** screens the rise Q·R against an allowable-rise
  budget (the rated junction limit over the ambient) as a No-silent-green check.

## Computing the coefficient h

When you don't have a datasheet h, compute it from the flow. Both take
caller-supplied fluid properties (Anvilate evaluates the correlation, it carries no
fluid-property database):

- **`flat_plate_forced_convection_coefficient`** — the Incropera laminar external-flow
  correlation Nu = 0.664·Re^(1/2)·Pr^(1/3). Above the laminar limit (Re ≈ 5×10⁵) it
  returns `None` — the flow is turbulent and the correlation would extrapolate, so it
  reports "not evaluated" instead of a wrong number.
- **`vertical_plate_natural_convection_coefficient`** — the Churchill–Chu correlation
  (valid over the whole Rayleigh range), what governs a passively-cooled enclosure.

## Temperature differences, not absolute scales

Everything is in temperature *differences* (kelvin) — resistances, rises, margins. The
absolute junction and ambient temperatures are yours to add, so the module never
wrestles with an offset temperature scale.

See [`examples/power_device_heatsink.py`](../examples/power_device_heatsink.py) for a
power device whose junction cooks in still air and survives with a fan — the governing
resistance is the convection to air.

## Isolation and shock

The other half of this change is the mount the machine sits on. Two screens, and they
pull in opposite directions often enough that they are worth reading together.

```python
from anvilate.analysis import (
    isolator_selection_scorecard, half_sine_shock_scorecard, half_sine_shock_regime,
)

pick = isolator_selection_scorecard(
    "pump mounts", forcing_frequency=Quantity.parse("24.17 Hz"),
    target_transmissibility=0.10, selected_static_deflection=Quantity.parse("0.5 mm"),
)
# [FAIL] the mount AMPLIFIES (f/f_n = 1.08 < √2, TR = 5.69) — it is not an isolator here
```

- **`isolator_selection_scorecard`** screens the mount you actually picked, by its rated
  static deflection, against the softness `isolator_static_deflection_for_transmissibility`
  says the target demands. A mount that is *too stiff* does not isolate less — past a
  point it sits inside the amplification region and passes more than a rigid bolt-down
  would, so the entry says "AMPLIFIES" instead of reporting a transmissibility of 5.69 as
  though it belonged on the same scale as 0.02. No isolator picked yet is `NOT_EVALUATED`.
- **`half_sine_shock_amplification`** is the undamped maximax shock response spectrum of a
  half-sine pulse, from the exact Duhamel solution rather than a table — the residual
  branch `4ρ·|cos(πρ)|/|4ρ²−1|` and the primary branch, with ρ = τ·f_n. It is checked in
  the test suite against a direct numerical integration of the ODE it claims to solve.
- **`half_sine_shock_regime`** names which stretch of that spectrum a mount is in, and
  **`half_sine_shock_scorecard`** puts the label next to the number.

### Why the regime is reported and not just the factor

The shock spectrum is not monotonic in mount stiffness:

| τ/T | Regime | Amplification | Softening the mount… |
| --- | --- | --- | --- |
| 0.04 | impulsive | 0.15 | …is already working; a 30 g pulse arrives as 4.6 g |
| 0.81 | amplifying | **1.77** (the peak) | …helps; stiffening makes it worse |
| 3.3 | quasi-static | 1.17 | …makes it *worse* until you clear the peak |

Move a mount from τ/T = 3.3 to τ/T = 0.8 in the name of "more isolation" and the shock it
passes goes *up* by half. Which way to move is a question the bare number cannot answer
and the regime label can, which is why both are in the entry.

See [`examples/isolator_amplifies_at_running_speed.py`](../examples/isolator_amplifies_at_running_speed.py)
— a 1450 rpm pump whose three candidate pads split two ways for vibration, and whose
softness question then inverts for an 11 ms transport shock.
