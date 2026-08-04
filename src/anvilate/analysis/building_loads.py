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
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "wind_velocity_pressure",
    "wind_design_pressure",
    "seismic_response_coefficient",
    "seismic_base_shear",
]

_VELOCITY_PRESSURE_CONSTANT = 0.613  # = 1/2 * rho_air (1.225 kg/m^3), SI ASCE 7 form


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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
