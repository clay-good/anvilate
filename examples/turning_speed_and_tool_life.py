"""Worked example: the turning cut where a faster spindle buys minutes and costs tool life.

Choosing a cutting speed is a tug of war. A handbook gives a surface speed for the tool-and-material
pair; the machinist converts it to an rpm for the workpiece diameter, and a faster speed removes
metal sooner. But the same speed that shortens the cut shortens the tool's life too — and by Taylor
law that penalty is steep, because tool life falls with a high power of speed.

This example turns a 50 mm bar with a carbide insert (Taylor constant C = 400 m/min, exponent
n = 0.25) at a 0.2 mm/rev feed and a 2 mm depth. At a conservative 157 m/min the spindle runs 1000
rpm, removes metal at about 63 cm³/min, and the edge lasts about 42 minutes. Push the surface speed
to 250 m/min and the spindle jumps to about 1592 rpm, the removal rate climbs to about 100 cm³/min —
a 60% faster cut — but the tool life collapses to about 6.5 minutes, more than six times shorter.
The example computes the rpm, the removal rate, and the tool life at both speeds so the trade is
explicit: the productivity gain is linear in speed, but the tool-life cost goes as speed to the
fourth power, and somewhere between these two points sits the economical speed a shop actually runs.

Run it directly (``python examples/turning_speed_and_tool_life.py``);
:func:`turning_tradeoff` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    material_removal_rate,
    spindle_speed_for_cutting_speed,
    taylor_tool_life,
)
from anvilate.units import Quantity

DIAMETER = Quantity.parse("50 mm")
FEED = Quantity.parse("0.2 mm")  # per revolution
DEPTH_OF_CUT = Quantity.parse("2 mm")
TAYLOR_C = Quantity.parse("400 m/min")
TAYLOR_N = 0.25  # carbide
CONSERVATIVE_SPEED = Quantity.parse("157 m/min")
AGGRESSIVE_SPEED = Quantity.parse("250 m/min")


def turning_tradeoff() -> dict[str, float]:
    """Return the rpm, removal rate, and tool life at a conservative and an aggressive speed."""

    def at_speed(cutting_speed: Quantity) -> dict[str, float]:
        rpm = spindle_speed_for_cutting_speed(cutting_speed=cutting_speed, diameter=DIAMETER)
        mrr = material_removal_rate(
            cutting_speed=cutting_speed, feed=FEED, depth_of_cut=DEPTH_OF_CUT
        )
        life = taylor_tool_life(
            cutting_speed=cutting_speed,
            taylor_speed_constant=TAYLOR_C,
            taylor_exponent=TAYLOR_N,
        )
        return {
            "rpm": rpm.to("rpm").magnitude,
            "mrr_cm3_min": mrr.to("cm**3/min").magnitude,
            "life_min": life.to("min").magnitude,
        }

    slow = at_speed(CONSERVATIVE_SPEED)
    fast = at_speed(AGGRESSIVE_SPEED)
    return {
        "slow_rpm": slow["rpm"],
        "slow_mrr": slow["mrr_cm3_min"],
        "slow_life": slow["life_min"],
        "fast_rpm": fast["rpm"],
        "fast_mrr": fast["mrr_cm3_min"],
        "fast_life": fast["life_min"],
    }


def main() -> None:
    t = turning_tradeoff()
    print(
        f"157 m/min: {t['slow_rpm']:.0f} rpm, {t['slow_mrr']:.0f} cm3/min, "
        f"tool life {t['slow_life']:.0f} min"
    )
    print(
        f"250 m/min: {t['fast_rpm']:.0f} rpm, {t['fast_mrr']:.0f} cm3/min, "
        f"tool life {t['fast_life']:.1f} min"
    )
    print("  -> the faster cut removes ~60% more metal but the tool lasts ~6x less time")


if __name__ == "__main__":
    main()
