"""Worked example: why the last half of a draining tank takes longer than the first.

A tank draining through a hole in its bottom does not empty at a steady rate. Torricelli says the
jet speed is √(2gh), so it starts fast under a full head and slows as the level falls — the last,
shallow inch dribbles out. That means the drain time is not linear with depth: draining the top
half of the tank is quick, and the bottom half, under low head, takes disproportionately longer.
This example drains a 10 m² tank through a 100 cm² valve from a 4 m depth and shows the split — the
upper half empties in far less than half the total time — which is why a drain sized for the
average rate under-delivers at the end, and why spill-containment and blowdown times are computed
from the integral, not from volume over a nominal flow.

Run it directly (``python examples/tank_drain_down.py``);
:func:`drain_schedule` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import tank_drain_time
from anvilate.units import Quantity

TANK_AREA = Quantity.parse("10 m**2")
ORIFICE_AREA = Quantity.parse("0.01 m**2")  # 100 cm^2 valve
DISCHARGE_COEFFICIENT = 0.6
FULL_HEAD = Quantity.parse("4 m")
HALF_HEAD = Quantity.parse("2 m")
EMPTY = Quantity.parse("0 m")


def drain_schedule() -> dict[str, float]:
    """Return the total, upper-half, and lower-half drain times (s) and the lower/upper ratio."""
    total = (
        tank_drain_time(
            tank_area=TANK_AREA,
            orifice_area=ORIFICE_AREA,
            discharge_coefficient=DISCHARGE_COEFFICIENT,
            initial_head=FULL_HEAD,
            final_head=EMPTY,
        )
        .to("s")
        .magnitude
    )
    upper = (
        tank_drain_time(
            tank_area=TANK_AREA,
            orifice_area=ORIFICE_AREA,
            discharge_coefficient=DISCHARGE_COEFFICIENT,
            initial_head=FULL_HEAD,
            final_head=HALF_HEAD,
        )
        .to("s")
        .magnitude
    )
    lower = total - upper
    return {
        "total_s": total,
        "upper_half_s": upper,
        "lower_half_s": lower,
        "lower_over_upper": lower / upper,
    }


def main() -> None:
    d = drain_schedule()
    print(f"total drain time : {d['total_s'] / 60:.1f} min (4 m to empty)")
    print(f"upper half (4->2 m) : {d['upper_half_s'] / 60:.1f} min")
    print(f"lower half (2->0 m) : {d['lower_half_s'] / 60:.1f} min")
    print(
        f"  -> the low-head bottom half takes {d['lower_over_upper']:.1f}x as long as the top half"
    )


if __name__ == "__main__":
    main()
