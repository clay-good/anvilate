"""T1 analytical building code design loads (ASCE 7 wind and seismic, closed-form).

The rest of the library checks whether a member *resists* its load; this module supplies the
*load* itself from the two governing environmental hazards, following ASCE 7's closed forms. Every
site- and building-specific coefficient (exposure, topography, directionality, gust, pressure, and
seismic response factors) is a value the caller looks up in the standard's tables — this module does
the arithmetic that turns them into a pressure or a base shear, not the table lookups.

**Wind.** The velocity pressure is the wind's dynamic pressure with the air density folded into the
constant, qz = 0.613·Kz·Kzt·Kd·Ke·V² (SI, V in m/s → qz in Pa; the 0.613 is ½·ρ_air). The design
pressure on a surface is that velocity pressure scaled by the gust-effect factor and the surface's
pressure coefficient, p = qz·G·Cp.

**Seismic.** The equivalent lateral force method reduces the earthquake to a base shear V = Cs·W,
where the seismic weight W is resisted in proportion to the response coefficient Cs = SDS·Ie/R (the
design spectral acceleration, scaled up by importance and down by the system's ductility R). ASCE 7
also caps Cs above and below (by SD1/T and the 0.044·SDS·Ie floor) — those bounds need the building
period and are the caller's to apply; this is the base §12.8.1.1 value.

**Snow.** The flat-roof snow load is the ground snow discounted for the roof's exposure, warmth, and
occupancy, pf = 0.7·Ce·Ct·Is·pg, and a pitched roof sheds part of it through the slope factor,
ps = Cs·pf.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "wind_velocity_pressure",
    "wind_design_pressure",
    "seismic_response_coefficient",
    "seismic_base_shear",
    "flat_roof_snow_load",
    "sloped_roof_snow_load",
]

_VELOCITY_PRESSURE_CONSTANT = 0.613  # = 1/2 * rho_air (1.225 kg/m^3), SI ASCE 7 form
_FLAT_ROOF_SNOW_CONSTANT = 0.7  # ASCE 7 Eq 7.3-1 exposure/thermal baseline


def wind_velocity_pressure(
    *,
    basic_wind_speed: Quantity,
    exposure_coefficient: float,
    topographic_factor: float = 1.0,
    directionality_factor: float = 0.85,
    ground_elevation_factor: float = 1.0,
) -> Quantity:
    """The ASCE 7 velocity pressure qz = 0.613·Kz·Kzt·Kd·Ke·V² (SI).

    The wind's dynamic pressure at height, with the air density folded into the 0.613 constant
    (½·ρ_air). ``basic_wind_speed`` V is the 3-second gust design speed, ``exposure_coefficient`` Kz
    the velocity-pressure exposure coefficient (from the terrain category and height),
    ``topographic_factor`` Kzt the speed-up over hills and escarpments (1 on flat ground),
    ``directionality_factor`` Kd the wind-direction factor (0.85 for buildings), and
    ``ground_elevation_factor`` Ke the elevation adjustment (1 at sea level). All are ASCE 7 table
    values. Scale the result by the gust factor and pressure coefficient with
    :func:`wind_design_pressure`. Returns the velocity pressure in Pa.
    """
    _check(basic_wind_speed, "[length]/[time]", "basic_wind_speed")
    v = basic_wind_speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("basic_wind_speed must be positive")
    for name, value in (
        ("exposure_coefficient", exposure_coefficient),
        ("topographic_factor", topographic_factor),
        ("directionality_factor", directionality_factor),
        ("ground_elevation_factor", ground_elevation_factor),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    qz = (
        _VELOCITY_PRESSURE_CONSTANT
        * exposure_coefficient
        * topographic_factor
        * directionality_factor
        * ground_elevation_factor
        * v**2
    )
    return Quantity(magnitude=qz, unit="Pa")


def wind_design_pressure(
    *,
    velocity_pressure: Quantity,
    gust_effect_factor: float,
    pressure_coefficient: float,
) -> Quantity:
    """The ASCE 7 design wind pressure on a surface, p = qz·G·Cp.

    The net pressure a surface actually feels: the ``velocity_pressure`` qz (from
    :func:`wind_velocity_pressure`) scaled by the ``gust_effect_factor`` G (0.85 for a rigid
    building) and the ``pressure_coefficient`` Cp for that surface (positive for a windward wall
    pushed in, negative for a leeward wall or roof sucked out — an ASCE 7 table value that carries
    its own sign). A negative result is a net suction. Returns the design pressure in Pa.
    """
    _check(velocity_pressure, "[pressure]", "velocity_pressure")
    qz = velocity_pressure.to("Pa").magnitude
    if qz <= 0:
        raise ValueError("velocity_pressure must be positive")
    if gust_effect_factor <= 0:
        raise ValueError(f"gust_effect_factor must be positive; got {gust_effect_factor}")
    return Quantity(magnitude=qz * gust_effect_factor * pressure_coefficient, unit="Pa")


def seismic_response_coefficient(
    *,
    design_spectral_acceleration: float,
    response_modification_factor: float,
    importance_factor: float = 1.0,
) -> float:
    """The ASCE 7 seismic response coefficient Cs = SDS·Ie/R (§12.8.1.1).

    The fraction of a structure's weight taken as an equivalent static earthquake force.
    ``design_spectral_acceleration`` SDS is the short-period design spectral acceleration (in g),
    ``response_modification_factor`` R the seismic system's ductility/overstrength factor (larger
    for a more ductile system, which is allowed to yield and so is designed for less force), and
    ``importance_factor`` Ie the occupancy importance factor. This is the base value; ASCE 7 caps it
    above (by SD1/(T·R/Ie)) and below (the 0.044·SDS·Ie floor), which need the building period and
    are the caller's to apply. Returns the dimensionless Cs.
    """
    if design_spectral_acceleration <= 0:
        raise ValueError("design_spectral_acceleration must be positive")
    if response_modification_factor <= 0:
        raise ValueError("response_modification_factor must be positive")
    if importance_factor <= 0:
        raise ValueError("importance_factor must be positive")
    return design_spectral_acceleration * importance_factor / response_modification_factor


def seismic_base_shear(
    *,
    seismic_weight: Quantity,
    response_coefficient: float,
) -> Quantity:
    """The ASCE 7 seismic base shear V = Cs·W (§12.8.1).

    The total equivalent lateral earthquake force at the base of a structure: its effective
    ``seismic_weight`` W (dead load plus the code's fraction of other loads) times the
    ``response_coefficient`` Cs from :func:`seismic_response_coefficient`. This shear is then
    distributed up the height to each level. Returns the base shear in kN.
    """
    _check(seismic_weight, "[force]", "seismic_weight")
    w = seismic_weight.to("kN").magnitude
    if w <= 0:
        raise ValueError("seismic_weight must be positive")
    if response_coefficient <= 0:
        raise ValueError(f"response_coefficient must be positive; got {response_coefficient}")
    return Quantity(magnitude=w * response_coefficient, unit="kN")


def flat_roof_snow_load(
    *,
    ground_snow_load: Quantity,
    exposure_factor: float = 1.0,
    thermal_factor: float = 1.0,
    importance_factor: float = 1.0,
) -> Quantity:
    """The ASCE 7 flat-roof snow load pf = 0.7·Ce·Ct·Is·pg (§7.3).

    The design snow on a flat (or nearly flat) roof: the site's ``ground_snow_load`` pg discounted
    by the 0.7 baseline and three table factors — ``exposure_factor`` Ce (wind exposure, <1 for a
    windswept roof that blows clear, >1 for a sheltered one), ``thermal_factor`` Ct (roof warmth, <1
    for a heated building whose roof melts snow, >1 for a cold/freezer roof), and
    ``importance_factor`` Is (occupancy). All three are ASCE 7 table values. Reduce it for a pitched
    roof with :func:`sloped_roof_snow_load`. Returns the flat-roof snow load in kPa.
    """
    _check(ground_snow_load, "[pressure]", "ground_snow_load")
    pg = ground_snow_load.to("kPa").magnitude
    if pg <= 0:
        raise ValueError("ground_snow_load must be positive")
    for name, value in (
        ("exposure_factor", exposure_factor),
        ("thermal_factor", thermal_factor),
        ("importance_factor", importance_factor),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    pf = _FLAT_ROOF_SNOW_CONSTANT * exposure_factor * thermal_factor * importance_factor * pg
    return Quantity(magnitude=pf, unit="kPa")


def sloped_roof_snow_load(
    *,
    flat_roof_snow_load: Quantity,
    slope_factor: float,
) -> Quantity:
    """The ASCE 7 sloped-roof snow load ps = Cs·pf (§7.4).

    A pitched roof holds less snow than a flat one, because some slides off: the
    ``flat_roof_snow_load`` pf (from :func:`flat_roof_snow_load`) scaled by the ``slope_factor`` Cs,
    which falls from 1 toward 0 as the roof steepens and its surface grows more slippery (an ASCE 7
    value from the pitch and the roof's slipperiness). Returns the sloped-roof snow load in kPa.
    """
    _check(flat_roof_snow_load, "[pressure]", "flat_roof_snow_load")
    pf = flat_roof_snow_load.to("kPa").magnitude
    if pf <= 0:
        raise ValueError("flat_roof_snow_load must be positive")
    if not 0 <= slope_factor <= 1:
        raise ValueError(f"slope_factor must lie in [0, 1]; got {slope_factor}")
    return Quantity(magnitude=slope_factor * pf, unit="kPa")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
