"""Worked example: why water boils below 100 °C on a mountain, from one latent heat.

Every climber and high-altitude cook knows water boils cooler up high, so food takes longer. The
Clausius-Clapeyron equation puts a number on it from a single physical property — the enthalpy of
vaporization — and the normal boiling point as an anchor. This example takes water (ΔH_vap ≈ 40.66
kJ/mol, boiling at 100 °C under 1 atm) and works out the boiling temperature at 70 kPa, the ambient
pressure near 3,000 m, then closes the loop by recovering the latent heat from two points on the
curve.

At 70 kPa water boils at about 90 °C — a 10 °C drop that roughly doubles the cooking time for
starchy foods. Feeding the two (pressure, temperature) points back through the equation returns 40.7
kJ/mol, the latent heat we started from: the same physics read forward and backward.

Run it directly (``python examples/clausius_clapeyron_altitude_boiling.py``);
:func:`altitude_boiling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    clausius_clapeyron_boiling_temperature,
    clausius_clapeyron_enthalpy_of_vaporization,
)
from anvilate.units import Quantity

SEA_LEVEL_PRESSURE = Quantity.parse("101325 Pa")
SEA_LEVEL_BOILING = Quantity.parse("373.15 K")  # 100 C
ALTITUDE_PRESSURE = Quantity.parse("70 kPa")  # ~3,000 m
LATENT_HEAT = Quantity.parse("40660 J/mol")  # water


def altitude_boiling() -> dict[str, float]:
    """Return the high-altitude boiling temperature (C) and the latent heat recovered (kJ/mol)."""
    t_boil = clausius_clapeyron_boiling_temperature(
        reference_pressure=SEA_LEVEL_PRESSURE,
        reference_temperature=SEA_LEVEL_BOILING,
        pressure=ALTITUDE_PRESSURE,
        enthalpy_of_vaporization=LATENT_HEAT,
    )
    # Recover the latent heat from the two (P, T) points we now have on the curve.
    dh = clausius_clapeyron_enthalpy_of_vaporization(
        pressure1=SEA_LEVEL_PRESSURE,
        temperature1=SEA_LEVEL_BOILING,
        pressure2=ALTITUDE_PRESSURE,
        temperature2=t_boil,
    )
    return {
        "boiling_temperature_c": t_boil.to("K").magnitude - 273.15,
        "recovered_latent_heat_kj_mol": dh.to("kJ/mol").magnitude,
    }


def main() -> None:
    a = altitude_boiling()
    print("water, latent heat 40.66 kJ/mol, boils at 100 C under 1 atm:")
    print(f"  at 70 kPa (~3,000 m) it boils at {a['boiling_temperature_c']:.1f} C")
    print(
        f"  -> the two points recover the latent heat: "
        f"{a['recovered_latent_heat_kj_mol']:.2f} kJ/mol"
    )


if __name__ == "__main__":
    main()
