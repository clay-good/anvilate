"""Worked example: sizing a motor feeder so the motor at the far end still starts.

A conductor sized only for its ampacity — enough copper not to overheat — can still be wrong, and
the reason is voltage drop. Current flowing down a long run loses voltage to the conductor's own
resistance, and a motor at the end of a skimpy feeder may see too little voltage to develop
starting torque or to run without overheating. The check is simple: find the load current, the
conductor resistance, and the three-phase voltage drop, and keep it under the customary 3% of
nominal. This example feeds a 30 kW motor at 400 V over a 120 m run and compares two conductor
sizes — a 16 mm² cable that overheats the voltage budget and a 35 mm² one that stays within it. The
larger conductor isn't about ampacity here; it's about delivering usable voltage to the far end.

Run it directly (``python examples/motor_feeder_voltage_drop.py``);
:func:`feeder_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    conductor_resistance,
    line_current_for_power,
    voltage_drop_three_phase,
)
from anvilate.units import Quantity

MOTOR_POWER = Quantity.parse("30 kW")
LINE_VOLTAGE = Quantity.parse("400 V")
POWER_FACTOR = 0.85
RUN_LENGTH = Quantity.parse("200 m")
COPPER_RESISTIVITY = Quantity.parse("1.68e-8 ohm*m")
SMALL_CONDUCTOR = Quantity.parse("16 mm**2")
LARGE_CONDUCTOR = Quantity.parse("35 mm**2")
DROP_LIMIT_PERCENT = 3.0


def feeder_check() -> dict[str, float]:
    """Return the load current (A) and the voltage-drop percentage for each conductor size."""
    current = line_current_for_power(
        real_power=MOTOR_POWER, line_voltage=LINE_VOLTAGE, power_factor=POWER_FACTOR
    )
    nominal = LINE_VOLTAGE.to("V").magnitude

    def drop_percent(area: Quantity) -> float:
        r = conductor_resistance(
            resistivity=COPPER_RESISTIVITY, length=RUN_LENGTH, cross_section_area=area
        )
        vd = voltage_drop_three_phase(line_current=current, resistance=r, power_factor=POWER_FACTOR)
        return vd.to("V").magnitude / nominal * 100.0

    return {
        "current_a": current.to("A").magnitude,
        "small_drop_percent": drop_percent(SMALL_CONDUCTOR),
        "large_drop_percent": drop_percent(LARGE_CONDUCTOR),
    }


def main() -> None:
    f = feeder_check()
    print(f"load current : {f['current_a']:.0f} A for the 30 kW motor")
    small = f["small_drop_percent"]
    large = f["large_drop_percent"]
    small_ok = "OK" if small <= DROP_LIMIT_PERCENT else "FAIL"
    large_ok = "OK" if large <= DROP_LIMIT_PERCENT else "FAIL"
    print(f"16 mm2 cable : {small:.1f}% drop  ({small_ok} vs {DROP_LIMIT_PERCENT:.0f}% limit)")
    print(f"35 mm2 cable : {large:.1f}% drop  ({large_ok} vs {DROP_LIMIT_PERCENT:.0f}% limit)")
    print("  -> the bigger conductor is about delivering usable voltage, not just ampacity")


if __name__ == "__main__":
    main()
