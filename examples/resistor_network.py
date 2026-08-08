"""Worked example: Ohm's law and a two-resistor parallel network.

The three most basic DC-circuit relations answer most first-cut questions: Ohm's law gives the
voltage a current develops across a resistor, the power law gives the heat it dissipates, and the
parallel rule combines resistors that share a current.

A 2 A current through a 10 ohm resistor drops 20 V across it and dissipates 40 W of heat — enough to
need a suitably rated component. Wiring that 10 ohm resistor in parallel with a 20 ohm one gives a
combined resistance of about 6.67 ohm, less than either branch, because the second path lets more
current through for the same voltage. This example reports the Ohm's-law voltage, the resistive
power, and the parallel equivalent resistance.

Run it directly (``python examples/resistor_network.py``);
:func:`resistor_network` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    ohms_law_voltage,
    parallel_resistance,
    resistive_power,
)
from anvilate.units import Quantity

CURRENT = Quantity(magnitude=2.0, unit="A")
RESISTANCE = Quantity(magnitude=10.0, unit="ohm")
SECOND_RESISTANCE = Quantity(magnitude=20.0, unit="ohm")


def resistor_network() -> dict[str, float]:
    """Return the Ohm's-law voltage, the resistive power, and the parallel resistance."""
    voltage = ohms_law_voltage(current=CURRENT, resistance=RESISTANCE)
    power = resistive_power(current=CURRENT, resistance=RESISTANCE)
    equivalent = parallel_resistance(resistances=[RESISTANCE, SECOND_RESISTANCE])
    return {
        "voltage_v": voltage.to("V").magnitude,
        "power_w": power.to("W").magnitude,
        "parallel_resistance_ohm": equivalent.to("ohm").magnitude,
    }


def main() -> None:
    d = resistor_network()
    print(f"voltage across 10 ohm at 2 A: {d['voltage_v']:.0f} V")
    print(f"power dissipated: {d['power_w']:.0f} W")
    print(f"10 ohm || 20 ohm: {d['parallel_resistance_ohm']:.2f} ohm")


if __name__ == "__main__":
    main()
