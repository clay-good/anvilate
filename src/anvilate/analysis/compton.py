"""T1 analytical Compton-scattering checks (closed-form).

When a high-energy photon (an X-ray or gamma ray) scatters off a loosely-bound electron, it hands
the electron some energy and comes away with a longer wavelength. The wavelength shift depends only
on the scattering angle, not on the incident wavelength — the clean signature that light carries
particle-like momentum. This governs the dominant interaction of medium-energy gamma rays with
matter (behind the attenuation of :mod:`anvilate.analysis.radiation_shielding`), the physics of
Compton cameras, and the scattering the photon quanta of :mod:`anvilate.analysis.photon` undergo.

The Compton shift is Delta_lambda = lambda_C * (1 - cos(theta)), where lambda_C = h/(m_e*c) is the
electron Compton wavelength (2.426 pm) and theta is the scattering angle — zero for a grazing
photon, maximal for backscatter. Adding it to the incident wavelength gives the scattered photon
wavelength lambda' = lambda + Delta_lambda, and the energy the photon loses,
E_e = h*c*(1/lambda - 1/lambda'), is the recoil energy carried off by the electron.

Sources: Krane, *Modern Physics* (the Compton effect) — the wavelength shift a photon suffers
scattering off a free electron, the scattered wavelength, and the kinetic energy the electron
takes away.
"""

from __future__ import annotations

from math import cos, radians

from ..units import Quantity

_PLANCK_CONSTANT = 6.62607015e-34  # J*s
_ELECTRON_MASS = 9.1093837015e-31  # kg
_SPEED_OF_LIGHT = 299792458.0  # m/s
_COMPTON_WAVELENGTH = _PLANCK_CONSTANT / (_ELECTRON_MASS * _SPEED_OF_LIGHT)  # m
_HC = _PLANCK_CONSTANT * _SPEED_OF_LIGHT  # J*m

__all__ = [
    "compton_electron_energy",
    "compton_scattered_wavelength",
    "compton_wavelength_shift",
]


def compton_wavelength_shift(*, scattering_angle: float) -> Quantity:
    """The Compton wavelength shift, Delta_lambda = lambda_C * (1 - cos(theta)).

    The increase in a photon's wavelength when it scatters off an electron through a
    ``scattering_angle`` theta (degrees): Delta_lambda = lambda_C * (1 - cos(theta)), with the
    electron Compton wavelength lambda_C = 2.426 pm. It is zero for forward scatter and largest
    (2*lambda_C) for backscatter, and it is independent of the incident wavelength. Returns it in m.
    """
    if not 0.0 <= scattering_angle <= 180.0:
        raise ValueError("scattering_angle must be in [0, 180] degrees")
    return Quantity(
        magnitude=_COMPTON_WAVELENGTH * (1.0 - cos(radians(scattering_angle))), unit="m"
    )


def compton_scattered_wavelength(
    *, incident_wavelength: Quantity, scattering_angle: float
) -> Quantity:
    """The scattered photon wavelength, lambda' = lambda + lambda_C*(1 - cos(theta)).

    The wavelength of a photon after Compton scattering: the ``incident_wavelength`` lambda plus the
    Compton shift for the ``scattering_angle`` theta. The scattered photon is always longer in
    wavelength (lower-energy) than the incident one, having given energy to the electron. Returns it
    in m.
    """
    _check(incident_wavelength, "[length]", "incident_wavelength")
    lam = incident_wavelength.to("m").magnitude
    if lam <= 0:
        raise ValueError("incident_wavelength must be positive")
    if not 0.0 <= scattering_angle <= 180.0:
        raise ValueError("scattering_angle must be in [0, 180] degrees")
    shift = _COMPTON_WAVELENGTH * (1.0 - cos(radians(scattering_angle)))
    return Quantity(magnitude=lam + shift, unit="m")


def compton_electron_energy(*, incident_wavelength: Quantity, scattering_angle: float) -> Quantity:
    """The recoil electron energy, E_e = h*c*(1/lambda - 1/lambda').

    The energy the photon loses to the recoiling electron: E_e = h*c*(1/lambda - 1/lambda'), from
    the ``incident_wavelength`` lambda and the scattered wavelength lambda' for the
    ``scattering_angle`` theta. It is zero for forward scatter, greatest for backscatter, and what a
    detector measures. Returns the electron energy in J (convert to keV for x-ray/gamma scales).
    """
    _check(incident_wavelength, "[length]", "incident_wavelength")
    lam = incident_wavelength.to("m").magnitude
    if lam <= 0:
        raise ValueError("incident_wavelength must be positive")
    if not 0.0 <= scattering_angle <= 180.0:
        raise ValueError("scattering_angle must be in [0, 180] degrees")
    lam_scattered = lam + _COMPTON_WAVELENGTH * (1.0 - cos(radians(scattering_angle)))
    return Quantity(magnitude=_HC * (1.0 / lam - 1.0 / lam_scattered), unit="J")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
