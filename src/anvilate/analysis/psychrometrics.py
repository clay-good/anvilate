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

from math import atan, exp, log, sqrt

from ..units import Quantity

__all__ = [
    "wet_bulb_temperature",
    "adiabatic_mixing_temperature",
    "adiabatic_mixing_humidity_ratio",
    "coil_bypass_factor",
    "cooling_coil_load",
    "evaporative_cooler_effectiveness",
    "dew_point_temperature",
    "humidity_ratio",
    "latent_heat_load",
    "moist_air_enthalpy",
    "moist_air_specific_volume",
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
# Specific gas constant of dry air, R/M_air (J per kg per K).
_R_DRY_AIR = 287.042


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


def moist_air_specific_volume(
    *,
    temperature: Quantity,
    pressure: Quantity,
    humidity_ratio: float,
) -> Quantity:
    """The specific volume of moist air, v = R_da·T·(1 + 1.608·W)/p (m³ per kg dry air).

    The bridge between the volumetric flow an air system is actually specified in (CFM, m³/s) and
    the *dry-air mass flow* every load in this module wants: v = R_da·T·(1 + W/0.622)/p, with
    R_da = 287.042 J/(kg·K), ``temperature`` T absolute, ``pressure`` p barometric, and
    ``humidity_ratio`` W in kg water per kg dry air (from :func:`humidity_ratio`). It is the
    ideal-gas volume of a kg of dry air plus the vapor riding along with it, so the moisture term
    makes humid air *less* dense, not more. Divide a volumetric flow by v to get the ṁ that
    :func:`sensible_heat_load`, :func:`latent_heat_load`, and :func:`cooling_coil_load` need — and
    note that v rises with temperature, which is why a fan rated in CFM moves less mass on a hot
    day. Returns the specific volume in m³ per kg of dry air.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(pressure, "[pressure]", "pressure")
    t = temperature.to("K").magnitude
    p = pressure.to("Pa").magnitude
    if t <= 0:
        raise ValueError("temperature must be above absolute zero")
    if p <= 0:
        raise ValueError("pressure must be positive")
    if humidity_ratio < 0:
        raise ValueError("humidity_ratio must be non-negative")
    return Quantity(
        magnitude=_R_DRY_AIR * t * (1.0 + humidity_ratio / _MASS_RATIO) / p, unit="m^3/kg"
    )


def adiabatic_mixing_temperature(
    *,
    mass_flow_1: Quantity,
    temperature_1: Quantity,
    mass_flow_2: Quantity,
    temperature_2: Quantity,
) -> Quantity:
    """The temperature of two mixed air streams, T = (ṁ₁·T₁ + ṁ₂·T₂)/(ṁ₁ + ṁ₂).

    When two air streams merge with no heat added — the return and outdoor air joining in an
    air-handler's mixing box — the mixed temperature is the mass-weighted average of the two:
    T = (``mass_flow_1``·``temperature_1`` + ``mass_flow_2``·``temperature_2``)/(ṁ₁ + ṁ₂). The mixed
    point lands on the straight line between the two on a psychrometric chart, nearer the larger
    stream. Pair it with :func:`adiabatic_mixing_humidity_ratio` for the full mixed state. Returns
    the mixed dry-bulb temperature in °C.
    """
    _check(mass_flow_1, "[mass]/[time]", "mass_flow_1")
    _check(mass_flow_2, "[mass]/[time]", "mass_flow_2")
    _check(temperature_1, "[temperature]", "temperature_1")
    _check(temperature_2, "[temperature]", "temperature_2")
    m1 = mass_flow_1.to("kg/s").magnitude
    m2 = mass_flow_2.to("kg/s").magnitude
    t1 = temperature_1.to("degC").magnitude
    t2 = temperature_2.to("degC").magnitude
    if m1 <= 0 or m2 <= 0:
        raise ValueError("mass flows must be positive")
    return Quantity(magnitude=(m1 * t1 + m2 * t2) / (m1 + m2), unit="degC")


def adiabatic_mixing_humidity_ratio(
    *,
    mass_flow_1: Quantity,
    humidity_ratio_1: float,
    mass_flow_2: Quantity,
    humidity_ratio_2: float,
) -> float:
    """The humidity ratio of two mixed air streams, W = (ṁ₁·W₁ + ṁ₂·W₂)/(ṁ₁ + ṁ₂).

    The moisture of the merged stream is the mass-weighted average of the two humidity ratios:
    W = (``mass_flow_1``·``humidity_ratio_1`` + ``mass_flow_2``·``humidity_ratio_2``)/(ṁ₁ + ṁ₂).
    ``humidity_ratio_1``/``humidity_ratio_2`` are in kg water per kg dry air (from
    :func:`humidity_ratio`). This is the companion of :func:`adiabatic_mixing_temperature`; together
    they fix the mixed air condition an air-handler's coil then has to treat. Returns the
    dimensionless mixed humidity ratio (kg/kg).
    """
    _check(mass_flow_1, "[mass]/[time]", "mass_flow_1")
    _check(mass_flow_2, "[mass]/[time]", "mass_flow_2")
    m1 = mass_flow_1.to("kg/s").magnitude
    m2 = mass_flow_2.to("kg/s").magnitude
    if m1 <= 0 or m2 <= 0:
        raise ValueError("mass flows must be positive")
    if humidity_ratio_1 < 0 or humidity_ratio_2 < 0:
        raise ValueError("humidity ratios must be non-negative")
    return (m1 * humidity_ratio_1 + m2 * humidity_ratio_2) / (m1 + m2)


def evaporative_cooler_effectiveness(
    *,
    entering_dry_bulb: Quantity,
    leaving_dry_bulb: Quantity,
    entering_wet_bulb: Quantity,
) -> float:
    """The direct evaporative cooler saturation effectiveness ε = (t_db1 − t_db2)/(t_db1 − t_wb1).

    A direct (adiabatic) evaporative cooler drops the air's dry-bulb temperature by evaporating
    water into it, and the coldest it could reach is the entering wet-bulb temperature — the
    thermodynamic limit where the air is saturated. The saturation effectiveness measures how close
    it gets: ε = (``entering_dry_bulb`` − ``leaving_dry_bulb``)/(``entering_dry_bulb`` −
    ``entering_wet_bulb``). A good rigid-media (swamp) cooler reaches 0.8–0.9; a spray or slinger
    less. The bigger the wet-bulb depression (hot, dry air), the more cooling that effectiveness
    delivers, which is why evaporative cooling suits arid climates and fails in humid ones. The
    leaving dry-bulb must lie between the entering wet-bulb and the entering dry-bulb. Returns the
    dimensionless effectiveness.
    """
    _check(entering_dry_bulb, "[temperature]", "entering_dry_bulb")
    _check(leaving_dry_bulb, "[temperature]", "leaving_dry_bulb")
    _check(entering_wet_bulb, "[temperature]", "entering_wet_bulb")
    t_db1 = entering_dry_bulb.to("degC").magnitude
    t_db2 = leaving_dry_bulb.to("degC").magnitude
    t_wb1 = entering_wet_bulb.to("degC").magnitude
    if not t_wb1 <= t_db2 <= t_db1:
        raise ValueError(
            "temperatures must satisfy entering_wet_bulb <= leaving_dry_bulb <= entering_dry_bulb"
        )
    if t_db1 == t_wb1:
        raise ValueError("entering air is already saturated (no wet-bulb depression to work with)")
    return (t_db1 - t_db2) / (t_db1 - t_wb1)


def coil_bypass_factor(
    *,
    entering_temperature: Quantity,
    leaving_temperature: Quantity,
    apparent_dew_point: Quantity,
) -> float:
    """The cooling-coil bypass factor BF = (t_leave − t_ADP)/(t_enter − t_ADP).

    A cooling coil does not bring all the air to its fin temperature — some slips through untouched,
    as if it bypassed the coil entirely. The bypass factor is that fraction, measured on the
    temperature approach to the coil's apparent dew point (the effective fin-surface condition):
    BF = (``leaving_temperature`` − ``apparent_dew_point``)/(``entering_temperature`` −
    ``apparent_dew_point``). A tight, many-row coil has a low BF (0.05–0.15, most air contacts the
    fins); a shallow, high-velocity coil bypasses more. The contact factor 1 − BF is its complement.
    The leaving temperature must lie between the apparent dew point and the entering temperature.
    Returns the dimensionless bypass factor.
    """
    _check(entering_temperature, "[temperature]", "entering_temperature")
    _check(leaving_temperature, "[temperature]", "leaving_temperature")
    _check(apparent_dew_point, "[temperature]", "apparent_dew_point")
    t_in = entering_temperature.to("degC").magnitude
    t_out = leaving_temperature.to("degC").magnitude
    t_adp = apparent_dew_point.to("degC").magnitude
    if not t_adp < t_out < t_in:
        raise ValueError("temperatures must satisfy apparent_dew_point < leaving < entering")
    return (t_out - t_adp) / (t_in - t_adp)


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


def wet_bulb_temperature(*, dry_bulb_temperature: Quantity, relative_humidity: float) -> Quantity:
    """The wet-bulb temperature (Stull 2011 explicit fit).

    The temperature a wetted thermometer settles at in a moving airstream — the lowest temperature
    evaporation alone can reach, and the reference every evaporative process is measured against.
    :func:`evaporative_cooler_effectiveness` consumes an entering wet bulb and the module had no
    way to produce one.

    There is no closed form from first principles: the psychrometric relation is implicit in T_wb,
    so this is Stull's empirical inversion, in degrees Celsius with the ``relative_humidity`` φ
    expressed as a percentage RH = 100·φ:

        T_wb = T·atan(0.151977·√(RH + 8.313659)) + atan(T + RH) − atan(RH − 1.676331)
               + 0.00391838·RH^1.5·atan(0.023101·RH) − 4.686035

    The wet-bulb *depression* is the whole story of evaporative cooling. Air at 30 °C and 50% RH
    has a wet bulb of 22.3 °C, so a perfect evaporative cooler could shed 7.7 K; the same air at
    90% RH could shed barely 1.4 K. That is why swamp coolers work in Phoenix and not in Houston,
    and it is invisible from the dry-bulb temperature alone.

    The fit is good to about 0.3 K over most of the range that matters for building HVAC — dry
    bulb between −20 and 50 °C at relative humidities above roughly 5% — but Stull's paper
    excludes one corner of that box: cold air that is also dry. Below about −10 °C at low humidity
    the fit overshoots, and by −20 °C at 5% RH it returns a wet bulb 2.4 K *above* the dry bulb,
    which is thermodynamically impossible. Rather than hand that back, the function checks its own
    answer against the physical bound T_wb ≤ T_db and raises when the correlation has left its
    range — a screening number that is known-wrong is worse than no number.

    At saturation the wet bulb equals the dry bulb, which the fit reproduces to within its own
    error band rather than exactly (it can read a few hundredths of a kelvin high), so do not use
    it as an equality test; the bound check tolerates that much overshoot.
    ``dry_bulb_temperature`` is an absolute Quantity and ``relative_humidity`` a plain fraction in
    (0, 1]. Returns the wet-bulb temperature in K.
    """
    _check(dry_bulb_temperature, "[temperature]", "dry_bulb_temperature")
    if not 0.0 < relative_humidity <= 1.0:
        raise ValueError(f"relative_humidity must be a fraction in (0, 1]; got {relative_humidity}")
    t_c = dry_bulb_temperature.to("K").magnitude - 273.15
    rh = 100.0 * relative_humidity
    t_wb = (
        t_c * atan(0.151977 * sqrt(rh + 8.313659))
        + atan(t_c + rh)
        - atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * atan(0.023101 * rh)
        - 4.686035
    )
    # The fit's own sanity check: evaporation cannot drive a thermometer above the dry bulb, so a
    # wet bulb over it means Stull's correlation has left its range (the cold, dry corner his
    # paper excludes). The 0.25 K allowance covers the documented overshoot near saturation.
    # The overshoot the allowance exists for happens only as the air approaches saturation, so
    # the allowance is granted only there. Applying a flat 0.25 K everywhere would wave through
    # most of the cold-dry band this check is meant to catch: -20 degC at 13% RH overshoots by
    # 0.22 K, under a flat allowance but still impossible.
    allowance = 0.25 if relative_humidity > 0.95 else 0.0
    if t_wb > t_c + allowance:
        raise ValueError(
            f"the Stull wet-bulb fit is out of range at {t_c:.1f} degC and "
            f"{100.0 * relative_humidity:.0f}% RH: it returns a wet bulb of {t_wb:.2f} degC, above "
            f"the dry bulb, which evaporation cannot reach. The fit is not valid for air that is "
            f"both cold and dry; use a psychrometric chart or table there."
        )
    return Quantity(magnitude=t_wb + 273.15, unit="K")
