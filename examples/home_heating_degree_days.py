"""Worked example: a home's seasonal heating energy, and what a heat pump changes.

The degree-day method turns a winter into a single number — heating degree days, the season's total
shortfall of outdoor temperature below the balance point — and multiplies it by how leaky the house
is to get the heat it must supply. This example takes a house with a 250 W/K whole-building
heat-loss coefficient in a climate with 3000 K·day of heating degree days, and asks what heating
costs. Burning gas in a 90% furnace, it needs 20,000 kWh of fuel. Swapping to a heat pump that
delivers 3 units of heat per unit of electricity (a COP of 3) cuts the delivered energy to a third —
the same heat loss, but each kilowatt-hour of electricity moves three from outside. The method is
coarse, but it is the number a retrofit decision starts from.

Run it directly (``python examples/home_heating_degree_days.py``);
:func:`seasonal_heating` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import degree_day_heating_energy
from anvilate.units import Quantity

HEAT_LOSS_COEFFICIENT = Quantity.parse("250 W/K")
HEATING_DEGREE_DAYS = Quantity.parse("3000 K*day")
FURNACE_EFFICIENCY = 0.9
HEAT_PUMP_COP = 3.0


def seasonal_heating() -> dict[str, float]:
    """Return the seasonal heating energy for a gas furnace and a heat pump."""
    furnace = degree_day_heating_energy(
        heat_loss_coefficient=HEAT_LOSS_COEFFICIENT,
        heating_degree_days=HEATING_DEGREE_DAYS,
        system_efficiency=FURNACE_EFFICIENCY,
    )
    heat_pump = degree_day_heating_energy(
        heat_loss_coefficient=HEAT_LOSS_COEFFICIENT,
        heating_degree_days=HEATING_DEGREE_DAYS,
        system_efficiency=HEAT_PUMP_COP,
    )
    return {
        "furnace_kwh": furnace.to("kWh").magnitude,
        "heat_pump_kwh": heat_pump.to("kWh").magnitude,
    }


def main() -> None:
    s = seasonal_heating()
    print(f"gas furnace (90%)  : {s['furnace_kwh']:.0f} kWh of fuel per winter")
    print(f"heat pump (COP 3)  : {s['heat_pump_kwh']:.0f} kWh of electricity")
    print("  -> same heat loss; the heat pump moves 3 units of heat per unit of electricity")


if __name__ == "__main__":
    main()
