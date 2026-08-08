"""T1 analytical nucleate-boiling checks (Rohsenow / Zuber, closed-form).

Boiling is the mirror of the condensation in :mod:`anvilate.analysis.condensation`: a surface hotter
than the liquid's saturation temperature grows vapor bubbles that carry heat away as latent heat. In
the nucleate regime the bubbles stir the liquid violently and the heat flux is enormous — but only
to a limit. Push the surface too hot and the bubbles merge into a vapor blanket; the flux
collapses, the surface temperature leaps by hundreds of degrees, and a power-controlled heater burns
out. That boiling crisis, the critical heat flux, is the governing failure mode of a boiling
surface, and both it and the nucleate flux below it have closed forms.

The nucleate flux follows the Rohsenow correlation, q″ = μ_l·h_fg·√(g·Δρ/σ)·[c_pl·ΔT_e/(C_sf·h_fg·
Pr_l^n)]³, cubic in the excess temperature ΔT_e = T_s − T_sat, with the surface-fluid coefficient
C_sf and exponent n capturing the particular liquid and finish. Inverting the cube gives the surface
superheat a target flux needs. The ceiling is Zuber's critical heat flux, q″_max = 0.149·h_fg·√ρ_v·
[σ·g·Δρ]^¼ — a clean result with no empirical constant that, for water at 1 atm, lands near
1.3 MW/m². Designing a boiling surface is keeping its flux a safe margin below that number.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "critical_heat_flux",
    "nucleate_boiling_excess_temperature",
    "nucleate_boiling_heat_flux",
]


def _rohsenow_prefactor(
    liquid_viscosity: Quantity,
    latent_heat: Quantity,
    liquid_density: Quantity,
    vapor_density: Quantity,
    surface_tension: Quantity,
) -> tuple[float, float]:
    """Return (mu*h_fg*sqrt(g*Δρ/σ), h_fg) in SI, validating the shared boiling inputs."""
    _check(liquid_viscosity, "[pressure]*[time]", "liquid_viscosity")
    _check(latent_heat, "[energy]/[mass]", "latent_heat")
    _check(liquid_density, "[mass]/[length]**3", "liquid_density")
    _check(vapor_density, "[mass]/[length]**3", "vapor_density")
    _check(surface_tension, "[force]/[length]", "surface_tension")
    mu = liquid_viscosity.to("Pa*s").magnitude
    h_fg = latent_heat.to("J/kg").magnitude
    rho_l = liquid_density.to("kg/m**3").magnitude
    rho_v = vapor_density.to("kg/m**3").magnitude
    sigma = surface_tension.to("N/m").magnitude
    if mu <= 0:
        raise ValueError("liquid_viscosity must be positive")
    if h_fg <= 0:
        raise ValueError("latent_heat must be positive")
    if rho_l <= 0:
        raise ValueError("liquid_density must be positive")
    if rho_v < 0:
        raise ValueError("vapor_density must be non-negative")
    if rho_v >= rho_l:
        raise ValueError("vapor_density must be less than liquid_density")
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    prefactor = mu * h_fg * sqrt(STANDARD_GRAVITY_M_PER_S2 * (rho_l - rho_v) / sigma)
    return prefactor, h_fg


def nucleate_boiling_heat_flux(
    *,
    liquid_viscosity: Quantity,
    latent_heat: Quantity,
    liquid_density: Quantity,
    vapor_density: Quantity,
    surface_tension: Quantity,
    liquid_specific_heat: Quantity,
    excess_temperature: Quantity,
    surface_fluid_coefficient: float,
    prandtl_number: float,
    fluid_exponent: float,
) -> Quantity:
    """The Rohsenow nucleate boiling flux, q″ = μ_l·h_fg·√(g·Δρ/σ)·[c_pl·ΔT_e/(C_sf·h_fg·Pr_l^n)]³.

    The heat flux a nucleate-boiling surface carries: the Rohsenow correlation over the
    ``liquid_viscosity`` μ_l, ``latent_heat`` h_fg, ``liquid_density`` ρ_l, ``vapor_density`` ρ_v,
    ``surface_tension`` σ, ``liquid_specific_heat`` c_pl, and the surface superheat
    ``excess_temperature`` ΔT_e = T_s − T_sat, with the ``surface_fluid_coefficient`` C_sf,
    ``prandtl_number`` Pr_l, and ``fluid_exponent`` n (1.0 for water, 1.7 for other fluids) that fit
    the liquid and finish. The cube in ΔT_e makes the flux climb steeply — until the critical heat
    flux (:func:`critical_heat_flux`) caps it. Returns the flux in W/m**2.
    """
    prefactor, h_fg = _rohsenow_prefactor(
        liquid_viscosity, latent_heat, liquid_density, vapor_density, surface_tension
    )
    _check(liquid_specific_heat, "[energy]/([mass]*[temperature])", "liquid_specific_heat")
    _check(excess_temperature, "[temperature]", "excess_temperature")
    c_pl = liquid_specific_heat.to("J/(kg*K)").magnitude
    dte = excess_temperature.to("K").magnitude
    if c_pl <= 0:
        raise ValueError("liquid_specific_heat must be positive")
    if dte <= 0:
        raise ValueError("excess_temperature must be positive")
    if surface_fluid_coefficient <= 0:
        raise ValueError("surface_fluid_coefficient must be positive")
    if prandtl_number <= 0:
        raise ValueError("prandtl_number must be positive")
    if fluid_exponent <= 0:
        raise ValueError("fluid_exponent must be positive")
    bracket = c_pl * dte / (surface_fluid_coefficient * h_fg * prandtl_number**fluid_exponent)
    return Quantity(magnitude=prefactor * bracket**3, unit="W/m**2")


def nucleate_boiling_excess_temperature(
    *,
    heat_flux: Quantity,
    liquid_viscosity: Quantity,
    latent_heat: Quantity,
    liquid_density: Quantity,
    vapor_density: Quantity,
    surface_tension: Quantity,
    liquid_specific_heat: Quantity,
    surface_fluid_coefficient: float,
    prandtl_number: float,
    fluid_exponent: float,
) -> Quantity:
    """The surface superheat for a target flux, the Rohsenow correlation inverted for ΔT_e.

    Inverting the Rohsenow flux (:func:`nucleate_boiling_heat_flux`) for the surface superheat,
    ΔT_e = (C_sf·h_fg·Pr_l^n/c_pl)·(q″/(μ_l·h_fg·√(g·Δρ/σ)))^⅓: the excess temperature
    ΔT_e = T_s − T_sat needed to drive a ``heat_flux`` q″, from the same fluid properties and the
    ``surface_fluid_coefficient`` C_sf, ``prandtl_number`` Pr_l, and ``fluid_exponent`` n. It is how
    a boiling surface's wall temperature is estimated from its duty —
    and, checked against the critical heat flux (:func:`critical_heat_flux`), how much superheat
    margin remains before burnout. Returns the excess temperature in K.
    """
    prefactor, h_fg = _rohsenow_prefactor(
        liquid_viscosity, latent_heat, liquid_density, vapor_density, surface_tension
    )
    _check(heat_flux, "[power]/[area]", "heat_flux")
    _check(liquid_specific_heat, "[energy]/([mass]*[temperature])", "liquid_specific_heat")
    q = heat_flux.to("W/m**2").magnitude
    c_pl = liquid_specific_heat.to("J/(kg*K)").magnitude
    if q <= 0:
        raise ValueError("heat_flux must be positive")
    if c_pl <= 0:
        raise ValueError("liquid_specific_heat must be positive")
    if surface_fluid_coefficient <= 0:
        raise ValueError("surface_fluid_coefficient must be positive")
    if prandtl_number <= 0:
        raise ValueError("prandtl_number must be positive")
    if fluid_exponent <= 0:
        raise ValueError("fluid_exponent must be positive")
    bracket = (q / prefactor) ** (1.0 / 3.0)
    dte = surface_fluid_coefficient * h_fg * prandtl_number**fluid_exponent / c_pl * bracket
    return Quantity(magnitude=dte, unit="K")


def critical_heat_flux(
    *,
    latent_heat: Quantity,
    liquid_density: Quantity,
    vapor_density: Quantity,
    surface_tension: Quantity,
) -> Quantity:
    """Zuber's critical heat flux, q″_max = 0.149·h_fg·√ρ_v·[σ·g·Δρ]^¼.

    The peak flux a boiling surface can sustain before the boiling crisis: Zuber's hydrodynamic
    limit from the ``latent_heat`` h_fg, the ``vapor_density`` ρ_v, the ``surface_tension`` σ, and
    the liquid-vapor density difference Δρ (``liquid_density`` − ``vapor_density``), q″_max =
    0.149·h_fg·√ρ_v·[σ·g·Δρ]^¼ — a clean result with no empirical constant. Past it the bubbles
    merge into a vapor blanket, the flux collapses, and a power-controlled surface burns out; a real
    design holds well below it. For water at 1 atm it is near 1.3 MW/m². Returns the flux in W/m**2.
    """
    _check(latent_heat, "[energy]/[mass]", "latent_heat")
    _check(liquid_density, "[mass]/[length]**3", "liquid_density")
    _check(vapor_density, "[mass]/[length]**3", "vapor_density")
    _check(surface_tension, "[force]/[length]", "surface_tension")
    h_fg = latent_heat.to("J/kg").magnitude
    rho_l = liquid_density.to("kg/m**3").magnitude
    rho_v = vapor_density.to("kg/m**3").magnitude
    sigma = surface_tension.to("N/m").magnitude
    if h_fg <= 0:
        raise ValueError("latent_heat must be positive")
    if rho_l <= 0:
        raise ValueError("liquid_density must be positive")
    if rho_v <= 0:
        raise ValueError("vapor_density must be positive")
    if rho_v >= rho_l:
        raise ValueError("vapor_density must be less than liquid_density")
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    q_max = (
        0.149 * h_fg * sqrt(rho_v) * (sigma * STANDARD_GRAVITY_M_PER_S2 * (rho_l - rho_v)) ** 0.25
    )
    return Quantity(magnitude=q_max, unit="W/m**2")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
