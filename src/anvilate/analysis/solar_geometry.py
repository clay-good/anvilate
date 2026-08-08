"""T1 analytical solar-position geometry checks (closed-form).

Sizing a solar collector or PV array starts with where the sun is: how high it climbs, and how much
atmosphere its light must cross to reach the panel. Both follow from the date and the site latitude
by simple astronomy, and they set the resource that the electrical model of
:mod:`anvilate.analysis.solar_pv` and the thermal model of
:mod:`anvilate.analysis.solar_thermal` then convert into power.

The sun's declination — its angle north or south of the equator — swings sinusoidally through the
year, δ = 23.45°·sin(360·(284 + n)/365) for day-of-year n (Cooper's equation), reaching ±23.45° at
the solstices and zero at the equinoxes. At solar noon the sun's altitude above the horizon is
α = 90° − |φ − δ|, from the site latitude φ, so a panel tilt near |φ − δ| faces it squarely. The
light then crosses an air mass AM = 1/sin(α) relative to a straight-down path — the AM1.5 standard
(α ≈ 41.8°) that solar panels are rated against. Angles are taken as **plain floats in degrees**;
computed angles are returned as dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import radians, sin

from ..units import Quantity

__all__ = [
    "air_mass",
    "solar_altitude_at_noon",
    "solar_declination",
]


def solar_declination(*, day_of_year: int) -> Quantity:
    """The solar declination, δ = 23.45°·sin(360·(284 + n)/365) (Cooper's equation).

    The angle of the sun north (+) or south (−) of the celestial equator on ``day_of_year`` n
    (1 = January 1): δ = 23.45°·sin(360·(284 + n)/365). It reaches +23.45° at the June solstice,
    −23.45° in December, and zero at the equinoxes. Returns the declination in degrees.
    """
    if not 1 <= day_of_year <= 366:
        raise ValueError(f"day_of_year must be in 1..366; got {day_of_year}")
    delta = 23.45 * sin(radians(360.0 * (284 + day_of_year) / 365.0))
    return Quantity(magnitude=delta, unit="degree")


def solar_altitude_at_noon(*, latitude: float, declination: float) -> Quantity:
    """The solar altitude at solar noon, α = 90° − |φ − δ|.

    How high the sun stands above the horizon at solar noon, from the site ``latitude`` φ and the
    solar ``declination`` δ (both plain floats in degrees): α = 90° − |φ − δ|. It peaks in summer,
    when δ moves toward the site's hemisphere, and a fixed panel tilted near |φ − δ| meets the noon
    sun head-on. Returns the altitude in degrees.
    """
    if not -90.0 <= latitude <= 90.0:
        raise ValueError(f"latitude must be in -90..90 degrees; got {latitude}")
    if not -23.45 <= declination <= 23.45:
        raise ValueError(f"declination must be in -23.45..23.45 degrees; got {declination}")
    alpha = 90.0 - abs(latitude - declination)
    return Quantity(magnitude=alpha, unit="degree")


def air_mass(*, solar_altitude: float) -> float:
    """The atmospheric air mass, AM = 1/sin(α).

    The length of the atmospheric path sunlight crosses relative to a straight-down (zenith) path,
    from the ``solar_altitude`` α (a plain float in degrees above the horizon): AM = 1/sin(α). It is
    1.0 with the sun overhead and 1.5 at α ≈ 41.8° — the AM1.5 spectrum solar cells are rated to.
    A low sun means a long path and a redder, weaker beam. Returns the air mass as a plain float.
    """
    if not 0.0 < solar_altitude <= 90.0:
        raise ValueError(f"solar_altitude must be in (0, 90] degrees; got {solar_altitude}")
    return 1.0 / sin(radians(solar_altitude))
