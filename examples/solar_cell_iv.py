"""Worked example: grading a solar cell from its I-V curve.

A solar cell is characterized by four points on its current-voltage curve: the open-circuit voltage,
the short-circuit current, and the voltage and current at the maximum-power point. From those, three
figures grade the cell — the fill factor (how square the curve is), the maximum power, and the
conversion efficiency. This example computes them for a production monocrystalline silicon cell.

The 156 mm cell measures V_oc = 0.68 V, I_sc = 9.5 A, and a maximum-power point of 0.57 V and 8.9 A.
Its fill factor is about 0.785 — a healthy value indicating low series-resistance loss. The maximum
power is 5.07 W (= FF*V_oc*I_sc, the same as V_mp*I_mp). Against the 1000 W/m^2 standard-test
irradiance over the cell's 0.0243 m^2 area, that is a conversion efficiency of about 20.8%. The
example reports the fill factor, the maximum power, and the efficiency.

Run it directly (``python examples/solar_cell_iv.py``);
:func:`grade_cell` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import fill_factor, solar_cell_efficiency, solar_cell_max_power
from anvilate.units import Quantity

OPEN_CIRCUIT_VOLTAGE = Quantity.parse("0.68 V")
SHORT_CIRCUIT_CURRENT = Quantity.parse("9.5 A")
MAX_POWER_VOLTAGE = Quantity.parse("0.57 V")
MAX_POWER_CURRENT = Quantity.parse("8.9 A")
IRRADIANCE = Quantity(magnitude=1000.0, unit="W/m**2")
CELL_AREA = Quantity(magnitude=0.156**2, unit="m**2")


def grade_cell() -> dict[str, float]:
    """Return the fill factor, the maximum power, and the conversion efficiency of the cell."""
    ff = fill_factor(
        max_power_voltage=MAX_POWER_VOLTAGE,
        max_power_current=MAX_POWER_CURRENT,
        open_circuit_voltage=OPEN_CIRCUIT_VOLTAGE,
        short_circuit_current=SHORT_CIRCUIT_CURRENT,
    )
    p_max = solar_cell_max_power(
        open_circuit_voltage=OPEN_CIRCUIT_VOLTAGE,
        short_circuit_current=SHORT_CIRCUIT_CURRENT,
        fill_factor=ff,
    )
    efficiency = solar_cell_efficiency(max_power=p_max, irradiance=IRRADIANCE, cell_area=CELL_AREA)
    return {
        "fill_factor": ff,
        "max_power_w": p_max.to("W").magnitude,
        "efficiency_percent": efficiency * 100.0,
    }


def main() -> None:
    d = grade_cell()
    print(f"fill factor: {d['fill_factor']:.3f}")
    print(f"maximum power: {d['max_power_w']:.2f} W")
    print(f"conversion efficiency: {d['efficiency_percent']:.1f}%")


if __name__ == "__main__":
    main()
