"""Worked example: why a 24 V DC run needs far fatter wire than its current suggests.

Low-voltage DC circuits — a solar system's battery-to-pump run, an RV, a 24 V control loop — are
governed by voltage drop, not ampacity. Two things stack against them: the current flows out and
back over the *same* length, so the drop is twice the one-way conductor loss (the factor is 2, not
the √3 of a three-phase line), and the nominal voltage is small, so even a modest absolute drop is a
large *percentage*. A volt lost on a 400 V feeder is nothing; a volt lost on 24 V is over 4%.

This example runs a 24 V DC pump drawing 15 A over a 30 m cable and compares two conductor sizes. A
4 mm² cable — ample for 15 A on ampacity alone — drops a crippling ~16%, browning the pump out. A
25 mm² cable, six times the copper, brings it under the 3% limit. The current never changed; the
lesson is that on low-voltage DC the wire is sized by the volts it must *deliver*, and the humble
factor-of-2 single-phase drop is what sets it.

Run it directly (``python examples/dc_low_voltage_run.py``);
:func:`dc_run_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import conductor_resistance, voltage_drop_single_phase
from anvilate.units import Quantity

SYSTEM_VOLTAGE = Quantity.parse("24 V")
LOAD_CURRENT = Quantity.parse("15 A")
RUN_LENGTH = Quantity.parse("30 m")
COPPER_RESISTIVITY = Quantity.parse("1.68e-8 ohm*m")
SMALL_CONDUCTOR = Quantity.parse("4 mm**2")
LARGE_CONDUCTOR = Quantity.parse("25 mm**2")
DROP_LIMIT_PERCENT = 3.0


def dc_run_check() -> dict[str, float]:
    """Return the voltage-drop percentage for each conductor size on the 24 V DC run."""
    nominal = SYSTEM_VOLTAGE.to("V").magnitude

    def drop_percent(area: Quantity) -> float:
        r = conductor_resistance(
            resistivity=COPPER_RESISTIVITY, length=RUN_LENGTH, cross_section_area=area
        )
        vd = voltage_drop_single_phase(load_current=LOAD_CURRENT, resistance=r)
        return vd.to("V").magnitude / nominal * 100.0

    return {
        "small_drop_percent": drop_percent(SMALL_CONDUCTOR),
        "large_drop_percent": drop_percent(LARGE_CONDUCTOR),
    }


def main() -> None:
    f = dc_run_check()
    small = f["small_drop_percent"]
    large = f["large_drop_percent"]
    small_ok = "OK" if small <= DROP_LIMIT_PERCENT else "FAIL"
    large_ok = "OK" if large <= DROP_LIMIT_PERCENT else "FAIL"
    print("24 V DC, 15 A over 30 m")
    print(f"4 mm2 cable  : {small:.1f}% drop  ({small_ok} vs {DROP_LIMIT_PERCENT:.0f}% limit)")
    print(f"25 mm2 cable : {large:.1f}% drop  ({large_ok} vs {DROP_LIMIT_PERCENT:.0f}% limit)")
    print("  -> low-voltage DC is sized by the volts it delivers, not its ampacity")


if __name__ == "__main__":
    main()
