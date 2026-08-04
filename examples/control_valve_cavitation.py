"""Worked example: will a throttling control valve cavitate? The cavitation-number screen.

A control valve does its job by throwing away pressure, and where it does that the flow speeds up
and the local pressure dives — if it dives to the liquid's vapor pressure, the water flashes to
vapor cavities that collapse downstream and hammer the trim to pieces. The cavitation number
σ = (p − p_v)/(½·ρ·V²) is the dimensionless margin against that. This example screens the same valve
at two duty points on 20°C water (vapor pressure 2.34 kPa). Lightly throttled, the vena-contracta
pressure stays around 200 kPa at a modest 8 m/s and σ sits comfortably above the ~1 incipient value.
Heavily throttled, the local pressure collapses toward 40 kPa while the velocity jumps to 18 m/s,
and σ falls below 1 — into the regime where the valve cavitates and needs anti-cavitation trim or a
staged pressure drop.

Run it directly (``python examples/control_valve_cavitation.py``);
:func:`valve_cavitation` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import cavitation_number
from anvilate.units import Quantity

VAPOR_PRESSURE = Quantity.parse("2.34 kPa")  # water at 20 C
DENSITY = Quantity.parse("998 kg/m**3")


def valve_cavitation() -> dict[str, float]:
    """Return the cavitation number at a light and a heavy throttling condition."""
    light = cavitation_number(
        local_pressure=Quantity.parse("200 kPa"),
        vapor_pressure=VAPOR_PRESSURE,
        density=DENSITY,
        velocity=Quantity.parse("8 m/s"),
    )
    heavy = cavitation_number(
        local_pressure=Quantity.parse("40 kPa"),
        vapor_pressure=VAPOR_PRESSURE,
        density=DENSITY,
        velocity=Quantity.parse("18 m/s"),
    )
    return {"light_sigma": light, "heavy_sigma": heavy}


def main() -> None:
    v = valve_cavitation()
    print(f"lightly throttled : σ = {v['light_sigma']:.1f} (well above 1 — no cavitation)")
    print(f"heavily throttled : σ = {v['heavy_sigma']:.2f} (below 1 — cavitation risk)")
    print("  -> as the valve throttles, p falls and V rises; σ drops toward the cavitation regime")


if __name__ == "__main__":
    main()
