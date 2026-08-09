"""Worked example: how hot air's properties drift as it heats from room to furnace temperature.

A ventilation or drying calc that grabs "air viscosity" from a room-temperature table and reuses it
at 800 K is quietly wrong: a gas is not a liquid, and its viscosity and thermal conductivity both
climb steeply with temperature. This example runs Sutherland's law for dry air from 300 K up to
800 K and computes the Prandtl number at each end from the resulting properties. The viscosity rises
by roughly 90% and the conductivity more than doubles over that span, while the Prandtl number
barely moves — which is exactly why the convection correlations lean on Pr ≈ 0.7 for air and take
µ and k as the temperature-sensitive inputs. Feed the 800 K viscosity and conductivity into a
Reynolds or Nusselt number and you get a duct sized for the gas it actually carries.

Run it directly (``python examples/gas_transport_hot_air.py``);
:func:`hot_air_properties` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    prandtl_number,
    sutherland_thermal_conductivity,
    sutherland_viscosity,
)
from anvilate.units import Quantity

# Sutherland reference constants for dry air.
MU_REF = Quantity.parse("1.716e-5 Pa*s")  # at 273.15 K
K_REF = Quantity.parse("0.0241 W/(m*K)")  # at 273.15 K
T_REF = Quantity.parse("273.15 K")
S_MU = Quantity.parse("110.4 K")  # Sutherland constant for viscosity
S_K = Quantity.parse("194 K")  # Sutherland constant for conductivity
CP_AIR = Quantity.parse("1005 J/(kg*K)")  # ~constant over the range

COLD = Quantity.parse("300 K")
HOT = Quantity.parse("800 K")


def _at(temperature: Quantity) -> dict[str, float]:
    mu = sutherland_viscosity(
        temperature=temperature,
        reference_viscosity=MU_REF,
        reference_temperature=T_REF,
        sutherland_constant=S_MU,
    )
    k = sutherland_thermal_conductivity(
        temperature=temperature,
        reference_conductivity=K_REF,
        reference_temperature=T_REF,
        sutherland_constant=S_K,
    )
    pr = prandtl_number(dynamic_viscosity=mu, specific_heat=CP_AIR, thermal_conductivity=k)
    return {
        "viscosity_upa_s": mu.to("Pa*s").magnitude * 1e6,
        "conductivity_mw_mk": k.to("W/(m*K)").magnitude * 1e3,
        "prandtl": pr,
    }


def hot_air_properties() -> dict[str, float]:
    """Return air's viscosity, conductivity, and Prandtl number at 300 K and 800 K (with ratios)."""
    cold = _at(COLD)
    hot = _at(HOT)
    return {
        "cold_viscosity_upa_s": cold["viscosity_upa_s"],
        "hot_viscosity_upa_s": hot["viscosity_upa_s"],
        "cold_conductivity_mw_mk": cold["conductivity_mw_mk"],
        "hot_conductivity_mw_mk": hot["conductivity_mw_mk"],
        "cold_prandtl": cold["prandtl"],
        "hot_prandtl": hot["prandtl"],
        "viscosity_ratio": hot["viscosity_upa_s"] / cold["viscosity_upa_s"],
        "conductivity_ratio": hot["conductivity_mw_mk"] / cold["conductivity_mw_mk"],
    }


def main() -> None:
    p = hot_air_properties()
    print("dry air, Sutherland's law:")
    print(
        f"  300 K : mu = {p['cold_viscosity_upa_s']:.2f} uPa.s, "
        f"k = {p['cold_conductivity_mw_mk']:.1f} mW/m.K, Pr = {p['cold_prandtl']:.3f}"
    )
    print(
        f"  800 K : mu = {p['hot_viscosity_upa_s']:.2f} uPa.s, "
        f"k = {p['hot_conductivity_mw_mk']:.1f} mW/m.K, Pr = {p['hot_prandtl']:.3f}"
    )
    print(
        f"  -> viscosity x{p['viscosity_ratio']:.2f}, conductivity x{p['conductivity_ratio']:.2f} "
        f"over the span, but Pr barely moves"
    )


if __name__ == "__main__":
    main()
