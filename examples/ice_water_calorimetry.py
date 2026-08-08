"""Worked example: heating water and dropping ice into it (calorimetry).

Heating something takes energy two ways: sensible heat to raise its temperature, and latent heat to
change its phase. When a hot and a cold body mix, a heat balance sets the temperature they reach.
This example works all three for water and ice.

Warming 2 kg of water (specific heat 4,186 J/(kg·K)) by 30 K takes about 251 kJ of sensible heat.
Melting 0.5 kg of ice at 0 C takes about 167 kJ of latent heat (heat of fusion 334 kJ/kg) with no
temperature change at all. And mixing 1 kg of water at 80 C with 1 kg at 20 C — equal masses of the
same fluid — settles at their average, 50 C. This example reports the sensible heat to warm the
water, the latent heat to melt the ice, and the mixing temperature.

Run it directly (``python examples/ice_water_calorimetry.py``);
:func:`calorimetry_quantities` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    latent_heat,
    mixing_equilibrium_temperature,
    sensible_heat,
)
from anvilate.units import Quantity

WATER_SPECIFIC_HEAT = Quantity(magnitude=4186.0, unit="J/(kg*K)")
HEAT_OF_FUSION = Quantity(magnitude=334000.0, unit="J/kg")


def calorimetry_quantities() -> dict[str, float]:
    """Return the sensible heat to warm water, the latent heat to melt ice, and mixing temp."""
    q_sensible = sensible_heat(
        mass=Quantity(magnitude=2.0, unit="kg"),
        specific_heat=WATER_SPECIFIC_HEAT,
        temperature_change=Quantity(magnitude=30.0, unit="K"),
    )
    q_latent = latent_heat(
        mass=Quantity(magnitude=0.5, unit="kg"), specific_latent_heat=HEAT_OF_FUSION
    )
    t_mix = mixing_equilibrium_temperature(
        mass1=Quantity(magnitude=1.0, unit="kg"),
        specific_heat1=WATER_SPECIFIC_HEAT,
        temperature1=Quantity(magnitude=353.15, unit="K"),  # 80 C
        mass2=Quantity(magnitude=1.0, unit="kg"),
        specific_heat2=WATER_SPECIFIC_HEAT,
        temperature2=Quantity(magnitude=293.15, unit="K"),  # 20 C
    )
    return {
        "sensible_heat_kj": q_sensible.to("J").magnitude / 1000.0,
        "latent_heat_kj": q_latent.to("J").magnitude / 1000.0,
        "mixing_temperature_c": t_mix.to("K").magnitude - 273.15,
    }


def main() -> None:
    d = calorimetry_quantities()
    print(f"sensible heat to warm 2 kg water 30 K: {d['sensible_heat_kj']:.0f} kJ")
    print(f"latent heat to melt 0.5 kg ice: {d['latent_heat_kj']:.0f} kJ")
    print(f"mixing temperature: {d['mixing_temperature_c']:.0f} C")


if __name__ == "__main__":
    main()
