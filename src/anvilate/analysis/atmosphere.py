"""T1 analytical barometric (isothermal-atmosphere) checks (closed-form).

Air is a compressible gas, so the pressure of the atmosphere does not fall linearly with height the
way the incompressible hydrostatic law p = ρgh of :mod:`anvilate.analysis.fluid_statics` would
predict for a liquid column. Instead, because the gas thins as the pressure drops, the pressure
decays *exponentially* with altitude. Treating the column as isothermal (a good approximation over a
few kilometres) gives the barometric formula, the basis of every pressure altimeter.

The pressure at altitude h is p = p₀·exp(−M·g·h/(R·T)), from the sea-level pressure p₀, the molar
mass of the gas M (about 0.029 kg/mol for air), gravity g, the universal gas constant R, and the
absolute temperature T. The grouping H = R·T/(M·g) is the *scale height* — the altitude over which
the pressure falls by a factor of e, about 8.4 km for air at 15 °C. Inverting the barometric formula
recovers the altitude from a measured pressure ratio, h = H·ln(p₀/p), which is how a barometric
altimeter reads height. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Anderson, *Introduction to Flight* (the standard atmosphere) — the scale height, the
isothermal barometric relation and its inversion to altitude, and the gradient-layer form for a
constant lapse rate. The layer structure is that of the ISO 2533 / U.S. Standard Atmosphere.
"""

from __future__ import annotations

from math import exp, log

from ..units import Quantity

_UNIVERSAL_GAS_CONSTANT = 8.314462618  # J/(mol*K)
_STANDARD_GRAVITY = 9.80665  # m/s**2
_MOLAR_MASS_AIR = 0.0289647  # kg/mol, dry air
_ISA_LAPSE_RATE = 0.0065  # K/m, the ISA troposphere temperature gradient
_ISA_TROPOPAUSE_ALTITUDE = 11000.0  # m, where the ISA troposphere ends and the lapse stops

__all__ = [
    "barometric_altitude",
    "barometric_pressure",
    "lapse_rate_pressure",
    "scale_height",
]


def scale_height(*, temperature: Quantity, molar_mass: Quantity | None = None) -> Quantity:
    """The atmospheric scale height, H = R*T/(M*g).

    The altitude over which an isothermal atmosphere's pressure falls by a factor of e, from the
    absolute ``temperature`` T and the gas ``molar_mass`` M (defaulting to dry air, 0.029 kg/mol):
    H = R*T/(M*g). It is about 8.4 km for air at 15 °C — warmer or lighter gas gives a taller
    atmosphere. Returns the scale height in m.
    """
    _check(temperature, "[temperature]", "temperature")
    t = temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    m = _molar_mass_value(molar_mass)
    h = _UNIVERSAL_GAS_CONSTANT * t / (m * _STANDARD_GRAVITY)
    return Quantity(magnitude=h, unit="m")


