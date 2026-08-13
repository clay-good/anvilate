"""T1 analytical lighting-design checks (illuminance, closed-form).

Facility and electrical engineers size lighting to a target illuminance — the lux (or foot-candle)
on a work plane that a task needs — and two relations carry the design.

A single luminaire treated as a point source obeys the inverse-square cosine law,
E = I·cos(θ)/d²: the illuminance on a surface falls with the square of the distance d from the
source and with the cosine of the incidence angle θ (measured from the surface normal), because a
tilted surface catches the beam more obliquely. ``luminous_intensity`` I is in candela; the result
is in lux.

A whole room is laid out by the lumen method, E = n·Φ·CU·LLF/A: the average maintained illuminance
over a floor of area A from n luminaires each emitting Φ lumens, discounted by the coefficient of
utilization CU (the fraction of emitted light that reaches the work plane, from room geometry and
surface reflectances) and the light loss factor LLF (dirt, lamp aging). CU and LLF are supplied
design coefficients — like an allowable, retrieved from photometric tables, not invented here. The
inverse sizes the installation: how many luminaires a target illuminance needs.

Angles are plain floats in radians (the units layer does not carry dimensionless angles), matching
the convention elsewhere in the analysis package.
"""

from __future__ import annotations

from math import cos, pi

from ..units import Quantity

__all__ = [
    "diffuse_surface_luminance",
    "illuminance_for_target_luminance",
    "lighting_power_density",
    "lumen_method_illuminance",
    "lumen_method_luminaire_count",
    "point_source_illuminance",
    "room_cavity_ratio",
]


def room_cavity_ratio(
    *,
    cavity_height: Quantity,
    room_length: Quantity,
    room_width: Quantity,
) -> float:
    """The room cavity ratio RCR = 5·h·(L + W)/(L·W) that sets the coefficient of utilization.

    The lumen method's coefficient of utilization (the CU fed to :func:`lumen_method_illuminance`)
    is read from a photometric table against the room's cavity ratio — a single number capturing how
    tall and narrow the room is between the luminaires and the work plane. RCR = 5·h·(L + W)/(L·W)
    from the ``cavity_height`` h (luminaires down to the work plane), the ``room_length`` L, and the
    ``room_width`` W. A low, wide room has a small RCR and a high CU (light reaches the plane before
    the walls absorb it); a tall, narrow room has a large RCR and a low CU. Returns the
    dimensionless RCR.
    """
    _check(cavity_height, "[length]", "cavity_height")
    _check(room_length, "[length]", "room_length")
    _check(room_width, "[length]", "room_width")
    h = cavity_height.to("m").magnitude
    length = room_length.to("m").magnitude
    width = room_width.to("m").magnitude
    if h <= 0 or length <= 0 or width <= 0:
        raise ValueError("cavity_height, room_length, and room_width must be positive")
    return 5.0 * h * (length + width) / (length * width)


def point_source_illuminance(
    *,
    luminous_intensity: Quantity,
    distance: Quantity,
    incidence_angle: float = 0.0,
) -> Quantity:
    """The illuminance from a point source by the inverse-square cosine law, E = I·cos(θ)/d².

    A luminaire small against its distance acts as a point source: the illuminance it lays on a
    surface is E = I·cos(θ)/d², from its ``luminous_intensity`` I (candela), the ``distance`` d to
    the surface, and the ``incidence_angle`` θ in radians between the light's direction and the
    surface normal (0 for light hitting the surface head-on). Doubling the distance quarters the
    illuminance, and a steeply tilted surface (θ near π/2) catches almost nothing. Returns the
    illuminance as a Quantity in lux.
    """
    _check(luminous_intensity, "[luminosity]", "luminous_intensity")
    _check(distance, "[length]", "distance")
    d = distance.to("m").magnitude
    if d <= 0:
        raise ValueError("distance must be positive")
    if not -1.5707963267948966 <= incidence_angle <= 1.5707963267948966:
        raise ValueError("incidence_angle (radians) must be within ±π/2 of the surface normal")
    intensity = luminous_intensity.to("cd").magnitude
    e = intensity * cos(incidence_angle) / d**2
    return Quantity(magnitude=e, unit="lux")


def diffuse_surface_luminance(*, illuminance: Quantity, reflectance: float) -> Quantity:
    """The luminance of a diffuse (Lambertian) surface, L = ρ·E/π.

    Illuminance is the light falling *on* a surface; luminance is the brightness the eye actually
    sees coming *off* it — and for a matte, perfectly diffusing surface the two relate by
    L = ρ·E/π, from the ``illuminance`` E landing on it and its ``reflectance`` ρ (0 to 1). The π
    converts the reflected flux (ρ·E per unit area) into the per-steradian luminance of a Lambertian
    emitter. It is what turns a lighting-design illuminance target into the wall or desktop
    brightness a person perceives, and the input to glare and contrast checks. ``reflectance`` must
    be in (0, 1]. Returns the luminance as a Quantity in cd/m².
    """
    _check(illuminance, "[luminosity]/[area]", "illuminance")
    _check_coefficient(reflectance, "reflectance")
    e = illuminance.to("lux").magnitude
    if e < 0:
        raise ValueError("illuminance must be non-negative")
    return Quantity(magnitude=reflectance * e / pi, unit="cd/m**2")


