"""T1 analytical film-condensation heat-transfer checks (Nusselt, closed-form).

When a vapor touches a surface below its saturation temperature it condenses, and in filmwise
condensation the liquid drains as a continuous film that the rest of the vapor must conduct through.
Nusselt's 1916 analysis of that draining film gives the heat-transfer coefficient in closed form,
and it is a different regime from the single-phase convection of :mod:`anvilate.analysis.thermal`:
the latent heat freed at the film's surface makes condensation an order of magnitude more effective
than gas convection, which is why condensers can be compact.

The coefficient depends on the properties of the *liquid* film — its density ρ_l, thermal
conductivity k_l, and viscosity μ_l — the vapor density ρ_v it drains against, the latent heat h_fg
freed per unit mass, the subcooling ΔT = T_sat − T_s driving it, and the length the film runs. For a
vertical plate of height L, h = 0.943·[ρ_l·(ρ_l − ρ_v)·g·h_fg·k_l³/(μ_l·ΔT·L)]^¼; for a horizontal
tube of diameter D the film is shorter, so the coefficient rises and the constant changes to 0.729
over D. Either way the wall's heat flux h·A·ΔT sets the condensate produced, ṁ = h·A·ΔT/h_fg — the
rate a condenser must drain away.
"""

from __future__ import annotations

from ..units import Quantity

STANDARD_GRAVITY_M_PER_S2 = 9.80665


def _nusselt_coefficient(
    *,
    constant: float,
    liquid_density: Quantity,
    vapor_density: Quantity,
    liquid_thermal_conductivity: Quantity,
    liquid_viscosity: Quantity,
    latent_heat: Quantity,
    temperature_difference: Quantity,
    characteristic_length: Quantity,
    length_name: str,
) -> Quantity:
    _check(liquid_density, "[mass]/[length]**3", "liquid_density")
    _check(vapor_density, "[mass]/[length]**3", "vapor_density")
    _check(
        liquid_thermal_conductivity,
        "[power]/([length]*[temperature])",
        "liquid_thermal_conductivity",
    )
    _check(liquid_viscosity, "[pressure]*[time]", "liquid_viscosity")
    _check(latent_heat, "[energy]/[mass]", "latent_heat")
    _check(temperature_difference, "[temperature]", "temperature_difference")
    _check(characteristic_length, "[length]", length_name)
    rho_l = liquid_density.to("kg/m**3").magnitude
    rho_v = vapor_density.to("kg/m**3").magnitude
    k = liquid_thermal_conductivity.to("W/(m*K)").magnitude
    mu = liquid_viscosity.to("Pa*s").magnitude
    h_fg = latent_heat.to("J/kg").magnitude
    dt = temperature_difference.to("K").magnitude
    length = characteristic_length.to("m").magnitude
    if rho_l <= 0:
        raise ValueError("liquid_density must be positive")
    if rho_v < 0:
        raise ValueError("vapor_density must be non-negative")
    if rho_v >= rho_l:
        raise ValueError("vapor_density must be less than liquid_density")
    if k <= 0:
        raise ValueError("liquid_thermal_conductivity must be positive")
    if mu <= 0:
        raise ValueError("liquid_viscosity must be positive")
    if h_fg <= 0:
        raise ValueError("latent_heat must be positive")
    if dt <= 0:
        raise ValueError("temperature_difference must be positive")
    if length <= 0:
        raise ValueError(f"{length_name} must be positive")
    numerator = rho_l * (rho_l - rho_v) * STANDARD_GRAVITY_M_PER_S2 * h_fg * k**3
    h = constant * (numerator / (mu * dt * length)) ** 0.25
    return Quantity(magnitude=h, unit="W/(m**2*K)")


def film_condensation_vertical_plate_coefficient(
    *,
    liquid_density: Quantity,
    vapor_density: Quantity,
    liquid_thermal_conductivity: Quantity,
    liquid_viscosity: Quantity,
    latent_heat: Quantity,
    temperature_difference: Quantity,
    plate_height: Quantity,
) -> Quantity:
    """The Nusselt vertical-plate coefficient, h = 0.943·[ρ_l(ρ_l−ρ_v)g·h_fg·k_l³/(μ_l·ΔT·L)]^¼.

    The average film-condensation coefficient over a vertical plate of ``plate_height`` L: from the
    condensate's ``liquid_density`` ρ_l, ``liquid_thermal_conductivity`` k_l, ``liquid_viscosity``
    μ_l, the ``vapor_density`` ρ_v it drains against, the ``latent_heat`` h_fg, and the subcooling
    ``temperature_difference`` ΔT = T_sat − T_s. The film thickens down the plate, so a taller plate
    has a lower average coefficient (h ∝ L^−¼). Returns the coefficient in W/(m**2*K).
    """
    return _nusselt_coefficient(
        constant=0.943,
        liquid_density=liquid_density,
        vapor_density=vapor_density,
        liquid_thermal_conductivity=liquid_thermal_conductivity,
        liquid_viscosity=liquid_viscosity,
        latent_heat=latent_heat,
        temperature_difference=temperature_difference,
        characteristic_length=plate_height,
        length_name="plate_height",
    )


