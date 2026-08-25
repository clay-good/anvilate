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

Sources: Duffie & Beckman, *Solar Engineering of Thermal Processes*, Chapter 1 (available solar
radiation) — Cooper's declination equation, the sunset hour angle from latitude and declination,
the day-length relation N = (2/15)·ω_s, and the general solar-altitude relation are given there,
along with the plane-parallel air mass AM = 1/sin α and the limits of that approximation near
the horizon.
"""

from __future__ import annotations

from math import acos, asin, cos, degrees, radians, sin, tan

from ..units import Quantity

__all__ = [
    "solar_altitude_angle",
    "air_mass",
    "daylight_hours",
    "solar_altitude_at_noon",
    "solar_declination",
    "sunset_hour_angle",
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


def sunset_hour_angle(*, latitude: float, declination: float) -> Quantity:
    """The sunset hour angle, ω_s = arccos(−tan φ · tan δ).

    How far the sun travels from solar noon to the horizon, expressed as an angle the earth turns
    through (15° per hour). From the site ``latitude`` φ and the solar ``declination`` δ, both plain
    floats in degrees: ω_s = arccos(−tan φ · tan δ). It is exactly 90° at every equinox and at the
    equator all year — the six-hour afternoon that makes every day twelve hours long there — and
    swings either side of that as the declination moves into or away from the site's hemisphere.
    Together with :func:`solar_altitude_at_noon` (how HIGH the sun gets) it fixes the other half of
    the resource: how LONG it is up, which :func:`daylight_hours` converts to time. Raises inside
    the polar circles when the sun does not rise or set at all (|tan φ · tan δ| > 1). Returns the
    sunset hour angle in degrees.
    """
    if not -90.0 <= latitude <= 90.0:
        raise ValueError(f"latitude must be in -90..90 degrees; got {latitude}")
    if not -23.45 <= declination <= 23.45:
        raise ValueError(f"declination must be in -23.45..23.45 degrees; got {declination}")
    cosine = -tan(radians(latitude)) * tan(radians(declination))
    if not -1.0 <= cosine <= 1.0:
        raise ValueError(
            f"the sun neither rises nor sets at latitude {latitude}° with declination "
            f"{declination}° (polar day or polar night), so there is no sunset hour angle"
        )
    return Quantity(magnitude=degrees(acos(cosine)), unit="degree")


def daylight_hours(*, latitude: float, declination: float) -> Quantity:
    """The length of the day, N = (2/15)·ω_s.

    The hours between sunrise and sunset at the site ``latitude`` φ on a day of solar
    ``declination`` δ (both plain floats in degrees). The earth turns 15° per hour, and the sun is
    up for twice the sunset hour angle of :func:`sunset_hour_angle`, so N = 2·ω_s/15. This is the
    number a daily energy yield is built on — the irradiance model says how strong the sun is, this
    says for how long — and it is why a summer day at 51°N is worth roughly 16 collector-hours
    against 8 in midwinter. It is exactly 12 h at the equinoxes everywhere, and 12 h all year on
    the equator. Purely geometric: it takes the sun as a point and ignores atmospheric refraction
    and the solar disc, which together add a few minutes to a real sunrise-to-sunset day. Raises
    inside the polar circles, where the sun does not rise or set. Returns the day length in hours.
    """
    omega = sunset_hour_angle(latitude=latitude, declination=declination)
    return Quantity(magnitude=2.0 * omega.to("degree").magnitude / 15.0, unit="hour")


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


def solar_altitude_angle(*, latitude: float, declination: float, hour_angle: float) -> Quantity:
    """The solar altitude at any hour, sin α = sin φ·sin δ + cos φ·cos δ·cos ω.

    How high the sun stands above the horizon at a given moment, from the ``latitude`` φ, the solar
    ``declination`` δ (:func:`solar_declination`), and the ``hour_angle`` ω — all in degrees, with
    ω measured from solar noon at 15° per hour, negative in the morning and positive in the
    afternoon.

    The module computed altitude only at solar noon, yet :func:`air_mass` takes an arbitrary
    altitude, so there was no way to reach it at any other hour. That gap matters because the
    atmospheric path length is strongly nonlinear in altitude: at 40°N with δ = 20°, the sun is
    70° up at noon (air mass 1.06) but 46.8° up at 3 pm (air mass 1.37), a 29% longer path. An
    hourly yield model that silently reuses the noon air mass over-predicts morning and afternoon
    irradiance, which is where a fixed collector spends most of its day.

    At ω = 0 this reduces exactly to :func:`solar_altitude_at_noon`, and at the sunset hour angle
    (:func:`sunset_hour_angle`) it returns zero by construction. A negative result means the sun is
    below the horizon — night, not an error — so it is returned rather than raised on. This is the
    geometric altitude, before atmospheric refraction, which lifts the apparent sun by about half a
    degree near the horizon. Returns the altitude in degrees.
    """
    if not -90.0 <= latitude <= 90.0:
        raise ValueError(f"latitude (degrees) must lie in [-90, 90]; got {latitude}")
    if not -90.0 <= declination <= 90.0:
        raise ValueError(f"declination (degrees) must lie in [-90, 90]; got {declination}")
    if not -180.0 <= hour_angle <= 180.0:
        raise ValueError(f"hour_angle (degrees) must lie in [-180, 180]; got {hour_angle}")
    phi = radians(latitude)
    delta = radians(declination)
    omega = radians(hour_angle)
    sin_altitude = sin(phi) * sin(delta) + cos(phi) * cos(delta) * cos(omega)
    return Quantity(magnitude=degrees(asin(max(-1.0, min(1.0, sin_altitude)))), unit="degree")
