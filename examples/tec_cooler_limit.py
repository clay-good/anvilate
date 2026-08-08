"""Worked example: why more current stops cooling a Peltier module — Joule heat catches up.

A thermoelectric cooler pumps heat with current, but not without limit. The Peltier effect lifts the
heat from the cold face in proportion to the current, while the current's own Joule heating grows
with the square of it and dumps half back onto that same cold face. So cooling rises, peaks, and
then falls as current climbs, and even at the best current a single-stage module can only hold so
large a
temperature difference before the back-conduction and Joule heat swallow the pumping entirely. That
ceiling, ΔT_max, is fixed by the module's figure of merit, and it is why deep cooling needs cascaded
stages, not just a bigger power supply.

This example drives a module (Seebeck coefficient 0.05 V/K, resistance 2 Ω, thermal conductance
0.5 W/K) as a cooler with a 280 K cold face against a 40 K difference. At 5 A the net cooling works
out to about 25 W: 70 W of Peltier pumping, less 25 W of Joule heat returning and 20 W of conduction
leak. Held open-circuit, the same module would generate about 2 V from that 40 K difference (the
Seebeck effect). And its single-stage ceiling — the coldest it can pull with no load — is a ΔT_max
of about 98 K, so the 40 K duty sits well inside its reach. The example reports the Seebeck voltage,
net cooling, and the ΔT_max limit, so the trade the module lives within is explicit.

Run it directly (``python examples/tec_cooler_limit.py``);
:func:`tec_operating_point` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    peltier_cooling_rate,
    seebeck_voltage,
    thermoelectric_max_temperature_difference,
)
from anvilate.units import Quantity

SEEBECK_COEFFICIENT = Quantity.parse("0.05 V/K")
ELECTRICAL_RESISTANCE = Quantity.parse("2 ohm")
THERMAL_CONDUCTANCE = Quantity.parse("0.5 W/K")
CURRENT = Quantity.parse("5 A")
COLD_TEMPERATURE = Quantity.parse("280 K")
TEMPERATURE_DIFFERENCE = Quantity.parse("40 K")


def tec_operating_point() -> dict[str, float]:
    """Return the Seebeck voltage, the net Peltier cooling, and the single-stage ΔT_max limit."""
    voltage = seebeck_voltage(
        seebeck_coefficient=SEEBECK_COEFFICIENT,
        temperature_difference=TEMPERATURE_DIFFERENCE,
    )
    cooling = peltier_cooling_rate(
        seebeck_coefficient=SEEBECK_COEFFICIENT,
        current=CURRENT,
        cold_temperature=COLD_TEMPERATURE,
        electrical_resistance=ELECTRICAL_RESISTANCE,
        thermal_conductance=THERMAL_CONDUCTANCE,
        temperature_difference=TEMPERATURE_DIFFERENCE,
    )
    dt_max = thermoelectric_max_temperature_difference(
        seebeck_coefficient=SEEBECK_COEFFICIENT,
        electrical_resistance=ELECTRICAL_RESISTANCE,
        thermal_conductance=THERMAL_CONDUCTANCE,
        cold_temperature=COLD_TEMPERATURE,
    )
    return {
        "seebeck_voltage_v": voltage.to("V").magnitude,
        "net_cooling_w": cooling.to("W").magnitude,
        "max_temperature_difference_k": dt_max.to("K").magnitude,
    }


def main() -> None:
    d = tec_operating_point()
    print(f"Seebeck voltage at 40 K: {d['seebeck_voltage_v']:.1f} V")
    print(f"net cooling at 5 A: {d['net_cooling_w']:.0f} W")
    print(
        f"single-stage ceiling: {d['max_temperature_difference_k']:.0f} K "
        f"-> the 40 K duty is well inside it"
    )


if __name__ == "__main__":
    main()