def film_condensation_horizontal_tube_coefficient(
    *,
    liquid_density: Quantity,
    vapor_density: Quantity,
    liquid_thermal_conductivity: Quantity,
    liquid_viscosity: Quantity,
    latent_heat: Quantity,
    temperature_difference: Quantity,
    tube_diameter: Quantity,
) -> Quantity:
    """The Nusselt horizontal-tube coefficient, h = 0.729·[ρ_l(ρ_l−ρ_v)g·h_fg·k_l³/(μ_l·ΔT·D)]^¼.

    The average film-condensation coefficient on a horizontal tube of ``tube_diameter`` D: the same
    Nusselt balance as the vertical plate (:func:`film_condensation_vertical_plate_coefficient`) but
    over the short drainage path around a tube, so the constant is 0.729 and the length is the
    diameter D. The shorter film makes a tube more effective than a tall plate of like properties,
    which is why condensers are built from horizontal tube banks. Returns the coefficient in
    W/(m**2*K).
    """
    return _nusselt_coefficient(
        constant=0.729,
        liquid_density=liquid_density,
        vapor_density=vapor_density,
        liquid_thermal_conductivity=liquid_thermal_conductivity,
        liquid_viscosity=liquid_viscosity,
        latent_heat=latent_heat,
        temperature_difference=temperature_difference,
        characteristic_length=tube_diameter,
        length_name="tube_diameter",
    )


def condensation_rate(
    *,
    heat_transfer_coefficient: Quantity,
    area: Quantity,
    temperature_difference: Quantity,
    latent_heat: Quantity,
) -> Quantity:
    """The condensate mass rate, ṁ = h·A·ΔT/h_fg.

    The mass of vapor a surface condenses per unit time: the wall heat flux — the
    ``heat_transfer_coefficient`` h (from the Nusselt forms above) over the ``area`` A at the
    subcooling ``temperature_difference`` ΔT — divided by the ``latent_heat`` h_fg each unit mass
    gives up, ṁ = h·A·ΔT/h_fg. It is the drainage the condenser must handle and the throughput it is
    sized on. Returns the condensate rate in kg/s.
    """
    _check(heat_transfer_coefficient, "[power]/([area]*[temperature])", "heat_transfer_coefficient")
    _check(area, "[area]", "area")
    _check(temperature_difference, "[temperature]", "temperature_difference")
    _check(latent_heat, "[energy]/[mass]", "latent_heat")
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    a = area.to("m**2").magnitude
    dt = temperature_difference.to("K").magnitude
    h_fg = latent_heat.to("J/kg").magnitude
    if h <= 0:
        raise ValueError("heat_transfer_coefficient must be positive")
    if a <= 0:
        raise ValueError("area must be positive")
    if dt <= 0:
        raise ValueError("temperature_difference must be positive")
    if h_fg <= 0:
        raise ValueError("latent_heat must be positive")
    return Quantity(magnitude=h * a * dt / h_fg, unit="kg/s")


def jakob_number(
    *, specific_heat: Quantity, temperature_difference: Quantity, latent_heat: Quantity
) -> float:
    """The Jakob number, Ja = c_p·ΔT/h_fg.

    The ratio of sensible heat to latent heat in a phase change: from the liquid ``specific_heat``
    c_p, the subcooling or superheat ``temperature_difference`` ΔT, and the ``latent_heat`` h_fg,
    Ja = c_p·ΔT/h_fg. It measures how much sensible heating the condensate (or vapor) carries
    alongside the latent heat of the change — small for water near atmospheric pressure, where the
    latent heat dominates. It sets the h_fg' = h_fg·(1 + 0.68·Ja) correction to Nusselt's film
    coefficient and scales the sensible load in boiling and melting. Returns the Jakob number as a
    plain float.
    """
    _check(specific_heat, "[energy]/[mass]/[temperature]", "specific_heat")
    _check(temperature_difference, "[temperature]", "temperature_difference")
    _check(latent_heat, "[energy]/[mass]", "latent_heat")
    cp = specific_heat.to("J/(kg*K)").magnitude
    dt = temperature_difference.to("K").magnitude
    h_fg = latent_heat.to("J/kg").magnitude
    if cp <= 0:
        raise ValueError("specific_heat must be positive")
    if dt <= 0:
        raise ValueError("temperature_difference must be positive")
    if h_fg <= 0:
        raise ValueError("latent_heat must be positive")
    return cp * dt / h_fg


__all__ = [
    "condensation_rate",
    "film_condensation_horizontal_tube_coefficient",
    "film_condensation_vertical_plate_coefficient",
    "jakob_number",
]


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
