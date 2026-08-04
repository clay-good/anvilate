"""Worked example: why a cooling tower is rated by its approach, not the water temperature it hits.

A cooling tower's job is to throw a condenser's heat away by evaporating a little water, and the
coldest it can ever make that water is the *wet-bulb* temperature of the air — the floor evaporation
sets. Two numbers describe how a tower does against that floor. The range is how much it cools the
water, T_hot − T_cold, and it is fixed by the heat load and the flow, not by the tower. The approach
is how close the cooled water gets to the wet-bulb, T_cold − T_wb, and *that* is what the tower's
size buys: the wet-bulb is unreachable, and each degree closer to it costs a steeply larger tower.

This example takes a tower cooling condenser water from 37 °C down to 30 °C on a muggy day whose air
sits at a 25 °C wet-bulb. The range is a healthy 7 °C, but the water still lands 5 °C above the
wet-bulb floor, so the tower captures 7/(7 + 5) ≈ 58% of the cooling that was thermodynamically on
the table. The example then asks what a bigger tower — one designed for a 2 °C approach on the same
day — would achieve: the same 7 °C range, but now 78% effectiveness, because the water leaves much
closer to the floor. The lesson is the one every tower-selection sheet turns on: quoting the cold-
water temperature alone is meaningless without the wet-bulb it was measured against, and it is the
approach, not the leaving temperature, that says how much tower you are actually paying for.

Run it directly (``python examples/cooling_tower_approach.py``);
:func:`tower_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    cooling_tower_approach,
    cooling_tower_effectiveness,
    cooling_tower_range,
)
from anvilate.units import Quantity

HOT_WATER = Quantity(magnitude=37.0, unit="degC")
COLD_WATER = Quantity(magnitude=30.0, unit="degC")
WET_BULB = Quantity(magnitude=25.0, unit="degC")
TIGHT_APPROACH = Quantity(magnitude=2.0, unit="K")  # a larger tower designed for a 2 C approach


def tower_performance() -> dict[str, float]:
    """Return the range, approach, and effectiveness of the tower, and a tighter-approach design."""
    r = cooling_tower_range(hot_water_temperature=HOT_WATER, cold_water_temperature=COLD_WATER)
    a = cooling_tower_approach(cold_water_temperature=COLD_WATER, wet_bulb_temperature=WET_BULB)
    eff = cooling_tower_effectiveness(range_=r, approach=a)
    tight_eff = cooling_tower_effectiveness(range_=r, approach=TIGHT_APPROACH)
    return {
        "range_k": r.to("K").magnitude,
        "approach_k": a.to("K").magnitude,
        "effectiveness": eff,
        "tight_effectiveness": tight_eff,
    }


def main() -> None:
    p = tower_performance()
    print(f"range   : {p['range_k']:.0f} K  (37 C -> 30 C water, set by the load and flow)")
    print(f"approach: {p['approach_k']:.0f} K  (30 C water vs 25 C wet-bulb -- the floor)")
    print(f"effectiveness: {p['effectiveness']:.0%}  (share of the available cooling captured)")
    print(
        f"a bigger tower at a 2 K approach would reach {p['tight_effectiveness']:.0%} "
        "on the same day"
    )


if __name__ == "__main__":
    main()
