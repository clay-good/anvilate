"""T1 analytical wind-turbine power checks (closed-form).

The power in the wind, and the fraction a turbine can take from it, complete the renewable trio with
:mod:`anvilate.analysis.solar_pv` and :mod:`anvilate.analysis.energy_storage`.

The kinetic power crossing a unit area of moving air is ½·ρ·V³ — it rises with the *cube* of wind
speed, so a site with 25% more wind holds nearly twice the power, which is why turbine siting lives
and dies on the wind resource.

A turbine cannot take all of it: slowing the air too much would dam the flow, so Betz's law caps the
extractable fraction at 16/27 ≈ 0.593 of the incident power. Real rotors reach a power coefficient
C_p of ~0.35–0.45. The power a rotor of swept area A = π·D²/4 delivers is then P = ½·ρ·A·V³·C_p,
with C_p the caller's value (bounded by the Betz limit).
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "BETZ_LIMIT",
    "wind_power_density",
    "wind_turbine_power",
]

BETZ_LIMIT = 16.0 / 27.0  # ≈ 0.593, the maximum fraction of wind power any turbine can extract


def wind_power_density(*, air_density: Quantity, wind_speed: Quantity) -> Quantity:
    """The kinetic power per unit area in the wind, P/A = ½·ρ·V³.

    The power crossing a unit area facing the wind, from the ``air_density`` ρ and the
    ``wind_speed`` V: P/A = ½·ρ·V³. Because it goes as the cube of speed, a turbine's output is far
    more sensitive to where it sits than to how big it is — doubling the wind speed lifts the power
    eightfold. Returns the power density in W/m².
    """
    _check(air_density, "[mass]/[length]**3", "air_density")
    _check(wind_speed, "[length]/[time]", "wind_speed")
    rho = air_density.to("kg/m**3").magnitude
    v = wind_speed.to("m/s").magnitude
    if rho <= 0:
        raise ValueError("air_density must be positive")
    if v < 0:
        raise ValueError("wind_speed must be non-negative")
    return Quantity(magnitude=0.5 * rho * v**3, unit="W/m**2")


def wind_turbine_power(
    *,
    air_density: Quantity,
    rotor_diameter: Quantity,
    wind_speed: Quantity,
    power_coefficient: float,
) -> Quantity:
    """The electrical power a wind turbine produces, P = ½·ρ·A·V³·C_p.

    The rotor of ``rotor_diameter`` D sweeps an area A = π·D²/4 and extracts a fraction
    ``power_coefficient`` C_p of the wind power crossing it: P = ½·ρ·A·V³·C_p, from the
    ``air_density`` ρ and the ``wind_speed`` V. C_p is the caller's from the turbine's curve and
    cannot exceed the Betz limit :data:`BETZ_LIMIT` (16/27) — the aerodynamic ceiling; real rotors
    reach ~0.35–0.45. Returns the power in watts.
    """
    _check(air_density, "[mass]/[length]**3", "air_density")
    _check(rotor_diameter, "[length]", "rotor_diameter")
    _check(wind_speed, "[length]/[time]", "wind_speed")
    rho = air_density.to("kg/m**3").magnitude
    d = rotor_diameter.to("m").magnitude
    v = wind_speed.to("m/s").magnitude
    if rho <= 0 or d <= 0:
        raise ValueError("air_density and rotor_diameter must be positive")
    if v < 0:
        raise ValueError("wind_speed must be non-negative")
    if not 0.0 < power_coefficient <= BETZ_LIMIT:
        raise ValueError(f"power_coefficient must be in (0, {BETZ_LIMIT:.4f}] (the Betz limit)")
    area = pi * d**2 / 4.0
    return Quantity(magnitude=0.5 * rho * area * v**3 * power_coefficient, unit="W")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