def illuminance_for_target_luminance(*, target_luminance: Quantity, reflectance: float) -> Quantity:
    """The illuminance a target surface brightness requires, E = π·L/ρ.

    The design inverse of :func:`diffuse_surface_luminance`: to make a matte surface of
    ``reflectance`` ρ appear at a ``target_luminance`` L (its perceived brightness), the light
    landing on it must reach E = π·L/ρ. A darker surface (low ρ) needs proportionally more
    illuminance to read as bright, which is why dark finishes drive up the lighting load.
    ``target_luminance`` is a cd/m² quantity and ``reflectance`` must be in (0, 1]. Returns the
    required illuminance as a Quantity in lux.
    """
    _check(target_luminance, "[luminosity]/[area]", "target_luminance")
    if not 0.0 < reflectance <= 1.0:
        raise ValueError(f"reflectance must be in (0, 1]; got {reflectance}")
    lum = target_luminance.to("cd/m**2").magnitude
    if lum < 0:
        raise ValueError("target_luminance must be non-negative")
    return Quantity(magnitude=pi * lum / reflectance, unit="lux")


def lumen_method_illuminance(
    *,
    luminaire_count: int,
    lumens_per_luminaire: Quantity,
    coefficient_of_utilization: float,
    light_loss_factor: float,
    area: Quantity,
) -> Quantity:
    """The average maintained illuminance of a room by the lumen method, E = n·Φ·CU·LLF/A.

    The workhorse of interior lighting layout: the average illuminance a work plane sees is
    E = n·Φ·CU·LLF/A, from the ``luminaire_count`` n, the ``lumens_per_luminaire`` Φ, the
    ``coefficient_of_utilization`` CU (fraction of emitted lumens reaching the plane — room geometry
    and reflectances), the ``light_loss_factor`` LLF (maintenance depreciation from dirt and aging),
    and the floor ``area`` A. CU and LLF are supplied photometric coefficients, dimensionless and in
    (0, 1]. Returns the maintained illuminance as a Quantity in lux.
    """
    _check(lumens_per_luminaire, "[luminosity]", "lumens_per_luminaire")
    _check(area, "[length]**2", "area")
    if luminaire_count <= 0:
        raise ValueError("luminaire_count must be positive")
    _check_coefficient(coefficient_of_utilization, "coefficient_of_utilization")
    _check_coefficient(light_loss_factor, "light_loss_factor")
    a = area.to("m**2").magnitude
    if a <= 0:
        raise ValueError("area must be positive")
    phi = lumens_per_luminaire.to("lumen").magnitude
    e = luminaire_count * phi * coefficient_of_utilization * light_loss_factor / a
    return Quantity(magnitude=e, unit="lux")


def lumen_method_luminaire_count(
    *,
    target_illuminance: Quantity,
    area: Quantity,
    lumens_per_luminaire: Quantity,
    coefficient_of_utilization: float,
    light_loss_factor: float,
) -> float:
    """The luminaires a target illuminance needs, n = E·A/(Φ·CU·LLF) — the lumen-method inverse.

    Turns the lumen method around to size an installation: the number of luminaires to hold a
    ``target_illuminance`` E over a floor ``area`` A is n = E·A/(Φ·CU·LLF), each luminaire
    emitting ``lumens_per_luminaire`` Φ, discounted by the ``coefficient_of_utilization`` CU and
    ``light_loss_factor`` LLF. Returns the exact (unrounded) count — a designer rounds up to the
    next whole luminaire, and up again to a layout that tiles the room, so the installed level
    clears the target with margin.
    """
    _check(target_illuminance, "[luminosity]/[length]**2", "target_illuminance")
    _check(area, "[length]**2", "area")
    _check(lumens_per_luminaire, "[luminosity]", "lumens_per_luminaire")
    _check_coefficient(coefficient_of_utilization, "coefficient_of_utilization")
    _check_coefficient(light_loss_factor, "light_loss_factor")
    e = target_illuminance.to("lux").magnitude
    a = area.to("m**2").magnitude
    phi = lumens_per_luminaire.to("lumen").magnitude
    if e <= 0 or a <= 0 or phi <= 0:
        raise ValueError("target_illuminance, area, and lumens_per_luminaire must be positive")
    return e * a / (phi * coefficient_of_utilization * light_loss_factor)


def lighting_power_density(
    *,
    luminaire_count: int,
    input_watts_per_luminaire: Quantity,
    area: Quantity,
) -> Quantity:
    """The installed lighting power density, LPD = n·W/A — the energy-code metric.

    Energy codes cap how much connected lighting power a space may draw per unit floor area:
    LPD = n·W/A, from the ``luminaire_count`` n, the ``input_watts_per_luminaire`` W (the fixture's
    total input power, driver included — not the lamp lumens), and the floor ``area`` A. It is the
    lever a code like ASHRAE 90.1 or the IECC pulls against illuminance: more fixtures light the
    room better but push the LPD up toward the allowance. Returns the power density in W/m².
    """
    _check(input_watts_per_luminaire, "[power]", "input_watts_per_luminaire")
    _check(area, "[length]**2", "area")
    if luminaire_count <= 0:
        raise ValueError("luminaire_count must be positive")
    a = area.to("m**2").magnitude
    if a <= 0:
        raise ValueError("area must be positive")
    watts = input_watts_per_luminaire.to("W").magnitude
    return Quantity(magnitude=luminaire_count * watts / a, unit="W/m**2")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _check_coefficient(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")
