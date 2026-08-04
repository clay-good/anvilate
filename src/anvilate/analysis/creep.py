"""T1 analytical creep-rupture screening (Larson-Miller parametric method).

At high temperature a metal under steady stress deforms and eventually ruptures
even below its yield strength — the time-dependent failure mode that governs
boilers, turbine blades, engine hot sections, and reformer tubes. The classic
screen is the Larson-Miller parameter, which collapses the whole
stress/temperature/time-to-rupture surface onto a single master curve:

    P = T · (C + log10 t_r)

where T is the absolute temperature, t_r the time to rupture in hours, and C a
material constant (≈ 20 for many ferritic and austenitic steels). A material's
master curve gives P as a function of stress; reading P off it at the service
stress, this module converts between the parameter, the service temperature, and
the rupture life. As with the other T1 checks the master-curve value P and the
constant C are supplied by the caller, the same way a material allowable is, and
inputs are dimension-checked :class:`~anvilate.units.Quantity` values. The
temperature must be absolute (kelvin or rankine) — the parameter is meaningless
on a Celsius scale.
"""

from __future__ import annotations

from math import log10

from ..units import Quantity

# Typical Larson-Miller constant for steels; the caller overrides it to match the
# material's own master-curve fit (it commonly runs from about 15 to 25).
LARSON_MILLER_CONSTANT = 20.0

__all__ = [
    "LARSON_MILLER_CONSTANT",
    "larson_miller_parameter",
    "larson_miller_rupture_life",
    "larson_miller_temperature_limit",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def larson_miller_parameter(
    *,
    temperature: Quantity,
    rupture_time: Quantity,
    constant: float = LARSON_MILLER_CONSTANT,
) -> float:
    """The Larson-Miller parameter P = T·(C + log10 t_r) for a creep condition.

    Combines a service ``temperature`` T and a target ``rupture_time`` t_r into the single
    parameter that indexes a material's creep master curve. ``temperature`` must be an
    **absolute** temperature (it is read in kelvin), ``rupture_time`` a time (read in
    hours), and ``constant`` the material's Larson-Miller constant C (≈ 20). Read the
    stress the master curve allows at this P and compare it to the service stress: a
    higher P (hotter, or longer required life) demands a lower allowable stress. Returns
    the parameter (in kelvin, the T·log-hours product — often quoted divided by 1000).
    """
    _require(temperature, "[temperature]", "temperature")
    _require(rupture_time, "[time]", "rupture_time")
    t_kelvin = temperature.to("K").magnitude
    hours = rupture_time.to("hour").magnitude
    if t_kelvin <= 0:
        raise ValueError("temperature must be a positive absolute temperature")
    if hours <= 0:
        raise ValueError(f"rupture_time must be positive; got {rupture_time}")
    return t_kelvin * (constant + log10(hours))


def larson_miller_rupture_life(
    *,
    parameter: float,
    temperature: Quantity,
    constant: float = LARSON_MILLER_CONSTANT,
) -> Quantity:
    """The creep-rupture life t_r = 10^(P/T − C) a Larson-Miller parameter implies.

    The inverse of :func:`larson_miller_parameter`: given the parameter ``parameter`` P
    read off the material's master curve at the service stress, and the service
    ``temperature`` T (absolute, kelvin), the time to rupture is t_r = 10^(P/T − C).
    ``constant`` is the material's Larson-Miller constant C. This is the estimated life
    of a component held at that stress and temperature — screen it against the required
    service life. A hotter service temperature collapses the life sharply. Returns the
    rupture life in hours.
    """
    _require(temperature, "[temperature]", "temperature")
    t_kelvin = temperature.to("K").magnitude
    if t_kelvin <= 0:
        raise ValueError("temperature must be a positive absolute temperature")
    exponent = parameter / t_kelvin - constant
    return Quantity(magnitude=10.0**exponent, unit="hour")


def larson_miller_temperature_limit(
    *,
    parameter: float,
    rupture_time: Quantity,
    constant: float = LARSON_MILLER_CONSTANT,
) -> Quantity:
    """The highest service temperature T = P/(C + log10 t_r) a required life allows.

    The other inverse of :func:`larson_miller_parameter`: solving for temperature gives
    the hottest a component may run and still reach ``rupture_time`` t_r at the stress
    whose master-curve value is ``parameter`` P. ``constant`` is the material constant C.
    This is the temperature margin a creep-limited design is really working to — a
    derating chart in one solve. Returns the limiting absolute temperature in kelvin.
    """
    _require(rupture_time, "[time]", "rupture_time")
    hours = rupture_time.to("hour").magnitude
    if hours <= 0:
        raise ValueError(f"rupture_time must be positive; got {rupture_time}")
    denominator = constant + log10(hours)
    if denominator <= 0:
        raise ValueError(
            "constant + log10(rupture_time in hours) must be positive; "
            "the rupture time is too short for this constant"
        )
    return Quantity(magnitude=parameter / denominator, unit="K")
