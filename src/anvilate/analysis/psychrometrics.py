"""T1 analytical psychrometric checks (moist-air properties, closed-form).

Sizing an HVAC coil, a dryer, or a cooling tower comes down to the state of moist air, and that
state is fixed by a handful of relations between temperature, humidity, and pressure.

How much water vapor the air *can* hold is set by the saturation vapor pressure, which climbs
steeply with temperature — the Magnus form p_ws = 610.94·exp(17.625·T/(T + 243.04)) captures it to
a fraction of a percent over normal conditions. How much it *does* hold is the humidity ratio
W = 0.622·p_w/(p − p_w), the mass of water per mass of dry air, and how close it is to saturation
is the relative humidity φ = p_w/p_ws. Cool the air and it eventually reaches saturation and sheds
water — the temperature where that happens is the dew point, the inverse of the Magnus curve.

Temperatures are :class:`~anvilate.units.Quantity` values (pass them in kelvin — ``"298.15 K"`` —
since pint can't parse an offset ``"25 degC"`` literal; ``.to("degC")`` on a result works fine).
Inputs and outputs are dimension-checked.
"""

from __future__ import annotations

from math import exp, log

from ..units import Quantity

__all__ = [
    "cooling_coil_load",
    "dew_point_temperature",
    "humidity_ratio",
    "latent_heat_load",
    "moist_air_enthalpy",
    "relative_humidity",
    "saturation_vapor_pressure",
    "sensible_heat_load",
    "sensible_heat_ratio",
]

# Specific-heat coefficients for moist-air enthalpy (per kg of dry air, T in deg C, h in kJ/kg):
# h = 1.006*T + W*(2501 + 1.86*T) — dry-air sensible heat plus the latent + sensible heat of the
# water vapor it carries.
_CP_DRY_AIR = 1.006
_LATENT_HEAT_0C = 2501.0
_CP_WATER_VAPOR = 1.86

# Magnus-Tetens coefficients for saturation vapor pressure over water (T in deg C, p in Pa).
_MAGNUS_A = 610.94
_MAGNUS_B = 17.625
_MAGNUS_C = 243.04
# Mass ratio of water vapor to dry air (M_water / M_air = 18.015 / 28.966).
_MASS_RATIO = 0.62198


def saturation_vapor_pressure(*, temperature: Quantity) -> Quantity:
    """The saturation vapor pressure of water in air, p_ws (Magnus formula).

    The most water vapor the air can hold at a given temperature, expressed as a partial pressure:
    p_ws = 610.94·exp(17.625·T/(T + 243.04)) with T in degrees Celsius. It roughly doubles every
    10 °C, which is why warm air carries so much more moisture. ``temperature`` T is the dry-bulb
    air temperature. Returns the saturation vapor pressure in Pa.
    """
    _check(temperature, "[temperature]", "temperature")
    if temperature.to("K").magnitude <= 0:
        raise ValueError("temperature must be above absolute zero")
    t = temperature.to("degC").magnitude
    if t <= -_MAGNUS_C:
        raise ValueError("temperature is below the valid range of the Magnus formula")
    return Quantity(magnitude=_MAGNUS_A * exp(_MAGNUS_B * t / (t + _MAGNUS_C)), unit="Pa")


def humidity_ratio(*, vapor_pressure: Quantity, total_pressure: Quantity) -> float:
    """The humidity ratio (mixing ratio) of moist air, W = 0.622·p_w/(p − p_w).

    The mass of water vapor carried per unit mass of dry air: W = 0.622·p_w/(p − p_w), from the
    ``vapor_pressure`` p_w (the water's partial pressure) and the ``total_pressure`` p (barometric).
    This is the conserved humidity measure across sensible heating and cooling — it changes only
    when water is actually added or condensed out. Returns W as a dimensionless mass ratio
    (kg water per kg dry air).
    """
    _check(vapor_pressure, "[pressure]", "vapor_pressure")
    _check(total_pressure, "[pressure]", "total_pressure")
    p_w = vapor_pressure.to("Pa").magnitude
    p = total_pressure.to("Pa").magnitude
    if p_w < 0 or p <= 0:
        raise ValueError("vapor_pressure must be non-negative and total_pressure positive")
    if p_w >= p:
        raise ValueError("vapor_pressure must be less than total_pressure")
    return _MASS_RATIO * p_w / (p - p_w)


