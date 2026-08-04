"""Worked example: sizing a rectangular duct through its round equivalent, and the fan it needs.

Duct friction charts are drawn for round duct, but real ducts run rectangular to fit above
ceilings, so sizing goes through the *circular equivalent* — the round duct with the same airflow
and friction. This example takes a 500 × 250 mm supply duct, finds its ASHRAE equivalent diameter,
and contrasts it with the hydraulic diameter 4A/P to show why the two must not be confused: the
equivalent is the larger, and using the hydraulic diameter would undersize the run. It then sizes
the fan
for the system, turning a 1.2 m³/s airflow against a 400 Pa total pressure loss into the shaft power
a 62%-efficient fan must deliver — the number that sets the motor and the running cost.

Run it directly (``python examples/rectangular_duct_sizing.py``);
:func:`duct_and_fan` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import circular_equivalent_diameter, fan_power
from anvilate.units import Quantity

WIDTH = Quantity.parse("500 mm")
HEIGHT = Quantity.parse("250 mm")
FLOW_RATE = Quantity.parse("1.2 m**3/s")
TOTAL_PRESSURE = Quantity.parse("400 Pa")
FAN_EFFICIENCY = 0.62


def duct_and_fan() -> dict[str, float]:
    """Return the equivalent and hydraulic diameters (mm) and the fan shaft power (W)."""
    equivalent = circular_equivalent_diameter(width=WIDTH, height=HEIGHT)
    a = WIDTH.to("m").magnitude
    b = HEIGHT.to("m").magnitude
    hydraulic_m = 4 * (a * b) / (2 * (a + b))  # 4A/P for the rectangle
    fan = fan_power(
        flow_rate=FLOW_RATE, total_pressure=TOTAL_PRESSURE, fan_efficiency=FAN_EFFICIENCY
    )
    return {
        "equivalent_mm": equivalent.to("mm").magnitude,
        "hydraulic_mm": hydraulic_m * 1000.0,
        "fan_watts": fan.to("W").magnitude,
    }


def main() -> None:
    r = duct_and_fan()
    print(f"500 x 250 mm duct -> equivalent diameter : {r['equivalent_mm']:.0f} mm")
    print(f"  (hydraulic 4A/P would read only {r['hydraulic_mm']:.0f} mm — do not use it here)")
    print(f"fan shaft power (1.2 m³/s, 400 Pa, 62%)  : {r['fan_watts']:.0f} W")
    print("  -> size the round chart on the equivalent diameter; the fan on Q·Δp/η")


if __name__ == "__main__":
    main()
