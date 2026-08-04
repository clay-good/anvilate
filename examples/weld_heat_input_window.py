"""Worked example: keeping a weld run inside its qualified heat-input window with travel speed.

A welding procedure does not just fix the amps and volts — it qualifies a *range* of heat input, the
energy the arc puts into the joint per millimetre of weld. Too little and the joint cools fast
enough to harden and risk hydrogen cracking; too much and the heat-affected zone softens, the plate
distorts, and thin material can burn through. At a fixed voltage and current the welder's real
control over heat input is travel speed: move faster to spread the same arc power over more length
and drop the heat input, slower to raise it.

This example takes a SMAW run at 25 V and 200 A — a 5 kW arc — at 80% thermal efficiency, and a
procedure qualified for 0.8 to 1.5 kJ/mm. At a brisk 5 mm/s the run comes in at 0.8 kJ/mm, right at
the low edge; slow to a crawl at 2.7 mm/s and it climbs to 1.5 kJ/mm at the high edge. So the
qualified window is not a vague instruction but a concrete travel-speed band: roughly 2.7 to 5 mm/s
for this electrode and current. The example computes the heat input at a chosen speed and inverts
relation to find the speeds that bound the window, turning a metallurgical limit into the number the
welder actually reads off the run.

Run it directly (``python examples/weld_heat_input_window.py``);
:func:`heat_input_window` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import weld_heat_input, weld_travel_speed_for_heat_input
from anvilate.units import Quantity

ARC_VOLTAGE = Quantity.parse("25 V")
WELDING_CURRENT = Quantity.parse("200 A")
THERMAL_EFFICIENCY = 0.8  # SMAW
NOMINAL_TRAVEL_SPEED = Quantity.parse("4 mm/s")
MIN_HEAT_INPUT = Quantity.parse("0.8 kJ/mm")
MAX_HEAT_INPUT = Quantity.parse("1.5 kJ/mm")


def heat_input_window() -> dict[str, float]:
    """Return the heat input at the nominal speed and the travel-speed band the window allows."""
    nominal = weld_heat_input(
        arc_voltage=ARC_VOLTAGE,
        welding_current=WELDING_CURRENT,
        travel_speed=NOMINAL_TRAVEL_SPEED,
        thermal_efficiency=THERMAL_EFFICIENCY,
    )
    # A higher heat input means a slower travel speed, so the max heat input sets the minimum speed.
    slowest = weld_travel_speed_for_heat_input(
        arc_voltage=ARC_VOLTAGE,
        welding_current=WELDING_CURRENT,
        heat_input=MAX_HEAT_INPUT,
        thermal_efficiency=THERMAL_EFFICIENCY,
    )
    fastest = weld_travel_speed_for_heat_input(
        arc_voltage=ARC_VOLTAGE,
        welding_current=WELDING_CURRENT,
        heat_input=MIN_HEAT_INPUT,
        thermal_efficiency=THERMAL_EFFICIENCY,
    )
    return {
        "nominal_heat_input_kj_mm": nominal.to("kJ/mm").magnitude,
        "slowest_speed_mm_s": slowest.to("mm/s").magnitude,
        "fastest_speed_mm_s": fastest.to("mm/s").magnitude,
    }


def main() -> None:
    w = heat_input_window()
    print(f"heat input at 4 mm/s : {w['nominal_heat_input_kj_mm']:.2f} kJ/mm")
    print(
        f"qualified 0.8-1.5 kJ/mm -> travel-speed band "
        f"{w['slowest_speed_mm_s']:.1f} to {w['fastest_speed_mm_s']:.1f} mm/s"
    )
    print("  -> travel speed is the knob that keeps the run inside the procedure's window")


if __name__ == "__main__":
    main()
