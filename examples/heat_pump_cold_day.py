"""Worked example: why a heat pump that sips power in autumn gulps it in a cold snap.

A heat pump is efficient because it *moves* heat rather than making it — one unit of electricity
can deliver several units of heat. But how many depends on the temperature lift it has to work
across, and thermodynamics is unforgiving: the Carnot ceiling on the heating COP is T_h/(T_h − T_c),
so as the outdoor source T_c falls away from the indoor T_h, the denominator grows and the ceiling
collapses. This example holds the indoor set point at 21 °C and drops the outdoor temperature from
a mild 7 °C to a frigid −10 °C, and shows the Carnot heating COP falling by nearly half. A real
unit tracks that ceiling at roughly a constant fraction of it, so the same heat demand that cost a
trickle of electricity in autumn costs far more in a cold snap — the reason heat pumps carry
backup heat and cold climates strain the grid on the coldest nights.

Run it directly (``python examples/heat_pump_cold_day.py``);
:func:`heat_pump_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import carnot_cop_heating, coefficient_of_performance
from anvilate.units import Quantity

INDOOR = Quantity.parse("294.15 K")  # 21 deg C set point
MILD_OUTDOOR = Quantity.parse("280.15 K")  # 7 deg C
COLD_OUTDOOR = Quantity.parse("263.15 K")  # -10 deg C
SECOND_LAW_EFFICIENCY = 0.45  # real cycle fraction of Carnot
HEAT_DEMAND = Quantity.parse("8 kW")  # steady building heat loss


def heat_pump_performance() -> dict[str, float]:
    """Return the Carnot and real heating COP and the compressor power at mild and cold outdoor."""

    def state(outdoor: Quantity) -> tuple[float, float]:
        carnot = carnot_cop_heating(cold_temperature=outdoor, hot_temperature=INDOOR)
        real_cop = SECOND_LAW_EFFICIENCY * carnot
        # Compressor power to meet the fixed heat demand at this real COP.
        power = HEAT_DEMAND.to("kW").magnitude / real_cop
        # Confirm the actual-COP helper agrees with capacity / power.
        _ = coefficient_of_performance(
            capacity=HEAT_DEMAND, power_input=Quantity(magnitude=power, unit="kW")
        )
        return carnot, power

    mild_carnot, mild_power = state(MILD_OUTDOOR)
    cold_carnot, cold_power = state(COLD_OUTDOOR)
    return {
        "mild_carnot_cop": mild_carnot,
        "cold_carnot_cop": cold_carnot,
        "mild_power_kw": mild_power,
        "cold_power_kw": cold_power,
    }


def main() -> None:
    p = heat_pump_performance()
    mild_cop, mild_kw = p["mild_carnot_cop"], p["mild_power_kw"]
    cold_cop, cold_kw = p["cold_carnot_cop"], p["cold_power_kw"]
    print(f"outdoor +7 C  : Carnot COP {mild_cop:.1f}, compressor draws {mild_kw:.1f} kW")
    print(f"outdoor -10 C : Carnot COP {cold_cop:.1f}, compressor draws {cold_kw:.1f} kW")
    more = cold_kw / mild_kw - 1
    print(f"  -> same 8 kW of heat costs {more:.0%} more power on the cold day")


if __name__ == "__main__":
    main()
