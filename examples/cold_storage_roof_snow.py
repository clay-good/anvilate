"""Worked example: why a freezer's roof carries more snow than the heated warehouse next door.

Two buildings on the same snowy site see the same ground snow, but their roofs do not carry the same
load — and the surprise is that the *colder* building carries more. A heated warehouse leaks enough
heat through its roof to melt the underside of the snowpack and shed it; a refrigerated cold-storage
building keeps its roof at freezing, so the snow just accumulates. ASCE 7 captures this in the
thermal factor Ct, which is 1.0 for a heated roof and rises above 1 for an unheated or freezer roof.

This example takes 2.0 kPa of ground snow and works the flat-roof load both ways: the heated
warehouse (Ct = 1.0) carries 1.4 kPa, while the freezer next door (Ct = 1.3) carries 1.82 kPa — 30%
more, for the same weather, purely because it refuses to melt its snow. It then puts a steeper pitch
on the freezer roof and lets the slope factor shed part of the load back off. The lesson is
counterintuitive but it drives real structure: a refrigerated building needs a stronger roof than
the heated one beside it, and geometry, through the slope factor, is one way to win some of it back.

Run it directly (``python examples/cold_storage_roof_snow.py``);
:func:`roof_snow_loads` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import flat_roof_snow_load, sloped_roof_snow_load
from anvilate.units import Quantity

GROUND_SNOW = Quantity.parse("2.0 kPa")
HEATED_THERMAL_FACTOR = 1.0
FREEZER_THERMAL_FACTOR = 1.3
FREEZER_SLOPE_FACTOR = 0.7  # a steeper, slippery freezer roof sheds part of the load


def roof_snow_loads() -> dict[str, float]:
    """Return the flat-roof snow on a heated and a freezer roof, and the freezer's sloped value."""
    heated = flat_roof_snow_load(ground_snow_load=GROUND_SNOW, thermal_factor=HEATED_THERMAL_FACTOR)
    freezer_flat = flat_roof_snow_load(
        ground_snow_load=GROUND_SNOW, thermal_factor=FREEZER_THERMAL_FACTOR
    )
    freezer_sloped = sloped_roof_snow_load(
        flat_roof_snow_load=freezer_flat, slope_factor=FREEZER_SLOPE_FACTOR
    )
    return {
        "heated_flat_kpa": heated.to("kPa").magnitude,
        "freezer_flat_kpa": freezer_flat.to("kPa").magnitude,
        "freezer_sloped_kpa": freezer_sloped.to("kPa").magnitude,
    }


def main() -> None:
    r = roof_snow_loads()
    extra = (r["freezer_flat_kpa"] / r["heated_flat_kpa"] - 1.0) * 100.0
    print(f"heated warehouse (Ct=1.0) : {r['heated_flat_kpa']:.2f} kPa flat-roof snow")
    print(f"freezer, flat  (Ct=1.3)   : {r['freezer_flat_kpa']:.2f} kPa ({extra:.0f}% more)")
    print(f"freezer, sloped (Cs=0.7)  : {r['freezer_sloped_kpa']:.2f} kPa (shed by the pitch)")
    print("  -> the colder roof carries more snow; geometry is one way to win it back")


if __name__ == "__main__":
    main()
