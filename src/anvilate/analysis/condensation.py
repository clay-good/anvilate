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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.temperature import temperature_difference_kelvin

_FLUID_PROPERTY_SOURCE = "the saturated-property table at the film temperature (e.g. NIST, IAPWS)"
_SURFACE_SOURCE = "the condenser drawing (plate height, tube diameter, area, and tube rows)"
_OPERATING_SOURCE = "the operating case (saturation temperature and wall temperature)"
_COEFFICIENT_SOURCE = "the condensing heat-transfer coefficient from the Nusselt correlation"


class _CondensationInputError(RefusalError, ValueError):
    """A film-condensation input that cannot be used without correction."""


def _condensation_refusal(message: str, *, subject: str, source: str) -> _CondensationInputError:
    return _CondensationInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _condensation_input_source(name: str) -> str:
    if name == "temperature_difference":
        return _OPERATING_SOURCE
    if name in {"area", "plate_height", "tube_diameter", "tube_rows"}:
        return _SURFACE_SOURCE
    if name in {"heat_transfer_coefficient", "single_tube_coefficient"}:
        return _COEFFICIENT_SOURCE
    return _FLUID_PROPERTY_SOURCE


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
    dt = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    length = characteristic_length.to("m").magnitude
    if rho_l <= 0:
        raise _condensation_refusal(
            "liquid_density must be positive",
            subject="liquid_density",
            source=_FLUID_PROPERTY_SOURCE,
        )
    if rho_v < 0:
        raise _condensation_refusal(
            "vapor_density must be non-negative",
            subject="vapor_density",
            source=_FLUID_PROPERTY_SOURCE,
        )
    if rho_v >= rho_l:
        raise _condensation_refusal(
            "vapor_density must be less than liquid_density",
            subject="liquid_density and vapor_density",
            source=_FLUID_PROPERTY_SOURCE,
        )
    if k <= 0:
        raise _condensation_refusal(
            "liquid_thermal_conductivity must be positive",
            subject="liquid_thermal_conductivity",
            source=_FLUID_PROPERTY_SOURCE,
        )
    if mu <= 0:
        raise _condensation_refusal(
            "liquid_viscosity must be positive",
            subject="liquid_viscosity",
            source=_FLUID_PROPERTY_SOURCE,
        )
    if h_fg <= 0:
        raise _condensation_refusal(
            "latent_heat must be positive", subject="latent_heat", source=_FLUID_PROPERTY_SOURCE
        )
    if dt <= 0:
        raise _condensation_refusal(
            "temperature_difference must be positive",
            subject="temperature_difference",
            source=_OPERATING_SOURCE,
        )
    if length <= 0:
        raise _condensation_refusal(
            f"{length_name} must be positive",
            subject=length_name,
            source=_condensation_input_source(length_name),
        )
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
    dt = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    h_fg = latent_heat.to("J/kg").magnitude
    if h <= 0:
        raise _condensation_refusal(
            "heat_transfer_coefficient must be positive",
            subject="heat_transfer_coefficient",
            source=_COEFFICIENT_SOURCE,
        )
    if a <= 0:
        raise _condensation_refusal("area must be positive", subject="area", source=_SURFACE_SOURCE)
    if dt <= 0:
        raise _condensation_refusal(
            "temperature_difference must be positive",
            subject="temperature_difference",
            source=_OPERATING_SOURCE,
        )
    if h_fg <= 0:
        raise _condensation_refusal(
            "latent_heat must be positive", subject="latent_heat", source=_FLUID_PROPERTY_SOURCE
        )
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
    dt = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    h_fg = latent_heat.to("J/kg").magnitude
    if cp <= 0:
        raise _condensation_refusal(
            "specific_heat must be positive", subject="specific_heat", source=_FLUID_PROPERTY_SOURCE
        )
    if dt <= 0:
        raise _condensation_refusal(
            "temperature_difference must be positive",
            subject="temperature_difference",
            source=_OPERATING_SOURCE,
        )
    if h_fg <= 0:
        raise _condensation_refusal(
            "latent_heat must be positive", subject="latent_heat", source=_FLUID_PROPERTY_SOURCE
        )
    return cp * dt / h_fg


__all__ = [
    "condensation_rate",
    "condensation_tube_bank_coefficient",
    "film_condensation_horizontal_tube_coefficient",
    "film_condensation_vertical_plate_coefficient",
    "condensation_modified_latent_heat",
    "jakob_number",
]


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _condensation_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_condensation_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _condensation_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_condensation_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)


