"""T1 analytical Clausius-Clapeyron vapor-pressure relations (closed-form).

How hard a liquid pushes to evaporate climbs steeply with temperature, and the Clausius-Clapeyron
equation ties that climb to a single physical property: the enthalpy of vaporization. Integrated
between two states (taking ΔH_vap roughly constant and the vapor as an ideal gas), it reads
ln(P₂/P₁) = −(ΔH_vap/R)·(1/T₂ − 1/T₁). Unlike the empirical Antoine fit, it uses a measurable latent
heat, so it is dimensionally clean and physically grounded — the phase-equilibrium companion to the
latent heat of :mod:`anvilate.analysis.calorimetry` and the moist-air saturation pressure of
:mod:`anvilate.analysis.psychrometrics`.

The three functions solve that one relation for its three unknowns. Given a reference boiling point
(P₁, T₁) and the molar ``enthalpy_of_vaporization``, the vapor pressure at another temperature is
P = P₁·exp[(ΔH_vap/R)·(1/T₁ − 1/T)]; running it the other way gives the temperature a liquid boils
at a chosen pressure — why water boils below 100 °C up a mountain. And two measured (P, T) points on
the vapor-pressure curve return the latent heat, ΔH_vap = −R·ln(P₂/P₁)/(1/T₂ − 1/T₁), the standard
way a boiling-point experiment yields it. Temperatures must be absolute; the enthalpy is molar.
Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Cengel & Boles, *Thermodynamics: An Engineering Approach* — the Clausius-Clapeyron
relation between vapour pressure and temperature, the enthalpy of vaporisation two pressure-
temperature pairs imply, and the boiling point at a stated pressure.
"""

from __future__ import annotations

from math import exp, log

from ..units import Quantity

_GAS_CONSTANT = 8.314462618  # J/(mol*K), universal

__all__ = [
    "clausius_clapeyron_vapor_pressure",
    "clausius_clapeyron_enthalpy_of_vaporization",
    "clausius_clapeyron_boiling_temperature",
]


def clausius_clapeyron_vapor_pressure(
    *,
    reference_pressure: Quantity,
    reference_temperature: Quantity,
    temperature: Quantity,
    enthalpy_of_vaporization: Quantity,
) -> Quantity:
    """The vapor pressure at a temperature, P = P₁·exp[(ΔH_vap/R)·(1/T₁ − 1/T)].

    The saturation pressure at ``temperature`` T, from a reference point (``reference_pressure`` P₁
    at ``reference_temperature`` T₁, e.g. the normal boiling point at 1 atm) and the molar
    ``enthalpy_of_vaporization`` ΔH_vap: P = P₁·exp[(ΔH_vap/R)·(1/T₁ − 1/T)]. It rises steeply with
    temperature — a modest warming multiplies the pressure. All temperatures must be absolute.
    Returns the vapor pressure in the units of ``reference_pressure``.
    """
    _check(reference_pressure, "[pressure]", "reference_pressure")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    _check(temperature, "[temperature]", "temperature")
    _check(enthalpy_of_vaporization, "[energy]/[substance]", "enthalpy_of_vaporization")
    p1 = reference_pressure.to("Pa").magnitude
    t1 = reference_temperature.to("K").magnitude
    t = temperature.to("K").magnitude
    dh = enthalpy_of_vaporization.to("J/mol").magnitude
    if p1 <= 0 or t1 <= 0 or t <= 0:
        raise ValueError("pressures and temperatures must be positive")
    if dh <= 0:
        raise ValueError("enthalpy_of_vaporization must be positive")
    p = p1 * exp((dh / _GAS_CONSTANT) * (1.0 / t1 - 1.0 / t))
    return Quantity(magnitude=p, unit="Pa")


def clausius_clapeyron_enthalpy_of_vaporization(
    *,
    pressure1: Quantity,
    temperature1: Quantity,
    pressure2: Quantity,
    temperature2: Quantity,
) -> Quantity:
    """The latent heat from two vapor-pressure points, ΔH_vap = −R·ln(P₂/P₁)/(1/T₂ − 1/T₁).

    The molar enthalpy of vaporization backed out of two measured points on the vapor-pressure
    curve, (``pressure1`` P₁, ``temperature1`` T₁) and (``pressure2`` P₂, ``temperature2`` T₂):
    ΔH_vap = −R·ln(P₂/P₁)/(1/T₂ − 1/T₁). This is how a boiling-point-versus-pressure experiment
    yields the latent heat — the slope of ln P against 1/T. The two temperatures must differ and be
    absolute. Returns the enthalpy of vaporization in kJ/mol.
    """
    _check(pressure1, "[pressure]", "pressure1")
    _check(temperature1, "[temperature]", "temperature1")
    _check(pressure2, "[pressure]", "pressure2")
    _check(temperature2, "[temperature]", "temperature2")
    p1 = pressure1.to("Pa").magnitude
    t1 = temperature1.to("K").magnitude
    p2 = pressure2.to("Pa").magnitude
    t2 = temperature2.to("K").magnitude
    if p1 <= 0 or p2 <= 0 or t1 <= 0 or t2 <= 0:
        raise ValueError("pressures and temperatures must be positive")
    if t1 == t2:
        raise ValueError("temperature1 and temperature2 must differ")
    dh = -_GAS_CONSTANT * log(p2 / p1) / (1.0 / t2 - 1.0 / t1)
    return Quantity(magnitude=dh / 1000.0, unit="kJ/mol")


def clausius_clapeyron_boiling_temperature(
    *,
    reference_pressure: Quantity,
    reference_temperature: Quantity,
    pressure: Quantity,
    enthalpy_of_vaporization: Quantity,
) -> Quantity:
    """The boiling temperature at a pressure, T = 1/(1/T₁ − (R/ΔH_vap)·ln(P/P₁)).

    The temperature at which a liquid boils under a given ``pressure`` P, inverted from the
    Clausius-Clapeyron relation: T = 1/(1/T₁ − (R/ΔH_vap)·ln(P/P₁)), from a reference boiling point
    (``reference_pressure`` P₁ at ``reference_temperature`` T₁) and the molar
    ``enthalpy_of_vaporization`` ΔH_vap. Below the reference pressure the boiling point drops — the
    reason water boils below 100 °C at altitude and a vacuum still runs cool. Returns the boiling
    temperature in kelvin.
    """
    _check(reference_pressure, "[pressure]", "reference_pressure")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    _check(pressure, "[pressure]", "pressure")
    _check(enthalpy_of_vaporization, "[energy]/[substance]", "enthalpy_of_vaporization")
    p1 = reference_pressure.to("Pa").magnitude
    t1 = reference_temperature.to("K").magnitude
    p = pressure.to("Pa").magnitude
    dh = enthalpy_of_vaporization.to("J/mol").magnitude
    if p1 <= 0 or t1 <= 0 or p <= 0:
        raise ValueError("pressures and temperature must be positive")
    if dh <= 0:
        raise ValueError("enthalpy_of_vaporization must be positive")
    inverse_t = 1.0 / t1 - (_GAS_CONSTANT / dh) * log(p / p1)
    if inverse_t <= 0:
        raise ValueError(
            "the given pressure lies beyond the model's valid range (implied temperature diverges)"
        )
    return Quantity(magnitude=1.0 / inverse_t, unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