def relative_humidity(*, vapor_pressure: Quantity, saturation_pressure: Quantity) -> float:
    """The relative humidity, φ = p_w/p_ws.

    How close the air is to saturation: the ratio of the actual ``vapor_pressure`` p_w to the
    ``saturation_pressure`` p_ws at the same temperature (from
    :func:`saturation_vapor_pressure`). Returns φ as a fraction from 0 (bone dry) to 1 (saturated);
    multiply by 100 for a percentage.
    """
    _check(vapor_pressure, "[pressure]", "vapor_pressure")
    _check(saturation_pressure, "[pressure]", "saturation_pressure")
    p_w = vapor_pressure.to("Pa").magnitude
    p_ws = saturation_pressure.to("Pa").magnitude
    if p_w < 0 or p_ws <= 0:
        raise ValueError("vapor_pressure must be non-negative and saturation_pressure positive")
    return p_w / p_ws


def dew_point_temperature(*, vapor_pressure: Quantity) -> Quantity:
    """The dew-point temperature, the inverse of the Magnus saturation curve.

    The temperature to which moist air must be cooled, at constant pressure, before it saturates
    and starts shedding water: T_dp = 243.04·γ/(17.625 − γ) where γ = ln(p_w/610.94), the inverse of
    :func:`saturation_vapor_pressure`. ``vapor_pressure`` p_w is the water's partial pressure. Cool
    a surface below the dew point and condensation forms on it. Returns the dew-point temperature in
    kelvin (call ``.to("degC")`` for Celsius).
    """
    _check(vapor_pressure, "[pressure]", "vapor_pressure")
    p_w = vapor_pressure.to("Pa").magnitude
    if p_w <= 0:
        raise ValueError("vapor_pressure must be positive")
    gamma = log(p_w / _MAGNUS_A)
    if gamma >= _MAGNUS_B:
        raise ValueError("vapor_pressure is above the valid range of the Magnus inverse")
    t_dp_celsius = _MAGNUS_C * gamma / (_MAGNUS_B - gamma)
    return Quantity(magnitude=t_dp_celsius + 273.15, unit="K")


def moist_air_enthalpy(*, temperature: Quantity, humidity_ratio: float) -> Quantity:
    """The specific enthalpy of moist air, h = 1.006·T + W·(2501 + 1.86·T) (kJ per kg dry air).

    The total heat content of the air — the number an air-conditioning coil actually changes:
    h = 1.006·T + W·(2501 + 1.86·T), the dry-air sensible heat plus the latent and sensible heat of
    the water vapor it carries, with T in degrees Celsius. ``temperature`` T is the dry-bulb
    temperature and ``humidity_ratio`` W the mass of vapor per mass of dry air (from
    :func:`humidity_ratio`). Because it rolls sensible and latent heat into one number, an enthalpy
    difference across a coil times the air flow is the total cooling or heating load — see
    :func:`cooling_coil_load`. Returns the enthalpy in kJ/kg of dry air.
    """
    _check(temperature, "[temperature]", "temperature")
    if humidity_ratio < 0:
        raise ValueError("humidity_ratio must be non-negative")
    t = temperature.to("degC").magnitude
    h = _CP_DRY_AIR * t + humidity_ratio * (_LATENT_HEAT_0C + _CP_WATER_VAPOR * t)
    return Quantity(magnitude=h, unit="kJ/kg")


def cooling_coil_load(
    *,
    dry_air_mass_flow: Quantity,
    enthalpy_in: Quantity,
    enthalpy_out: Quantity,
) -> Quantity:
    """The total cooling (or heating) load of an air coil, Q = ṁ·(h_in − h_out).

    The rate of heat a coil removes from (or adds to) an air stream, rolling sensible and latent
    together: Q = ṁ·(h_in − h_out). ``dry_air_mass_flow`` ṁ is the mass flow of *dry* air,
    ``enthalpy_in`` and ``enthalpy_out`` the moist-air enthalpies before and after the coil (from
    :func:`moist_air_enthalpy`). A positive result is cooling (enthalpy drops); the latent share is
    whatever part came from condensing moisture out. Returns the load in kW.
    """
    _check(dry_air_mass_flow, "[mass]/[time]", "dry_air_mass_flow")
    _check(enthalpy_in, "[length]**2/[time]**2", "enthalpy_in")
    _check(enthalpy_out, "[length]**2/[time]**2", "enthalpy_out")
    m_dot = dry_air_mass_flow.to("kg/s").magnitude
    h_in = enthalpy_in.to("kJ/kg").magnitude
    h_out = enthalpy_out.to("kJ/kg").magnitude
    if m_dot <= 0:
        raise ValueError("dry_air_mass_flow must be positive")
    return Quantity(magnitude=m_dot * (h_in - h_out), unit="kW")


