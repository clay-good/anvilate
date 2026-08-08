"""Worked example: why condensers are built from horizontal tubes — the film drains shorter.

Filmwise condensation is one of the most effective ways to move heat: as steam gives up its latent
heat on a cold surface, the condensate forms a thin liquid film, and the heat need only cross
that film. The thinner the film, the higher the coefficient — and film thickness grows with the
distance the condensate has to drain. A tall vertical plate builds a thick film near its bottom and
suffers for it; a horizontal tube gives the film only half a small diameter to drain over, so it
stays thin and the coefficient stays high. That is the whole reason a steam condenser is a bank of
horizontal tubes rather than vertical sheets.

This example condenses saturated steam at 100 °C (latent heat 2257 kJ/kg) with the surface held 15 K
cooler, using the condensate's properties at the film temperature (density 965 kg/m³, conductivity
0.68 W/m·K, viscosity 3.15e-4 Pa·s). On a 1 m tall vertical plate the Nusselt coefficient is about
5700 W/m²·K; on a 25 mm horizontal tube — a far shorter drainage path — it rises to about 11200,
roughly double. Both are an order of magnitude above the tens-of-W/m²·K a gas gives in single-phase
convection. Over 2 m² at the tube coefficient the surface condenses about 0.15 kg/s of steam. The
example reports both coefficients and the condensate rate, so the tube-versus-plate edge and the
drainage it implies are explicit.

Run it directly (``python examples/steam_condenser_coefficient.py``);
:func:`condenser_duty` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    condensation_rate,
    film_condensation_horizontal_tube_coefficient,
    film_condensation_vertical_plate_coefficient,
)
from anvilate.units import Quantity

LIQUID_DENSITY = Quantity.parse("965 kg/m**3")
VAPOR_DENSITY = Quantity.parse("0.6 kg/m**3")
LIQUID_CONDUCTIVITY = Quantity.parse("0.68 W/(m*K)")
LIQUID_VISCOSITY = Quantity.parse("3.15e-4 Pa*s")
LATENT_HEAT = Quantity.parse("2257 kJ/kg")
SUBCOOLING = Quantity.parse("15 K")
PLATE_HEIGHT = Quantity.parse("1 m")
TUBE_DIAMETER = Quantity.parse("25 mm")
TUBE_AREA = Quantity.parse("2 m**2")

_PROPS = {
    "liquid_density": LIQUID_DENSITY,
    "vapor_density": VAPOR_DENSITY,
    "liquid_thermal_conductivity": LIQUID_CONDUCTIVITY,
    "liquid_viscosity": LIQUID_VISCOSITY,
    "latent_heat": LATENT_HEAT,
    "temperature_difference": SUBCOOLING,
}


def condenser_duty() -> dict[str, float]:
    """Return the vertical-plate and horizontal-tube coefficients and the condensate rate."""
    h_plate = film_condensation_vertical_plate_coefficient(plate_height=PLATE_HEIGHT, **_PROPS)
    h_tube = film_condensation_horizontal_tube_coefficient(tube_diameter=TUBE_DIAMETER, **_PROPS)
    rate = condensation_rate(
        heat_transfer_coefficient=h_tube,
        area=TUBE_AREA,
        temperature_difference=SUBCOOLING,
        latent_heat=LATENT_HEAT,
    )
    return {
        "plate_coefficient": h_plate.to("W/(m**2*K)").magnitude,
        "tube_coefficient": h_tube.to("W/(m**2*K)").magnitude,
        "condensate_rate_kg_s": rate.to("kg/s").magnitude,
    }


def main() -> None:
    d = condenser_duty()
    print(f"vertical plate (1 m): {d['plate_coefficient']:.0f} W/m^2K")
    print(f"horizontal tube (25 mm): {d['tube_coefficient']:.0f} W/m^2K (shorter film -> higher)")
    print(f"condensate rate over 2 m^2 of tube: {d['condensate_rate_kg_s']:.2f} kg/s")


if __name__ == "__main__":
    main()
