"""Worked example: how close a boiling surface runs to burnout — the critical-heat-flux margin.

Nucleate boiling moves heat astonishingly well, but it has a cliff. As the surface is driven hotter
the flux climbs steeply — cubically, by the Rohsenow correlation — right up to a peak called the
critical heat flux. Push past that peak and the bubbles coalesce into an insulating vapor film; the
flux crashes and, on a power-controlled heater that cannot back off, the temperature
rockets by hundreds of degrees and the surface burns out. Designing a boiling surface therefore is
not about hitting a flux but about keeping a safe margin below the critical heat flux, and that
margin is the number that matters.

This example boils saturated water at 1 atm (properties: viscosity 2.79e-4 Pa·s, latent heat
2257 kJ/kg, liquid 957.9 and vapor 0.60 kg/m³, surface tension 0.0589 N/m, c_p 4217 J/kg·K,
Prandtl 1.76) on a copper surface (Rohsenow C_sf = 0.013, n = 1.0). At a 10 K wall superheat the
Rohsenow flux is about 137 kW/m². Zuber's critical heat flux for this water is about 1.26 MW/m², so
the surface runs at only about 11% of burnout — a comfortable margin, with headroom to about 21 K of
superheat before the crisis. The example reports the operating flux, the critical heat flux, and the
ratio between them, so how much boiling headroom remains is explicit.

Run it directly (``python examples/boiling_burnout_margin.py``);
:func:`boiling_margin` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    critical_heat_flux,
    nucleate_boiling_heat_flux,
)
from anvilate.units import Quantity

LIQUID_VISCOSITY = Quantity.parse("2.79e-4 Pa*s")
LATENT_HEAT = Quantity.parse("2257 kJ/kg")
LIQUID_DENSITY = Quantity.parse("957.9 kg/m**3")
VAPOR_DENSITY = Quantity.parse("0.5956 kg/m**3")
SURFACE_TENSION = Quantity.parse("0.0589 N/m")
LIQUID_SPECIFIC_HEAT = Quantity.parse("4217 J/(kg*K)")
PRANDTL = 1.76
SURFACE_FLUID_COEFFICIENT = 0.013  # water on copper
FLUID_EXPONENT = 1.0  # water
EXCESS_TEMPERATURE = Quantity.parse("10 K")


def boiling_margin() -> dict[str, float]:
    """Return the operating flux, the critical heat flux, and the fraction of burnout in use."""
    flux = nucleate_boiling_heat_flux(
        liquid_viscosity=LIQUID_VISCOSITY,
        latent_heat=LATENT_HEAT,
        liquid_density=LIQUID_DENSITY,
        vapor_density=VAPOR_DENSITY,
        surface_tension=SURFACE_TENSION,
        liquid_specific_heat=LIQUID_SPECIFIC_HEAT,
        excess_temperature=EXCESS_TEMPERATURE,
        surface_fluid_coefficient=SURFACE_FLUID_COEFFICIENT,
        prandtl_number=PRANDTL,
        fluid_exponent=FLUID_EXPONENT,
    )
    chf = critical_heat_flux(
        latent_heat=LATENT_HEAT,
        liquid_density=LIQUID_DENSITY,
        vapor_density=VAPOR_DENSITY,
        surface_tension=SURFACE_TENSION,
    )
    flux_w = flux.to("W/m**2").magnitude
    chf_w = chf.to("W/m**2").magnitude
    return {
        "operating_flux_kw_m2": flux_w / 1000.0,
        "critical_heat_flux_mw_m2": chf_w / 1.0e6,
        "fraction_of_burnout": flux_w / chf_w,
    }


def main() -> None:
    d = boiling_margin()
    print(f"operating flux at 10 K superheat: {d['operating_flux_kw_m2']:.0f} kW/m^2")
    print(f"critical heat flux (Zuber): {d['critical_heat_flux_mw_m2']:.2f} MW/m^2")
    print(
        f"running at {d['fraction_of_burnout']:.0%} of burnout "
        f"-> comfortable margin below the boiling crisis"
    )


if __name__ == "__main__":
    main()
