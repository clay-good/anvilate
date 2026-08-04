"""Worked example: a solar hot-water collector near its optical ceiling — that stagnates at 181 °C.

A flat-plate collector and a PV module face the same sun but reward it in opposite ways. A PV cell
loses output as it heats; a thermal collector *wants* heat — yet the hotter its fluid runs above the
air, the faster that heat leaks back to the sky. The collector test curve packages that trade into
one line, η = η₀ − a₁·ΔT/G − a₂·ΔT²/G, and it decides two very different operating points.

This example takes a good flat plate (optical efficiency η₀ = 0.78, loss coefficients a₁ = 3.6
W/(m²·K), a₂ = 0.012 W/(m²·K²)) under a bright 950 W/m² of sun. Early on a cool morning the fluid is
barely above the 10 °C air, so almost nothing leaks and the collector runs at its optical ceiling —
η ≈ 0.77, about 0.99 of η₀, and nearly 1.8 kW reaches the tank. By afternoon the tank has driven the
mean fluid to 70 °C over 25 °C air, a 45 °C rise, and the same collector has fallen to η ≈ 0.58: the
temperature it is prized for is also what bleeds it.

Push that to the limit the design must survive — the pump fails on the hottest day and the flow
stops — and the fluid climbs until the losses swallow the entire absorbed input and efficiency hits
zero. That no-flow *stagnation* temperature, here about 181 °C above a 35 °C day, is not an
operating point but a survival one: it sets the glycol that will not cook, the pressure-relief the
loop needs, and the materials that must take it. The lesson is that a solar-thermal loop lives at
two temperatures at once — the warm one it earns its keep at, and the far hotter one it must endure.

Run it directly (``python examples/solar_collector_stagnation.py``);
:func:`collector_operating_points` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    collector_stagnation_temperature,
    collector_useful_heat,
    flat_plate_collector_efficiency,
)
from anvilate.units import Quantity

OPTICAL_EFFICIENCY = 0.78
LOSS_A1 = Quantity.parse("3.6 W/(m**2*K)")
LOSS_A2 = Quantity.parse("0.012 W/(m**2*K**2)")
AREA = Quantity.parse("2.5 m**2")


def collector_operating_points() -> dict[str, float]:
    """Return the efficiency and heat at two operating points, and the stagnation temperature."""

    def operating(mean_c: float, ambient_c: float, irradiance_wm2: float) -> dict[str, float]:
        irr = Quantity(magnitude=irradiance_wm2, unit="W/m**2")
        eta = flat_plate_collector_efficiency(
            optical_efficiency=OPTICAL_EFFICIENCY,
            loss_coefficient=LOSS_A1,
            mean_fluid_temperature=Quantity(magnitude=mean_c, unit="degC"),
            ambient_temperature=Quantity(magnitude=ambient_c, unit="degC"),
            irradiance=irr,
            second_order_loss_coefficient=LOSS_A2,
        )
        heat = collector_useful_heat(efficiency=eta, irradiance=irr, area=AREA)
        return {"efficiency": eta, "heat_w": heat.to("W").magnitude}

    morning = operating(12.0, 10.0, 950.0)  # fluid barely above air: near the optical ceiling
    afternoon = operating(70.0, 25.0, 950.0)  # hot tank, 45 C rise: losses take half

    stagnation = collector_stagnation_temperature(
        optical_efficiency=OPTICAL_EFFICIENCY,
        loss_coefficient=LOSS_A1,
        ambient_temperature=Quantity(magnitude=35.0, unit="degC"),
        irradiance=Quantity(magnitude=1000.0, unit="W/m**2"),
        second_order_loss_coefficient=LOSS_A2,
    )
    return {
        "morning_efficiency": morning["efficiency"],
        "morning_heat_w": morning["heat_w"],
        "afternoon_efficiency": afternoon["efficiency"],
        "afternoon_heat_w": afternoon["heat_w"],
        "stagnation_c": stagnation.to("degC").magnitude,
    }


def main() -> None:
    p = collector_operating_points()
    print(
        f"cool morning : eta {p['morning_efficiency']:.2f} "
        f"({p['morning_efficiency'] / OPTICAL_EFFICIENCY:.0%} of optical) "
        f"-> {p['morning_heat_w']:.0f} W to the tank"
    )
    print(
        f"hot afternoon: eta {p['afternoon_efficiency']:.2f} "
        f"-> {p['afternoon_heat_w']:.0f} W (the fluid it heats is what bleeds it)"
    )
    print(
        f"no-flow stagnation on a hot day: {p['stagnation_c']:.0f} C "
        "-> sizes the glycol, relief valve, and materials"
    )


if __name__ == "__main__":
    main()
