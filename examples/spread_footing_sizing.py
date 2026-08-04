"""Worked example: the footing that comes out too small if you forget its own weight.

Sizing a spread footing is the tail end of a short chain: the soil's ultimate bearing capacity, an
allowable pressure a factor of safety below it, and the plan area the column load needs at that
pressure. This example runs the chain for an 800 kN column on a clayey-sand with a 600 kPa ultimate
capacity, and turns on the one step everyone is tempted to skip.

The allowable pressure is 600 / 3 = 200 kPa. Divide the 800 kN column load straight by that and you
get a 4.00 m² footing — but that is wrong, because the footing and the soil backfilled over it also
weigh on the ground, using up about 25 kPa of the allowable before the column load gets any. The
column has only 200 − 25 = 175 kPa to work with, so it needs 4.57 m² — a 14% bigger footing, a
2.14 m square instead of 2.00 m. Size on the gross pressure and the real bearing pressure quietly
exceeds the allowable once the footing is cast. The lesson is that the allowable pressure is shared:
the overburden takes its cut first, and the column is sized on what is left.

Run it directly (``python examples/spread_footing_sizing.py``);
:func:`footing_area` is also exercised in the test suite.
"""

from __future__ import annotations

from math import sqrt

from anvilate.analysis import allowable_bearing_from_ultimate, required_spread_footing_area
from anvilate.units import Quantity

ULTIMATE_BEARING = Quantity.parse("600 kPa")
FACTOR_OF_SAFETY = 3.0
COLUMN_LOAD = Quantity.parse("800 kN")
OVERBURDEN = Quantity.parse("25 kPa")  # footing + backfill weight at founding level


def footing_area() -> dict[str, float]:
    """Return the allowable pressure and the gross vs net required footing areas (m²)."""
    allowable = allowable_bearing_from_ultimate(
        ultimate_bearing_capacity=ULTIMATE_BEARING, factor_of_safety=FACTOR_OF_SAFETY
    )
    gross = required_spread_footing_area(
        service_load=COLUMN_LOAD, allowable_bearing_pressure=allowable
    )
    net = required_spread_footing_area(
        service_load=COLUMN_LOAD,
        allowable_bearing_pressure=allowable,
        overburden_pressure=OVERBURDEN,
    )
    return {
        "allowable_kpa": allowable.to("kPa").magnitude,
        "gross_area_m2": gross.to("m**2").magnitude,
        "net_area_m2": net.to("m**2").magnitude,
    }


def main() -> None:
    f = footing_area()
    bigger = (f["net_area_m2"] / f["gross_area_m2"] - 1.0) * 100.0
    gross_b = sqrt(f["gross_area_m2"])
    net_b = sqrt(f["net_area_m2"])
    print(f"allowable bearing : {f['allowable_kpa']:.0f} kPa (600 / 3)")
    print(f"gross-pressure area : {f['gross_area_m2']:.2f} m2  ({gross_b:.2f} m square)")
    print(
        f"net-pressure area   : {f['net_area_m2']:.2f} m2  ({net_b:.2f} m square, "
        f"{bigger:.0f}% bigger)"
    )
    print("  -> the overburden takes its cut of the allowable first; size the column on the rest")


if __name__ == "__main__":
    main()
