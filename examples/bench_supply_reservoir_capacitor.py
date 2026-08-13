"""Worked example: sizing the reservoir capacitor for an unregulated bench supply.

A small linear bench supply rectifies a transformer secondary (17 V peak after the bridge diode
drops) with a full-wave bridge and a reservoir capacitor, then feeds a 1 A load at 60 Hz line
frequency. We want the ripple under about 1 V peak-to-peak so a downstream 12 V regulator always has
enough headroom.

Sizing for 1 V of ripple asks for a ~8,300 µF capacitor; a standard 10,000 µF part does better,
leaving ~0.83 V of ripple and a mean DC output near 16.6 V — comfortably above the regulator's 12 V
plus its dropout. The ripple factor lands around 2%, the usual "before the regulator" figure for a
capacitor-input filter.

Run it directly (``python examples/bench_supply_reservoir_capacitor.py``);
:func:`bench_supply_filter` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    capacitor_filter_dc_voltage,
    capacitor_filter_ripple_factor,
    capacitor_filter_ripple_voltage,
    filter_capacitance_for_ripple,
)
from anvilate.units import Quantity

PEAK_VOLTAGE = Quantity.parse("17 V")
LOAD_CURRENT = Quantity.parse("1 A")
LINE_FREQUENCY = Quantity.parse("60 Hz")
TARGET_RIPPLE = Quantity.parse("1 V")
STANDARD_CAPACITOR = Quantity.parse("10000 uF")
LOAD_RESISTANCE = Quantity.parse("12 ohm")


def bench_supply_filter() -> dict[str, float]:
    """Return the sized capacitor (µF) and the chosen part's ripple, DC output, ripple factor."""
    c_needed = filter_capacitance_for_ripple(
        load_current=LOAD_CURRENT, frequency=LINE_FREQUENCY, ripple_voltage=TARGET_RIPPLE
    )
    ripple = capacitor_filter_ripple_voltage(
        load_current=LOAD_CURRENT, frequency=LINE_FREQUENCY, capacitance=STANDARD_CAPACITOR
    )
    v_dc = capacitor_filter_dc_voltage(
        peak_voltage=PEAK_VOLTAGE,
        load_current=LOAD_CURRENT,
        frequency=LINE_FREQUENCY,
        capacitance=STANDARD_CAPACITOR,
    )
    gamma = capacitor_filter_ripple_factor(
        frequency=LINE_FREQUENCY, load_resistance=LOAD_RESISTANCE, capacitance=STANDARD_CAPACITOR
    )
    return {
        "capacitor_needed_uF": c_needed.to("uF").magnitude,
        "ripple_pp_V": ripple.to("V").magnitude,
        "dc_output_V": v_dc.to("V").magnitude,
        "ripple_factor": gamma,
    }


def main() -> None:
    d = bench_supply_filter()
    print("Full-wave bench supply, 1 A load at 60 Hz:")
    print(f"  capacitor for 1 V ripple : {d['capacitor_needed_uF']:.0f} uF")
    print(f"  ripple with 10,000 uF    : {d['ripple_pp_V']:.2f} V pp")
    print(f"  mean DC output           : {d['dc_output_V']:.2f} V")
    print(f"  ripple factor            : {d['ripple_factor'] * 100:.1f} %")


if __name__ == "__main__":
    main()
