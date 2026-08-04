"""Worked example: the big column that gets to design for less live load.

Design live loads are set high enough to cover a crowd standing in the worst spot — but a column
gathering many square metres of floor is never fully loaded everywhere at once, and ASCE 7 rewards
that with a live-load reduction, L = L0·(0.25 + 4.57/√(KLL·AT)). The larger the tributary area, the
deeper the discount, down to a floor of half (or, over multiple floors, 40%) of the tabulated load.

This example takes an interior office column (2.4 kPa design live load, element factor KLL = 4)
carrying six floors of 60 m² each. On its own floor the small tributary area earns nothing, but
gathering 360 m² of influence area the reduction bites hard — the design live load drops to about
40% of the unreduced value, right at the multi-floor floor. It then carries that reduced load, plus
the dead load, into the governing LRFD combination to show the payoff: designing the column for
the unreduced live load would oversize it by a wide margin. The lesson is that the reduction is
not a rounding tweak — for a heavily-loaded column it is one of the largest single savings in the
gravity design, and it compounds through the load combination into the member size.

Run it directly (``python examples/column_live_load_reduction.py``);
:func:`column_live_load` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import asce7_lrfd_factored_load, reduced_live_load
from anvilate.units import Quantity

UNREDUCED_LIVE_LOAD = Quantity.parse("2.4 kPa")
ELEMENT_FACTOR = 4.0  # interior column
FLOOR_TRIBUTARY_AREA = Quantity.parse("60 m**2")
NUMBER_OF_FLOORS = 6
DEAD_LOAD = Quantity.parse("3.5 kPa")


def column_live_load() -> dict[str, float]:
    """Return the unreduced and reduced live loads and the LRFD demand each produces (in kPa)."""
    total_area = Quantity(
        magnitude=FLOOR_TRIBUTARY_AREA.to("m**2").magnitude * NUMBER_OF_FLOORS, unit="m**2"
    )
    reduced = reduced_live_load(
        unreduced_live_load=UNREDUCED_LIVE_LOAD,
        live_load_element_factor=ELEMENT_FACTOR,
        tributary_area=total_area,
        supports_multiple_floors=True,
    )
    lrfd_unreduced = asce7_lrfd_factored_load(dead=DEAD_LOAD, live=UNREDUCED_LIVE_LOAD)
    lrfd_reduced = asce7_lrfd_factored_load(dead=DEAD_LOAD, live=reduced)
    return {
        "unreduced_live_kpa": UNREDUCED_LIVE_LOAD.to("kPa").magnitude,
        "reduced_live_kpa": reduced.to("kPa").magnitude,
        "lrfd_unreduced_kpa": lrfd_unreduced.to("kPa").magnitude,
        "lrfd_reduced_kpa": lrfd_reduced.to("kPa").magnitude,
    }


def main() -> None:
    c = column_live_load()
    live_pct = c["reduced_live_kpa"] / c["unreduced_live_kpa"] * 100.0
    demand_pct = c["lrfd_reduced_kpa"] / c["lrfd_unreduced_kpa"] * 100.0
    print(
        f"live load : {c['unreduced_live_kpa']:.2f} -> {c['reduced_live_kpa']:.2f} kPa "
        f"({live_pct:.0f}% of unreduced)"
    )
    print(
        f"LRFD demand : {c['lrfd_unreduced_kpa']:.2f} -> {c['lrfd_reduced_kpa']:.2f} kPa "
        f"({demand_pct:.0f}%)"
    )
    print("  -> gathering 360 m2 of floor, the column designs for a much smaller live load")


if __name__ == "__main__":
    main()
