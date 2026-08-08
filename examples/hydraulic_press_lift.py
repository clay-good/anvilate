"""Worked example: a hydraulic press lifting a heavy load.

A hydraulic press multiplies force through the ratio of its piston areas, but like every simple
machine it gives nothing for free: the small input piston has to move much farther than the large
output piston, so the work in equals the work out.

Pressing with 100 N on a small piston of 0.001 m^2 (10 cm^2) develops a fluid pressure of 100 kPa.
Acting on a large output piston of 0.01 m^2 (100 cm^2) — a 10:1 area ratio — that pressure produces
1,000 N, a tenfold force gain. To raise the load 0.05 m, though, the input piston must be pushed
0.5 m, ten times as far, so both sides do the same 50 J of work. This example reports the
transmitted pressure, the output force, and the input stroke.

Run it directly (``python examples/hydraulic_press_lift.py``);
:func:`press_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    hydraulic_press_input_stroke,
    hydraulic_press_output_force,
    hydraulic_press_transmitted_pressure,
)
from anvilate.units import Quantity

INPUT_FORCE = Quantity(magnitude=100.0, unit="N")
INPUT_AREA = Quantity(magnitude=0.001, unit="m**2")  # 10 cm^2
OUTPUT_AREA = Quantity(magnitude=0.01, unit="m**2")  # 100 cm^2
OUTPUT_STROKE = Quantity(magnitude=0.05, unit="m")


def press_performance() -> dict[str, float]:
    """Return the transmitted pressure, the output force, and the input stroke."""
    pressure = hydraulic_press_transmitted_pressure(
        input_force=INPUT_FORCE, input_piston_area=INPUT_AREA
    )
    force = hydraulic_press_output_force(
        input_force=INPUT_FORCE, input_piston_area=INPUT_AREA, output_piston_area=OUTPUT_AREA
    )
    stroke = hydraulic_press_input_stroke(
        output_stroke=OUTPUT_STROKE, input_piston_area=INPUT_AREA, output_piston_area=OUTPUT_AREA
    )
    return {
        "transmitted_pressure_kpa": pressure.to("Pa").magnitude / 1000.0,
        "output_force_n": force.to("N").magnitude,
        "input_stroke_m": stroke.to("m").magnitude,
    }


def main() -> None:
    d = press_performance()
    print(f"transmitted pressure: {d['transmitted_pressure_kpa']:.0f} kPa")
    print(f"output force: {d['output_force_n']:.0f} N")
    print(f"input stroke to lift 0.05 m: {d['input_stroke_m']:.2f} m")


if __name__ == "__main__":
    main()