def condensation_modified_latent_heat(
    *, latent_heat: Quantity, specific_heat: Quantity, temperature_difference: Quantity
) -> Quantity:
    """The Rohsenow-corrected latent heat, h_fg' = h_fg·(1 + 0.68·Ja).

    :func:`jakob_number`'s own docstring names this correction and the module never applied it.
    Nusselt's film analysis assumes the condensate leaves at the saturation temperature, but the
    film is subcooled — it drains down a wall colder than saturation — so each kilogram carries
    away sensible heat on top of its latent heat, and the effective release is larger than h_fg.
    Rohsenow's integration of the film's actual temperature profile puts the surcharge at
    0.68·Ja: h_fg' = ``latent_heat`` h_fg·(1 + 0.68·Ja), with Ja = c_p·ΔT/h_fg from the liquid
    ``specific_heat`` c_p and the ``temperature_difference`` ΔT between saturation and the wall.

    Substitute it for h_fg in :func:`film_condensation_vertical_plate_coefficient`,
    :func:`film_condensation_horizontal_tube_coefficient`, or :func:`condensation_rate`. The
    correction is small where Ja is small — steam at ΔT = 10 K gains 1.3% — and grows with the
    subcooling, so it matters for a deeply subcooled surface or a low-latent-heat refrigerant. It
    is always positive, so the uncorrected form is conservative on coefficient and unconservative
    on condensate rate. Returns the modified latent heat in the units of ``latent_heat``.
    """
    _check(latent_heat, "[energy]/[mass]", "latent_heat")
    _check(specific_heat, "[energy]/([mass]*[temperature])", "specific_heat")
    _check(temperature_difference, "[temperature]", "temperature_difference")
    h_fg = latent_heat.to("J/kg").magnitude
    c_p = specific_heat.to("J/(kg*K)").magnitude
    delta_t = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    if h_fg <= 0:
        raise _condensation_refusal(
            "latent_heat must be positive", subject="latent_heat", source=_FLUID_PROPERTY_SOURCE
        )
    if c_p <= 0:
        raise _condensation_refusal(
            "specific_heat must be positive", subject="specific_heat", source=_FLUID_PROPERTY_SOURCE
        )
    if delta_t < 0:
        raise _condensation_refusal(
            "temperature_difference must be non-negative",
            subject="temperature_difference",
            source=_OPERATING_SOURCE,
        )
    jakob = c_p * delta_t / h_fg
    return Quantity(magnitude=h_fg * (1.0 + 0.68 * jakob), unit="J/kg").to(latent_heat.unit)


def condensation_tube_bank_coefficient(
    *, single_tube_coefficient: Quantity, tube_rows: float
) -> Quantity:
    """The vertical-tier tube-bank coefficient, h_N = h_1·N^−1/4.

    :func:`film_condensation_horizontal_tube_coefficient` sizes one tube in isolation, but a
    condenser stacks tubes in vertical columns and the condensate from every tube above drains onto
    the one below. The film arriving at row N is already thick, so the average coefficient over
    ``tube_rows`` N tiers falls below the ``single_tube_coefficient`` h_1. Nusselt's treatment of
    the bank as one tall tube of diameter N·D carries the same −1/4 exponent the single-tube result
    has on diameter, giving h_N = h_1·N^−1/4.

    The penalty is real and easy to forget: a four-row column delivers 71% of the single-tube
    coefficient and a ten-row column 56%, so a bank sized on the isolated-tube number is
    optimistic by that factor on area. Count rows in a vertical column, not tubes in the shell —
    tubes side by side do not drain onto each other. The relation is idealized: it assumes
    laminar film drainage between tiers, and real banks do somewhat better because the falling
    condensate splashes and ripples the film, so it is the conservative bound. N = 1 returns h_1
    unchanged. Returns the row-averaged coefficient in the units of ``single_tube_coefficient``.
    """
    _check(
        single_tube_coefficient,
        "[power]/([area]*[temperature])",
        "single_tube_coefficient",
    )
    h_1 = single_tube_coefficient.to("W/(m**2*K)").magnitude
    if h_1 <= 0:
        raise _condensation_refusal(
            "single_tube_coefficient must be positive",
            subject="single_tube_coefficient",
            source=_COEFFICIENT_SOURCE,
        )
    if tube_rows < 1:
        raise _condensation_refusal(
            "tube_rows must be at least 1", subject="tube_rows", source=_SURFACE_SOURCE
        )
    h_n = h_1 * tube_rows**-0.25
    return Quantity(magnitude=h_n, unit="W/(m**2*K)").to(single_tube_coefficient.unit)
