"""Worked example: does a 12 V-to-5 V linear regulator need a heatsink?

A board takes a 12 V rail down to 5 V at 1 A with a classic three-terminal linear regulator that
draws 5 mA of quiescent current. The designer wants to know two things before committing: how much
heat the regulator sheds, and how efficient the stage is.

The pass element drops 7 V at 1 A, so it burns about 7.06 W — far above the ~2 W a TO-220 package
can shed on its own in still air, so this stage needs a heatsink (or a switching pre-regulator). The
efficiency is only ~41%: nearly three-fifths of the input power is wasted as heat, the unavoidable
signature of a linear regulator across a wide input-to-output gap. Both numbers point the same way:
for a 12-to-5 step-down at an amp, a switching converter is the better choice.

Run it directly (``python examples/linear_regulator_heatsink_screen.py``);
:func:`regulator_thermal_screen` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    linear_regulator_dissipation,
    linear_regulator_efficiency,
)
from anvilate.units import Quantity

INPUT_VOLTAGE = Quantity.parse("12 V")
OUTPUT_VOLTAGE = Quantity.parse("5 V")
LOAD_CURRENT = Quantity.parse("1 A")
QUIESCENT_CURRENT = Quantity.parse("5 mA")


def regulator_thermal_screen() -> dict[str, float]:
    """Return the linear regulator's dissipation (W) and its efficiency."""
    p_diss = linear_regulator_dissipation(
        input_voltage=INPUT_VOLTAGE,
        output_voltage=OUTPUT_VOLTAGE,
        load_current=LOAD_CURRENT,
        quiescent_current=QUIESCENT_CURRENT,
    )
    efficiency = linear_regulator_efficiency(
        input_voltage=INPUT_VOLTAGE,
        output_voltage=OUTPUT_VOLTAGE,
        load_current=LOAD_CURRENT,
        quiescent_current=QUIESCENT_CURRENT,
    )
    return {
        "dissipation_W": p_diss.to("W").magnitude,
        "efficiency": efficiency,
    }


def main() -> None:
    d = regulator_thermal_screen()
    print("Linear regulator, 12 V -> 5 V at 1 A:")
    print(f"  dissipation : {d['dissipation_W']:.2f} W")
    print(f"  efficiency  : {d['efficiency'] * 100:.1f} %")


if __name__ == "__main__":
    main()
