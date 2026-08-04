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
    "dew_point_temperature",
    "humidity_ratio",
    "relative_humidity",
    "saturation_vapor_pressure",
]

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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
