"""Worked example: sizing a UPS battery bank, and what a shallower discharge costs in runtime.

Backup-power sizing turns a load and a ride-through time into an amp-hour number, and the usable
fraction of the battery is what makes or breaks it. This example sizes a 48 V bank to carry a 3 kW
control-room load through a 2-hour outage, drawing the batteries down to a 50% depth of discharge
(kind to cycle life) at 90% inverter efficiency. It then asks the follow-up a designer always faces:
if the same bank is only cycled to 40% depth of discharge to stretch its service life, how much
runtime is left for that 3 kW load? Shallower cycling protects the battery but shortens the outage
it can cover — the trade the depth-of-discharge number encodes.

Run it directly (``python examples/ups_battery_bank_sizing.py``);
:func:`bank_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import battery_backup_time, battery_bank_capacity
from anvilate.units import Quantity

LOAD = Quantity.parse("3 kW")
AUTONOMY = Quantity.parse("2 hour")
SYSTEM_VOLTAGE = Quantity.parse("48 V")
DESIGN_DOD = 0.5
EFFICIENCY = 0.9
CONSERVATIVE_DOD = 0.4


def bank_sizing() -> dict[str, float]:
    """Return the required capacity (Ah) and the runtime at a shallower depth of discharge (h)."""
    capacity = battery_bank_capacity(
        load_power=LOAD,
        autonomy_time=AUTONOMY,
        system_voltage=SYSTEM_VOLTAGE,
        depth_of_discharge=DESIGN_DOD,
        efficiency=EFFICIENCY,
    )
    shallow_runtime = battery_backup_time(
        rated_capacity=capacity,
        system_voltage=SYSTEM_VOLTAGE,
        load_power=LOAD,
        depth_of_discharge=CONSERVATIVE_DOD,
        efficiency=EFFICIENCY,
    )
    return {
        "capacity_ah": capacity.to("A*hour").magnitude,
        "shallow_runtime_h": shallow_runtime.to("hour").magnitude,
    }


def main() -> None:
    b = bank_sizing()
    print(f"bank capacity (50% DoD, 2 h) : {b['capacity_ah']:.0f} Ah at 48 V")
    print(f"runtime if cycled to 40% DoD : {b['shallow_runtime_h']:.1f} h for the same 3 kW")
    print("  -> shallower discharge saves the battery but shortens the outage it can ride out")


if __name__ == "__main__":
    main()
