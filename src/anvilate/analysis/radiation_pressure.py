"""T1 analytical radiation-pressure (photon momentum) checks (closed-form).

Light carries momentum as well as energy, so a beam pushes on whatever it strikes. The push is
tiny — micropascals in full sunlight — but it is real, and over a large, light sail it accumulates
into a usable thrust that needs no propellant. This is the mechanical side of light, distinct from
the energy-carrying view of :mod:`anvilate.analysis.photon` (which gives a photon's energy and flux)
and the reflection bookkeeping of :mod:`anvilate.analysis.fresnel`.

A single photon of wavelength λ carries momentum p = h/λ. Averaged over a beam, that momentum flux
becomes a radiation pressure P = (1 + R)·I/c, from the intensity I, the speed of light c, and the
surface reflectivity R — a perfect absorber (R = 0)
feels I/c, a perfect mirror (R = 1) feels twice that because it also recoils the reflected light.
Multiplied by the illuminated area it becomes the radiation force F = (1 + R)·I·A/c that drives a
solar sail. Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

_PLANCK = 6.62607015e-34  # J*s
_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "photon_momentum",
    "radiation_force",
    "radiation_pressure_from_intensity",
]


def photon_momentum(*, wavelength: Quantity) -> Quantity:
    """The photon momentum, p = h/λ.

    The momentum carried by a single photon of the given ``wavelength`` λ: p = h/λ, equivalently
    E/c. Shorter-wavelength (bluer, higher-energy) photons carry more momentum. It is the
    microscopic origin of radiation pressure. Returns the momentum in kg*m/s.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return Quantity(magnitude=_PLANCK / lam, unit="kg*m/s")


def radiation_pressure_from_intensity(
    *, intensity: Quantity, reflectivity: float = 0.0
) -> Quantity:
    """The radiation pressure, P = (1 + R)·I/c.

    The pressure a light beam of ``intensity`` I exerts on a surface of ``reflectivity`` R:
    P = (1 + R)·I/c. A perfect absorber (R = 0) feels I/c; a perfect mirror (R = 1) feels 2·I/c,
    since it must also reverse the momentum of the reflected light. In full sunlight (~1361 W/m²) it
    is only a few micropascals. Returns the radiation pressure in Pa.
    """
    _check(intensity, "[power]/[area]", "intensity")
    i = intensity.to("W/m**2").magnitude
    if i < 0:
        raise ValueError("intensity must be non-negative")
    if not 0.0 <= reflectivity <= 1.0:
        raise ValueError(f"reflectivity must be in [0, 1]; got {reflectivity}")
    return Quantity(magnitude=(1.0 + reflectivity) * i / _SPEED_OF_LIGHT, unit="Pa")


def radiation_force(*, intensity: Quantity, area: Quantity, reflectivity: float = 0.0) -> Quantity:
    """The radiation force, F = (1 + R)·I·A/c.

    The total force a light beam of ``intensity`` I exerts over an illuminated ``area`` A of
    ``reflectivity`` R: F = (1 + R)·I·A/c — the radiation pressure times the area. This is the
    propellant-free thrust of a solar sail, which is why sails are made large and reflective.
    Returns the force in N.
    """
    _check(intensity, "[power]/[area]", "intensity")
    _check(area, "[area]", "area")
    i = intensity.to("W/m**2").magnitude
    a = area.to("m**2").magnitude
    if i < 0:
        raise ValueError("intensity must be non-negative")
    if a <= 0:
        raise ValueError("area must be positive")
    if not 0.0 <= reflectivity <= 1.0:
        raise ValueError(f"reflectivity must be in [0, 1]; got {reflectivity}")
    return Quantity(magnitude=(1.0 + reflectivity) * i * a / _SPEED_OF_LIGHT, unit="N")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
