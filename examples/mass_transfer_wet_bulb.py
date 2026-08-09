"""Worked example: why a wet-bulb thermometer reads the air's saturation temperature.

Air blowing over a wet surface carries away both heat (cooling the surface) and water vapor
(evaporating it). Whether those two processes balance — and so whether the wet-bulb temperature a
psychrometer reads equals the adiabatic-saturation temperature — is decided by a single
dimensionless number, the Lewis number Le = α/D_AB. For the air-water system Le sits very close to
1, which is exactly why the two temperatures nearly coincide and the sling psychrometer works.

This example takes 25 °C air (kinematic viscosity, thermal diffusivity) and the diffusivity of
water vapor in air, and forms the three convective mass-transfer groups: the Schmidt number
(the Prandtl twin), the Sherwood number for a 0.1 m wetted plate with a measured mass-transfer
coefficient, and the Lewis number. It confirms the analogy identity Le = Sc/Pr and shows Le ≈ 0.85
— near enough to 1 that the heat and mass boundary layers track each other.

Run it directly (``python examples/mass_transfer_wet_bulb.py``);
:func:`air_water_groups` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    lewis_number,
    prandtl_number,
    schmidt_number,
    sherwood_number,
)
from anvilate.units import Quantity

# Dry air at ~25 C.
KINEMATIC_VISCOSITY = Quantity.parse("1.56e-5 m**2/s")  # nu
THERMAL_DIFFUSIVITY = Quantity.parse("2.22e-5 m**2/s")  # alpha
# Water vapor diffusing in air at ~25 C.
VAPOR_DIFFUSIVITY = Quantity.parse("2.60e-5 m**2/s")  # D_AB

# A wetted plate and its measured convective mass-transfer coefficient.
PLATE_LENGTH = Quantity.parse("0.1 m")
MASS_TRANSFER_COEFFICIENT = Quantity.parse("0.011 m/s")  # k_c


def air_water_groups() -> dict[str, float]:
    """Return Sc, Sh, Le for air-water vapor, plus Pr and the Sc/Pr check on Le."""
    sc = schmidt_number(
        kinematic_viscosity=KINEMATIC_VISCOSITY,
        mass_diffusivity=VAPOR_DIFFUSIVITY,
    )
    sh = sherwood_number(
        mass_transfer_coefficient=MASS_TRANSFER_COEFFICIENT,
        characteristic_length=PLATE_LENGTH,
        mass_diffusivity=VAPOR_DIFFUSIVITY,
    )
    le = lewis_number(
        thermal_diffusivity=THERMAL_DIFFUSIVITY,
        mass_diffusivity=VAPOR_DIFFUSIVITY,
    )
    # Pr = mu*cp/k = nu/alpha for the same air (rho cancels): mu = nu*rho, k = alpha*rho*cp with
    # rho = 1.184 kg/m^3, so the analogy identity Le = Sc/Pr closes to three digits.
    pr = prandtl_number(
        dynamic_viscosity=Quantity.parse("1.847e-5 Pa*s"),
        specific_heat=Quantity.parse("1007 J/(kg*K)"),
        thermal_conductivity=Quantity.parse("0.02647 W/(m*K)"),
    )
    return {
        "schmidt": sc,
        "sherwood": sh,
        "lewis": le,
        "prandtl": pr,
        "lewis_via_sc_over_pr": sc / pr,
    }


def main() -> None:
    g = air_water_groups()
    print("air-water vapor at ~25 C:")
    print(f"  Schmidt  Sc = {g['schmidt']:.3f}  (Prandtl twin; Pr = {g['prandtl']:.3f})")
    print(f"  Sherwood Sh = {g['sherwood']:.1f}   (dimensionless k_c for the 0.1 m plate)")
    print(f"  Lewis    Le = {g['lewis']:.3f}  (= Sc/Pr = {g['lewis_via_sc_over_pr']:.3f})")
    print("  -> Le is close to 1, so wet-bulb ~ adiabatic-saturation temperature")


if __name__ == "__main__":
    main()
