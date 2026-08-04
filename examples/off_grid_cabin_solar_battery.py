"""Worked example: sizing an off-grid cabin's solar array and battery bank together.

An off-grid system is two sizing problems that share one number — the daily energy demand. The array
must collect that energy from the sun the site actually gets; the battery must store enough of it to
ride through the nights and cloudy days when the array makes nothing. This example takes a cabin
that uses 6 kWh a day at a site with 4.5 peak sun hours. It sizes the PV array (with a 0.78 derate
inverter, wiring, and soiling losses) to meet that demand, then sizes a 48 V battery bank to carry
two full days of autonomy at a 50% depth of discharge and 90% round-trip efficiency. Together they
are the off-grid rule of thumb made explicit: enough panel to refill the load each sunny day, enough
battery to coast through the days without sun.

Run it directly (``python examples/off_grid_cabin_solar_battery.py``);
:func:`off_grid_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import battery_bank_capacity, pv_array_size_for_load
from anvilate.units import Quantity

DAILY_DEMAND = Quantity.parse("6 kWh")
PEAK_SUN_HOURS = Quantity.parse("4.5 hour")
DERATE = 0.78
AUTONOMY = Quantity.parse("2 day")
SYSTEM_VOLTAGE = Quantity.parse("48 V")
DEPTH_OF_DISCHARGE = 0.5
BATTERY_EFFICIENCY = 0.9


def off_grid_sizing() -> dict[str, float]:
    """Return the required PV array rating (W) and battery bank capacity (Ah)."""
    array = pv_array_size_for_load(
        daily_energy_demand=DAILY_DEMAND,
        peak_sun_hours=PEAK_SUN_HOURS,
        derate_factor=DERATE,
    )
    # Average load over the autonomy window drives the battery: daily energy / 24 h.
    average_load = Quantity(magnitude=DAILY_DEMAND.to("Wh").magnitude / 24.0, unit="W")
    bank = battery_bank_capacity(
        load_power=average_load,
        autonomy_time=AUTONOMY,
        system_voltage=SYSTEM_VOLTAGE,
        depth_of_discharge=DEPTH_OF_DISCHARGE,
        efficiency=BATTERY_EFFICIENCY,
    )
    return {
        "array_watts": array.to("W").magnitude,
        "bank_amp_hours": bank.to("A*hour").magnitude,
    }


def main() -> None:
    s = off_grid_sizing()
    print(f"PV array rating : {s['array_watts']:.0f} W (6 kWh/day, 4.5 sun hours, 0.78 derate)")
    print(f"battery bank    : {s['bank_amp_hours']:.0f} Ah at 48 V (2 days, 50% DoD, 90%)")
    print("  -> array refills the daily load; battery coasts through the sunless days")


if __name__ == "__main__":
    main()
