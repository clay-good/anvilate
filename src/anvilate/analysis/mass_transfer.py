"""T1 analytical convective mass-transfer dimensionless groups (closed-form).

Anvilate screens convective *heat* transfer with the Reynolds, Prandtl, and Nusselt numbers of
:mod:`anvilate.analysis.thermal`, but drying, humidification, absorption, and evaporation are
governed by the analogous convective *mass* transfer — and by the same dimensionless bookkeeping
with the mass diffusivity D_AB standing in for the thermal one. This module supplies the three
groups that make the heat-and-mass-transfer analogy work, the companions to the Prandtl number of
:mod:`anvilate.analysis.gas_transport` and the Fick's-law fluxes of
:mod:`anvilate.analysis.diffusion`.

The Schmidt number Sc = ν/D_AB is the mass-transfer twin of the Prandtl number: it compares how
fast momentum diffuses to how fast a species diffuses, and sets the relative thickness of the
velocity and concentration boundary layers. The Sherwood number Sh = k_c·L/D_AB is the twin of the
Nusselt number: the dimensionless convective mass-transfer coefficient a correlation returns. The
Lewis number Le = α/D_AB compares thermal to mass diffusivity and equals Sc/Pr — it governs whether
heat or species diffuses faster, the number behind the wet-bulb/adiabatic-saturation coincidence in
air-water systems (Le ≈ 1). These three are pure dimensionless ratios.

The last three functions are the Chilton-Colburn analogy that ties momentum, heat, and mass transfer
together — the reason a friction or heat-transfer measurement predicts the other two. The Stanton
number St = Nu/(Re·Pr) is the heat-transfer coefficient made dimensionless; the Colburn j-factor
j_H = St·Pr^(2/3) collapses the Prandtl dependence so that j_H = j_M = C_f/2; and the analogy then
converts a heat-transfer coefficient h into its mass-transfer twin k_c = h/(ρ·c_p·Le^(2/3)).
All results are dimensionless plain floats except the recovered mass-transfer coefficient (a
velocity); the inputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "schmidt_number",
    "sherwood_number",
    "lewis_number",
    "stanton_number",
    "colburn_j_factor",
    "chilton_colburn_mass_transfer_coefficient",
]


def schmidt_number(*, kinematic_viscosity: Quantity, mass_diffusivity: Quantity) -> float:
    """The Schmidt number, Sc = ν/D_AB.

    The ratio of momentum diffusivity to mass diffusivity: Sc = ν/D_AB, from the
    ``kinematic_viscosity`` ν and the ``mass_diffusivity`` D_AB of the diffusing species. It is the
    mass-transfer analog of the Prandtl number and sets the relative thickness of the velocity and
    concentration boundary layers. For gases Sc ≈ 0.6 (water vapor in air ≈ 0.6); for dissolved
    species in liquids it runs into the hundreds or thousands. Returns the dimensionless Schmidt
    number as a plain float.
    """
    _check(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    _check(mass_diffusivity, "[length]**2 / [time]", "mass_diffusivity")
    nu = kinematic_viscosity.to("m**2/s").magnitude
    d = mass_diffusivity.to("m**2/s").magnitude
    if nu < 0:
        raise ValueError("kinematic_viscosity must be non-negative")
    if d <= 0:
        raise ValueError("mass_diffusivity must be positive")
    return nu / d


def sherwood_number(
    *,
    mass_transfer_coefficient: Quantity,
    characteristic_length: Quantity,
    mass_diffusivity: Quantity,
) -> float:
    """The Sherwood number, Sh = k_c·L/D_AB.

    The dimensionless convective mass-transfer coefficient: Sh = k_c·L/D_AB, from the
    ``mass_transfer_coefficient`` k_c (a velocity), the ``characteristic_length`` L, and the
    ``mass_diffusivity`` D_AB. It is the mass-transfer analog of the Nusselt number — the ratio of
    convective to diffusive mass transport — and is what a mass-transfer correlation
    (Sh = f(Re, Sc)) returns, from which k_c = Sh·D_AB/L is recovered. Returns the dimensionless
    Sherwood number as a plain float.
    """
    _check(mass_transfer_coefficient, "[length] / [time]", "mass_transfer_coefficient")
    _check(characteristic_length, "[length]", "characteristic_length")
    _check(mass_diffusivity, "[length]**2 / [time]", "mass_diffusivity")
    kc = mass_transfer_coefficient.to("m/s").magnitude
    length = characteristic_length.to("m").magnitude
    d = mass_diffusivity.to("m**2/s").magnitude
    if kc < 0:
        raise ValueError("mass_transfer_coefficient must be non-negative")
    if length <= 0:
        raise ValueError("characteristic_length must be positive")
    if d <= 0:
        raise ValueError("mass_diffusivity must be positive")
    return kc * length / d


def lewis_number(*, thermal_diffusivity: Quantity, mass_diffusivity: Quantity) -> float:
    """The Lewis number, Le = α/D_AB.

    The ratio of thermal diffusivity to mass diffusivity: Le = α/D_AB, from the
    ``thermal_diffusivity`` α and the ``mass_diffusivity`` D_AB — equivalently Le = Sc/Pr. It says
    whether heat or a species diffuses faster; when Le ≈ 1 (as for air-water vapor) the thermal and
    concentration boundary layers coincide, which is why the wet-bulb temperature nearly equals the
    adiabatic-saturation temperature. Returns the dimensionless Lewis number as a plain float.
    """
    _check(thermal_diffusivity, "[length]**2 / [time]", "thermal_diffusivity")
    _check(mass_diffusivity, "[length]**2 / [time]", "mass_diffusivity")
    alpha = thermal_diffusivity.to("m**2/s").magnitude
    d = mass_diffusivity.to("m**2/s").magnitude
    if alpha < 0:
        raise ValueError("thermal_diffusivity must be non-negative")
    if d <= 0:
        raise ValueError("mass_diffusivity must be positive")
    return alpha / d


def stanton_number(
    *, nusselt_number: float, reynolds_number: float, prandtl_number: float
) -> float:
    """The Stanton number, St = Nu/(Re·Pr).

    The convective heat-transfer coefficient in dimensionless form: St = Nu/(Re·Pr), from the
    ``nusselt_number`` Nu, ``reynolds_number`` Re, and ``prandtl_number`` Pr. It measures the heat
    actually transferred against the heat the flow could carry, and is the group the Reynolds and
    Chilton-Colburn analogies work in. Returns the dimensionless Stanton number as a plain float.
    """
    if reynolds_number <= 0:
        raise ValueError("reynolds_number must be positive")
    if prandtl_number <= 0:
        raise ValueError("prandtl_number must be positive")
    if nusselt_number < 0:
        raise ValueError("nusselt_number must be non-negative")
    return nusselt_number / (reynolds_number * prandtl_number)


def colburn_j_factor(*, stanton_number: float, prandtl_number: float) -> float:
    """The Colburn j-factor for heat transfer, j_H = St·Pr^(2/3).

    The Stanton number with its Prandtl dependence scaled out: j_H = St·Pr^(2/3), from the
    ``stanton_number`` St and ``prandtl_number`` Pr. The Chilton-Colburn analogy states j_H = j_M =
    C_f/2, so this single number ties the heat transfer to the friction factor and (through the
    mass-transfer j-factor built with Sc in place of Pr) to the mass transfer. Returns the
    dimensionless j-factor as a plain float.
    """
    if stanton_number < 0:
        raise ValueError("stanton_number must be non-negative")
    if prandtl_number <= 0:
        raise ValueError("prandtl_number must be positive")
    return stanton_number * prandtl_number ** (2.0 / 3.0)


def chilton_colburn_mass_transfer_coefficient(
    *,
    heat_transfer_coefficient: Quantity,
    density: Quantity,
    specific_heat: Quantity,
    lewis_number: float,
) -> Quantity:
    """The mass-transfer coefficient from the heat-transfer one, k_c = h/(ρ·c_p·Le^(2/3)).

    The Chilton-Colburn analogy's payoff: convert a known convective ``heat_transfer_coefficient`` h
    into its mass-transfer twin k_c = h/(ρ·c_p·Le^(2/3)), from the fluid ``density`` ρ,
    ``specific_heat`` c_p, and ``lewis_number`` Le = α/D_AB. It lets a drying rate be predicted
    from a heat-transfer correlation (or measurement) without a separate mass-transfer
    experiment; when Le ≈ 1 the two coefficients differ only through ρ·c_p. Returns k_c in m/s.
    """
    _check(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    _check(density, "[mass] / [length]**3", "density")
    _check(specific_heat, "[energy]/[mass]/[temperature]", "specific_heat")
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    rho = density.to("kg/m**3").magnitude
    cp = specific_heat.to("J/(kg*K)").magnitude
    if h < 0:
        raise ValueError("heat_transfer_coefficient must be non-negative")
    if rho <= 0 or cp <= 0:
        raise ValueError("density and specific_heat must be positive")
    if lewis_number <= 0:
        raise ValueError("lewis_number must be positive")
    kc = h / (rho * cp * lewis_number ** (2.0 / 3.0))
    return Quantity(magnitude=kc, unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
