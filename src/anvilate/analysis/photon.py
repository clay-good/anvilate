"""T1 analytical photon-energy (Planck) checks (closed-form).

Light comes in quanta: each photon carries an energy fixed by its wavelength alone, E = h*c/lambda.
This single relation underlies photonics wherever light and matter trade energy quantum by quantum —
the band-gap a photon must clear to free a charge in a solar cell or photodiode, the energy an LED
photon carries, the line energies of a spectrometer. It is distinct from the thermal-emission peak
of :func:`anvilate.analysis.thermal.wien_peak_wavelength` (which locates the brightest wavelength of
a hot body): here the concern is the energy and count of individual photons, not a spectrum's shape.

The photon energy is E = h*c/lambda, from the Planck constant h, the speed of light c, and the
wavelength lambda — shorter wavelength, higher energy, so a blue photon carries more than a red one.
Inverting it, lambda = h*c/E gives the wavelength that matches an energy (e.g. a semiconductor band
gap). Dividing an optical power by the per-photon energy gives the photon flux, Phi = P*lambda/
(h*c) — the number of photons per second a beam or detector sees, the currency of low-light sensing.

Sources: Griffiths, *Introduction to Quantum Mechanics* — the photon energy E = h·c/lambda, the
wavelength an energy corresponds to, and the photon flux a radiant power at that energy carries.
"""

from __future__ import annotations

from ..units import Quantity

_PLANCK_CONSTANT = 6.62607015e-34  # J*s
_SPEED_OF_LIGHT = 299792458.0  # m/s
_HC = _PLANCK_CONSTANT * _SPEED_OF_LIGHT  # J*m

__all__ = [
    "photon_energy",
    "photon_flux",
    "photon_wavelength_from_energy",
]


def photon_energy(*, wavelength: Quantity) -> Quantity:
    """The energy of a photon, E = h*c/lambda.

    The energy a single photon of a given ``wavelength`` lambda carries, E = h*c/lambda. Shorter
    wavelengths carry more energy, so this sets whether a photon can free a charge across a
    semiconductor band gap or excite a given transition. Returns the energy in J (convert to eV for
    the electronvolt scale that photonics uses). Visible light spans roughly 1.6-3.3 eV.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return Quantity(magnitude=_HC / lam, unit="J")


def photon_wavelength_from_energy(*, energy: Quantity) -> Quantity:
    """The wavelength matching a photon energy, lambda = h*c/E.

    The inverse of :func:`photon_energy`: the wavelength of a photon of a given ``energy`` E,
    lambda = h*c/E. It answers the design question the other way — the longest wavelength a detector
    of a given band-gap energy responds to, or the wavelength an atomic transition emits. Returns
    the wavelength in m.
    """
    _check(energy, "[energy]", "energy")
    e = energy.to("J").magnitude
    if e <= 0:
        raise ValueError("energy must be positive")
    return Quantity(magnitude=_HC / e, unit="m")


def photon_flux(*, optical_power: Quantity, wavelength: Quantity) -> Quantity:
    """The photon flux of a beam, Phi = P*lambda/(h*c).

    The number of photons per second in a beam of ``optical_power`` P at ``wavelength`` lambda: the
    power divided by the per-photon energy, Phi = P/(h*c/lambda) = P*lambda/(h*c). It is the count a
    photodetector must register and the shot-noise floor of low-light sensing. Returns the flux in
    1/s (photons per second).
    """
    _check(optical_power, "[power]", "optical_power")
    _check(wavelength, "[length]", "wavelength")
    p = optical_power.to("W").magnitude
    lam = wavelength.to("m").magnitude
    if p < 0:
        raise ValueError("optical_power must be non-negative")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return Quantity(magnitude=p * lam / _HC, unit="1/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