def barometric_pressure(
    *,
    sea_level_pressure: Quantity,
    altitude: Quantity,
    temperature: Quantity,
    molar_mass: Quantity | None = None,
) -> Quantity:
    """The barometric pressure at altitude, p = p0*exp(-M*g*h/(R*T)).

    The pressure of an isothermal atmosphere at altitude h, from the ``sea_level_pressure`` p0, the
    ``altitude`` h, the absolute ``temperature`` T, and the gas ``molar_mass`` M (defaulting to dry
    air): p = p0*exp(-M*g*h/(R*T)) = p0*exp(-h/H). The pressure decays exponentially, not linearly,
    because the compressible gas thins as it rises. Returns the pressure in Pa.
    """
    _check(sea_level_pressure, "[pressure]", "sea_level_pressure")
    _check(altitude, "[length]", "altitude")
    _check(temperature, "[temperature]", "temperature")
    p0 = sea_level_pressure.to("Pa").magnitude
    h = altitude.to("m").magnitude
    t = temperature.to("K").magnitude
    if p0 <= 0:
        raise ValueError("sea_level_pressure must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    m = _molar_mass_value(molar_mass)
    scale = _UNIVERSAL_GAS_CONSTANT * t / (m * _STANDARD_GRAVITY)
    return Quantity(magnitude=p0 * exp(-h / scale), unit="Pa")


def barometric_altitude(
    *,
    sea_level_pressure: Quantity,
    pressure: Quantity,
    temperature: Quantity,
    molar_mass: Quantity | None = None,
) -> Quantity:
    """The altitude for a measured pressure, h = H*ln(p0/p).

    The height an isothermal-atmosphere pressure ``pressure`` p corresponds to, from the
    ``sea_level_pressure`` p0, the absolute ``temperature`` T, and the gas ``molar_mass`` M
    (defaulting to dry air): h = (R*T/(M*g))*ln(p0/p) = H*ln(p0/p). This is the reading of a
    barometric altimeter. Requires p <= p0 (altitude at or above the reference). Returns the
    altitude in m.
    """
    _check(sea_level_pressure, "[pressure]", "sea_level_pressure")
    _check(pressure, "[pressure]", "pressure")
    _check(temperature, "[temperature]", "temperature")
    p0 = sea_level_pressure.to("Pa").magnitude
    p = pressure.to("Pa").magnitude
    t = temperature.to("K").magnitude
    if p0 <= 0 or p <= 0:
        raise ValueError("pressures must be positive")
    if p > p0:
        raise ValueError("pressure must not exceed sea_level_pressure (altitude at or above datum)")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    m = _molar_mass_value(molar_mass)
    scale = _UNIVERSAL_GAS_CONSTANT * t / (m * _STANDARD_GRAVITY)
    return Quantity(magnitude=scale * log(p0 / p), unit="m")


def lapse_rate_pressure(
    *,
    sea_level_pressure: Quantity,
    altitude: Quantity,
    sea_level_temperature: Quantity,
    lapse_rate: Quantity | None = None,
    molar_mass: Quantity | None = None,
) -> Quantity:
    """The standard-atmosphere pressure at altitude, p = p0*(1 - L*h/T0)^(g*M/(R*L)).

    The isothermal :func:`barometric_pressure` above assumes the column is all one temperature; the
    real troposphere cools with height at a lapse rate L of about 6.5 K/km, and that is the model
    the ISA tables, altimeter settings, and every aircraft performance chart are built on. Because
    the air aloft is colder — and so denser — than an isothermal column, the pressure falls as a
    *power law* rather than an exponential: p = p0*(1 - L*h/T0)^(g*M/(R*L)), from the
    ``sea_level_pressure`` p0, the ``altitude`` h, the absolute ``sea_level_temperature`` T0, the
    ``lapse_rate`` L (defaulting to the ISA 0.0065 K/m), and the gas ``molar_mass`` M (defaulting to
    dry air). The exponent is 5.2559 for the ISA constants. Valid through the troposphere, up to the
    ~11 km tropopause where the lapse rate goes to zero and the isothermal form takes over again;
    the altitude must stay below T0/L, where the model's temperature would reach absolute zero.
    Returns the pressure in Pa.
    """
    _check(sea_level_pressure, "[pressure]", "sea_level_pressure")
    _check(altitude, "[length]", "altitude")
    _check(sea_level_temperature, "[temperature]", "sea_level_temperature")
    p0 = sea_level_pressure.to("Pa").magnitude
    h = altitude.to("m").magnitude
    t0 = sea_level_temperature.to("K").magnitude
    if p0 <= 0:
        raise ValueError("sea_level_pressure must be positive")
    if t0 <= 0:
        raise ValueError("sea_level_temperature must be positive (absolute temperature)")
    if lapse_rate is None:
        rate = _ISA_LAPSE_RATE
    else:
        _check(lapse_rate, "[temperature]/[length]", "lapse_rate")
        rate = lapse_rate.to("K/m").magnitude
        if rate <= 0:
            raise ValueError("lapse_rate must be positive (temperature falling with height)")
    if h >= t0 / rate:
        raise ValueError(
            "altitude is at or above T0/L, where the lapse-rate model reaches absolute zero"
        )
    # Two limits are documented and only the weak one (T0/L ≈ 44.3 km) was enforced, so
    # the accepted range ran four times past the real one. The 11 km tropopause is not a
    # fuzzy seam — it is a defined constant of the standard atmosphere, above which the
    # temperature stops falling and the model's premise is simply false. Extrapolating is
    # optimistic in every case: 21% low at 20 km, 4.2x low at 30 km, 470x low at 40 km.
    # Only the ISA lapse rate is bounded here; a caller supplying their own rate is
    # describing their own layer and owns its extent.
    if lapse_rate is None and h > _ISA_TROPOPAUSE_ALTITUDE:
        raise ValueError(
            f"altitude {altitude} is above the {_ISA_TROPOPAUSE_ALTITUDE / 1000:.0f} km ISA "
            f"tropopause, where the temperature stops falling and this constant-lapse-rate "
            f"form no longer describes the atmosphere. Extrapolating understates the "
            f"pressure — 4.2x at 30 km. Use the isothermal stratosphere relation above the "
            f"tropopause, or pass an explicit lapse_rate for the layer you mean."
        )
    m = _molar_mass_value(molar_mass)
    exponent = _STANDARD_GRAVITY * m / (_UNIVERSAL_GAS_CONSTANT * rate)
    return Quantity(magnitude=p0 * (1.0 - rate * h / t0) ** exponent, unit="Pa")


def _molar_mass_value(molar_mass: Quantity | None) -> float:
    if molar_mass is None:
        return _MOLAR_MASS_AIR
    _check(molar_mass, "[mass]/[substance]", "molar_mass")
    m = molar_mass.to("kg/mol").magnitude
    if m <= 0:
        raise ValueError("molar_mass must be positive")
    return m


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
