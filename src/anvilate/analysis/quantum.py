"""T1 analytical quantum (photoelectric / de Broglie) checks (closed-form).

Two foundational quantum relations turn up in real instruments. The photoelectric effect governs how
light ejects electrons from a surface — the physics of photomultipliers, photocathodes, and the
photoemission behind night-vision and photoelectron spectroscopy. The de Broglie relation gives the
wavelength of a moving particle, which sets the resolution of an electron microscope. Both build on
the photon quantum of :mod:`anvilate.analysis.photon`, extending it from light to the emission and
wave nature of matter.

A photon of frequency f delivers energy h*f; a surface holds its electrons with a work function phi,
so the most energetic ejected electron carries the surplus, KE_max = h*f - phi (Einstein's
photoelectric equation). Below the threshold frequency f0 = phi/h no photon has enough energy and no
electron escapes, however bright the light. Separately, a particle of momentum p = m*v behaves as a
wave of wavelength lambda = h/p — tiny for everyday objects but nanometre-scale for a fast electron,
which is why electron microscopes out-resolve light ones.
"""

from __future__ import annotations

from ..units import Quantity

_PLANCK_CONSTANT = 6.62607015e-34  # J*s

__all__ = [
    "de_broglie_wavelength",
    "photoelectric_max_kinetic_energy",
    "photoelectric_threshold_frequency",
]


def photoelectric_max_kinetic_energy(*, frequency: Quantity, work_function: Quantity) -> Quantity:
    """The maximum photoelectron kinetic energy, KE_max = h*f - phi.

    Einstein's photoelectric equation: a photon of ``frequency`` f delivers energy h*f, and the most
    energetic electron ejected from a surface of ``work_function`` phi carries the surplus,
    KE_max = h*f - phi. The frequency must clear the threshold (h*f > phi) or no electron escapes —
    this raises for a sub-threshold photon. Returns the kinetic energy in J (convert to eV).
    """
    _check(frequency, "1/[time]", "frequency")
    _check(work_function, "[energy]", "work_function")
    f = frequency.to("Hz").magnitude
    phi = work_function.to("J").magnitude
    if f <= 0:
        raise ValueError("frequency must be positive")
    if phi <= 0:
        raise ValueError("work_function must be positive")
    ke = _PLANCK_CONSTANT * f - phi
    if ke <= 0:
        raise ValueError(
            "photon energy does not exceed the work function; no photoemission "
            "(frequency is below the threshold)"
        )
    return Quantity(magnitude=ke, unit="J")


def photoelectric_threshold_frequency(*, work_function: Quantity) -> Quantity:
    """The photoelectric threshold frequency, f0 = phi/h.

    The lowest frequency of light that can eject an electron from a surface of ``work_function``
    phi: f0 = phi/h. Below it no photon carries enough energy, so no current flows however bright
    the beam — the sharp cutoff that classical wave theory could not explain. Returns the threshold
    frequency in Hz.
    """
    _check(work_function, "[energy]", "work_function")
    phi = work_function.to("J").magnitude
    if phi <= 0:
        raise ValueError("work_function must be positive")
    return Quantity(magnitude=phi / _PLANCK_CONSTANT, unit="Hz")


def de_broglie_wavelength(*, mass: Quantity, velocity: Quantity) -> Quantity:
    """The de Broglie wavelength, lambda = h/(m*v).

    The matter-wave wavelength of a particle of ``mass`` m moving at ``velocity`` v,
    lambda = h/(m*v). It is immeasurably small for macroscopic objects but reaches sub-nanometre for
    a fast electron, which is the resolution advantage an electron microscope has over a light one.
    (Non-relativistic; use with speeds well below c.) Returns the wavelength in m.
    """
    _check(mass, "[mass]", "mass")
    _check(velocity, "[length]/[time]", "velocity")
    m = mass.to("kg").magnitude
    v = velocity.to("m/s").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    if v <= 0:
        raise ValueError("velocity must be positive")
    return Quantity(magnitude=_PLANCK_CONSTANT / (m * v), unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
