"""Worked example: the same duty cycle through the three DC-DC converter topologies.

A switching regulator sets its output by the duty cycle D — the fraction of each cycle its switch is
on — not by dissipating the difference like a linear regulator. The three basic non-isolated
topologies read that same duty cycle very differently: the buck steps down, the boost steps up, and
the buck-boost can go either way. Seeing all three at one duty cycle shows why the topology, not the
duty cycle alone, decides the output.

This example feeds a 12 V input at a duty cycle of 0.4 into each. The buck delivers 4.8 V (down),
the boost 20 V (up), and the buck-boost 8 V (down, since D < 0.5, and inverted in polarity). Push
the buck-boost past D = 0.5 and it would step up instead — the reason it is the go-to when input can
sit above or below the target. The example reports the output of all three topologies at D = 0.4.

Run it directly (``python examples/dc_dc_converter_topologies.py``);
:func:`converter_outputs` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    boost_output_voltage,
    buck_boost_output_voltage,
    buck_output_voltage,
)
from anvilate.units import Quantity

INPUT_VOLTAGE = Quantity.parse("12 V")
DUTY_CYCLE = 0.4


def converter_outputs() -> dict[str, float]:
    """Return the buck, boost, and buck-boost output voltages at a 0.4 duty cycle from 12 V."""
    buck = buck_output_voltage(input_voltage=INPUT_VOLTAGE, duty_cycle=DUTY_CYCLE)
    boost = boost_output_voltage(input_voltage=INPUT_VOLTAGE, duty_cycle=DUTY_CYCLE)
    buck_boost = buck_boost_output_voltage(input_voltage=INPUT_VOLTAGE, duty_cycle=DUTY_CYCLE)
    return {
        "buck_v": buck.to("V").magnitude,
        "boost_v": boost.to("V").magnitude,
        "buck_boost_v": buck_boost.to("V").magnitude,
    }


def main() -> None:
    d = converter_outputs()
    print(f"buck (step-down):     {d['buck_v']:.1f} V")
    print(f"boost (step-up):      {d['boost_v']:.1f} V")
    print(f"buck-boost (either):  {d['buck_boost_v']:.1f} V")


if __name__ == "__main__":
    main()
