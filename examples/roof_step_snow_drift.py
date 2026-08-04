"""Worked example: the snow that piles against a roof step and caves it in.

Balanced snow spread evenly over a roof is the load everyone checks. The load that actually caves
roofs in is the *drift*: where a low roof abuts a taller wall or steps down from an upper roof, wind
scours snow off the upper surface and heaps it into a triangular pile against the step. ASCE 7 sizes
that pile — its height hd = 0.416·lu^⅓·(pg + 0.479)^¼ − 0.457 from the upwind fetch lu and the
ground snow pg — and the surcharge it adds is the snow's own weight, pd = γ·hd.

This example takes a loading-dock roof, 1.2 kPa ground snow, sitting below a 40 m upper roof that
feeds it. The balanced flat-roof snow is a mild 0.84 kPa. But the drift against the step builds to
about 1.2 m of snow at a density of 2.7 kN/m³, a peak surcharge near 3.2 kPa — nearly four times the
balanced load, concentrated in a narrow band along the wall. A roof checked only for balanced snow
is sized for a quarter of what the corner against the step will carry, which is why drifting is
the snow failure that surprises people. The lesson is that the governing snow load on a stepped roof
is local and lopsided: the drift, not the blanket, is what has to be caught.

Run it directly (``python examples/roof_step_snow_drift.py``);
:func:`drift_surcharge` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    flat_roof_snow_load,
    leeward_snow_drift_height,
    snow_density,
)
from anvilate.units import Quantity

GROUND_SNOW = Quantity.parse("1.2 kPa")
UPWIND_FETCH = Quantity.parse("40 m")


def drift_surcharge() -> dict[str, float]:
    """Return the balanced snow, drift height, and peak drift surcharge (kPa and m)."""
    balanced = flat_roof_snow_load(ground_snow_load=GROUND_SNOW).to("kPa").magnitude
    height = (
        leeward_snow_drift_height(upwind_fetch=UPWIND_FETCH, ground_snow_load=GROUND_SNOW)
        .to("m")
        .magnitude
    )
    density = snow_density(ground_snow_load=GROUND_SNOW).to("kN/m**3").magnitude
    return {
        "balanced_kpa": balanced,
        "drift_height_m": height,
        "drift_surcharge_kpa": density * height,
    }


def main() -> None:
    d = drift_surcharge()
    ratio = d["drift_surcharge_kpa"] / d["balanced_kpa"]
    print(f"balanced flat-roof snow : {d['balanced_kpa']:.2f} kPa")
    print(f"drift height at the step : {d['drift_height_m']:.2f} m")
    print(f"peak drift surcharge : {d['drift_surcharge_kpa']:.2f} kPa ({ratio:.1f}x the balanced)")
    print("  -> the drift against the step, not the balanced blanket, governs the roof")


if __name__ == "__main__":
    main()
