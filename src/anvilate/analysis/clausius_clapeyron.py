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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SATURATION_DATA_SOURCE = "the cited saturation-pressure table or measured vapor-pressure point"
_STATE_SOURCE = "the absolute operating temperature or pressure from the operating case"
_LATENT_HEAT_SOURCE = "the cited enthalpy of vaporization for the substance"


class _ClausiusClapeyronInputError(RefusalError, ValueError):
    """A vapor-pressure input that cannot be used without correction."""


def _clausius_clapeyron_refusal(
    message: str, *, subject: str, source: str
) -> _ClausiusClapeyronInputError:
    return _ClausiusClapeyronInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _clausius_clapeyron_input_source(name: str) -> str:
    if name in {
        "pressure1",
        "pressure2",
        "reference_pressure",
        "reference_temperature",
        "temperature1",
        "temperature2",
    }:
        return _SATURATION_DATA_SOURCE
    if name == "enthalpy_of_vaporization":
        return _LATENT_HEAT_SOURCE
    return _STATE_SOURCE


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
    for subject, magnitude in (
        ("reference_pressure", p1),
        ("reference_temperature", t1),
        ("temperature", t),
    ):
        if magnitude <= 0:
            raise _clausius_clapeyron_refusal(
                "pressures and temperatures must be positive",
                subject=subject,
                source=_clausius_clapeyron_input_source(subject),
            )
    if dh <= 0:
        raise _clausius_clapeyron_refusal(
            "enthalpy_of_vaporization must be positive",
            subject="enthalpy_of_vaporization",
            source=_LATENT_HEAT_SOURCE,
        )
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
    for subject, magnitude in (
        ("pressure1", p1),
        ("pressure2", p2),
        ("temperature1", t1),
        ("temperature2", t2),
    ):
        if magnitude <= 0:
            raise _clausius_clapeyron_refusal(
                "pressures and temperatures must be positive",
                subject=subject,
                source=_SATURATION_DATA_SOURCE,
            )
    if t1 == t2:
        raise _clausius_clapeyron_refusal(
            "temperature1 and temperature2 must differ",
            subject="temperature1 and temperature2",
            source=_SATURATION_DATA_SOURCE,
        )
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
    for subject, magnitude in (
        ("reference_pressure", p1),
        ("reference_temperature", t1),
        ("pressure", p),
    ):
        if magnitude <= 0:
            raise _clausius_clapeyron_refusal(
                "pressures and temperature must be positive",
                subject=subject,
                source=_clausius_clapeyron_input_source(subject),
            )
    if dh <= 0:
        raise _clausius_clapeyron_refusal(
            "enthalpy_of_vaporization must be positive",
            subject="enthalpy_of_vaporization",
            source=_LATENT_HEAT_SOURCE,
        )
    inverse_t = 1.0 / t1 - (_GAS_CONSTANT / dh) * log(p / p1)
    if inverse_t <= 0:
        raise _clausius_clapeyron_refusal(
            "the given pressure lies beyond the model's valid range (implied temperature diverges)",
            subject="pressure",
            source=_STATE_SOURCE,
        )
    return Quantity(magnitude=1.0 / inverse_t, unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _clausius_clapeyron_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_clausius_clapeyron_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _clausius_clapeyron_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_clausius_clapeyron_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
