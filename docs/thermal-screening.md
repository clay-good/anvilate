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
