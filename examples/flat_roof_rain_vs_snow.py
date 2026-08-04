"""Worked example: on a flat roof, does snow or a blocked drain govern?

A flat roof carries two competing environmental loads, and which one designs it is a real decision,
not a formality. Snow (from the ground snow load) is the obvious one. The quieter one is rain: if
the primary roof drain clogs — leaves, ice, debris — water backs up to the secondary (overflow)
drain and stands on the roof, and ASCE 7 makes you design for that pond, R = 0.0098·(ds + dh).

This example takes a heated commercial roof in a moderate-snow region: 1.2 kPa ground snow, and a
secondary-drainage layout that ponds 50 mm to the overflow inlet plus 40 mm of hydraulic head to
push the design storm through it. The flat-roof snow works out to 0.84 kPa, but the ponded rain
reaches 0.88 kPa — so the blocked-drain rain case, not the snow, sets the roof. That is the trap: a
designer who checks only snow underbuilds the roof for the storm that actually fails it, which is
why ASCE 7 requires the rain load be checked independently and why a generous secondary drain (small
hydraulic head) is cheap structural insurance. The lesson is that on a flat roof the governing load
can be the one nobody watches — the water that never drains.

Run it directly (``python examples/flat_roof_rain_vs_snow.py``);
:func:`roof_loads` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import flat_roof_snow_load, rain_load
from anvilate.units import Quantity

GROUND_SNOW = Quantity.parse("1.2 kPa")
STATIC_HEAD = Quantity.parse("50 mm")  # depth to the secondary drain inlet
HYDRAULIC_HEAD = Quantity.parse("40 mm")  # extra head to drive the design storm out


def roof_loads() -> dict[str, float]:
    """Return the flat-roof snow and the blocked-drain rain loads, and which governs."""
    snow = flat_roof_snow_load(ground_snow_load=GROUND_SNOW)
    rain = rain_load(static_head=STATIC_HEAD, hydraulic_head=HYDRAULIC_HEAD)
    return {
        "snow_kpa": snow.to("kPa").magnitude,
        "rain_kpa": rain.to("kPa").magnitude,
    }


def main() -> None:
    r = roof_loads()
    governing = "rain (blocked drain)" if r["rain_kpa"] > r["snow_kpa"] else "snow"
    print(f"flat-roof snow      : {r['snow_kpa']:.2f} kPa")
    print(f"ponded rain (backed-up drain) : {r['rain_kpa']:.2f} kPa")
    print(f"  -> {governing} governs the roof")


if __name__ == "__main__":
    main()
