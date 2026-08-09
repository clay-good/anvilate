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
air-water systems (Le ≈ 1). All three are pure dimensionless ratios returned as plain floats; the
inputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "schmidt_number",
    "sherwood_number",
    "lewis_number",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