def sensible_heat_load(
    *,
    dry_air_mass_flow: Quantity,
    temperature_change: Quantity,
    humidity_ratio: float = 0.0,
) -> Quantity:
    """The sensible portion of a coil's load, Q_s = ṁ·(1.006 + 1.86·W)·ΔT.

    The heat a coil moves by changing the air's *temperature* (at constant moisture), separate from
    the latent heat of condensing water: Q_s = ṁ·(1.006 + 1.86·W)·ΔT, from the ``dry_air_mass_flow``
    ṁ, the dry-bulb ``temperature_change`` ΔT, and the ``humidity_ratio`` W (whose vapor adds a
    little to the moist-air specific heat). It is the part of the load a fan-driven reheat or a
    sensible-only coil handles, and the numerator of the sensible heat ratio. Returns the sensible
    load in kW.
    """
    _check(dry_air_mass_flow, "[mass]/[time]", "dry_air_mass_flow")
    _check(temperature_change, "[temperature]", "temperature_change")
    m = dry_air_mass_flow.to("kg/s").magnitude
    dt = temperature_change.to("K").magnitude
    if m <= 0:
        raise ValueError("dry_air_mass_flow must be positive")
    if humidity_ratio < 0:
        raise ValueError("humidity_ratio must be non-negative")
    cp = _CP_DRY_AIR + _CP_WATER_VAPOR * humidity_ratio
    return Quantity(magnitude=m * cp * dt, unit="kW")


def latent_heat_load(
    *,
    dry_air_mass_flow: Quantity,
    humidity_ratio_change: float,
) -> Quantity:
    """The latent portion of a coil's load, Q_l = ṁ·h_fg·ΔW.

    The heat a coil moves by condensing (or evaporating) *moisture*, separate from the temperature
    change: Q_l = ṁ·h_fg·ΔW, from the ``dry_air_mass_flow`` ṁ and the ``humidity_ratio_change`` ΔW
    (kg water per kg dry air), with the latent heat of vaporization h_fg ≈ 2501 kJ/kg. It is the
    dehumidification load — the part a dry (sensible) coil cannot touch — and the reason a coil that
    holds temperature can still be working hard to pull water out of the air. Returns the latent
    load in kW.
    """
    _check(dry_air_mass_flow, "[mass]/[time]", "dry_air_mass_flow")
    m = dry_air_mass_flow.to("kg/s").magnitude
    if m <= 0:
        raise ValueError("dry_air_mass_flow must be positive")
    if humidity_ratio_change < 0:
        raise ValueError("humidity_ratio_change must be non-negative")
    return Quantity(magnitude=m * _LATENT_HEAT_0C * humidity_ratio_change, unit="kW")


def sensible_heat_ratio(*, sensible_load: Quantity, latent_load: Quantity) -> float:
    """The sensible heat ratio, SHR = Q_s/(Q_s + Q_l).

    The fraction of a coil's total load that is sensible: SHR = Q_s/(Q_s + Q_l), from the
    ``sensible_load`` Q_s and ``latent_load`` Q_l. A high SHR (near 1) is a dry, mostly-temperature
    job; a low SHR is a wet, dehumidification-heavy one — and matching a coil's inherent SHR to the
    space's is what keeps a system from overcooling to dehumidify (and then reheating). Returns the
    dimensionless ratio in [0, 1].
    """
    _check(sensible_load, "[power]", "sensible_load")
    _check(latent_load, "[power]", "latent_load")
    q_s = sensible_load.to("kW").magnitude
    q_l = latent_load.to("kW").magnitude
    if q_s < 0 or q_l < 0:
        raise ValueError("sensible_load and latent_load must be non-negative")
    total = q_s + q_l
    if total <= 0:
        raise ValueError("the total load must be positive")
    return q_s / total


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
