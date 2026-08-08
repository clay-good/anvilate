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

A third relation bounds how precisely nature allows two conjugate quantities to be known at once:
Heisenberg's uncertainty principle, Δx·Δp ≥ ℏ/2 for position and momentum (and ΔE·Δt ≥ ℏ/2 for
energy and time). Confining a particle to a small Δx forces a large momentum spread, and a
short-lived state has a correspondingly broad energy (its natural linewidth). These give the minimum
uncertainties at the equality (best case).
"""

from __future__ import annotations

from ..units import Quantity

_PLANCK_CONSTANT = 6.62607015e-34  # J*s
_HBAR = 1.054571817e-34  # J*s, reduced Planck constant

__all__ = [
    "de_broglie_wavelength",
    "minimum_energy_uncertainty",
    "minimum_momentum_uncertainty",
    "minimum_position_uncertainty",
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


def minimum_momentum_uncertainty(*, position_uncertainty: Quantity) -> Quantity:
    """The minimum momentum uncertainty, Δp = ℏ/(2·Δx).

    The smallest momentum spread compatible with a position spread ``position_uncertainty`` Δx, from
    Heisenberg's principle at the equality: Δp = ℏ/(2·Δx). Pinning a particle to a tighter Δx forces
    a larger momentum uncertainty — the reason a confined electron cannot sit still. Returns the
    momentum uncertainty in kg*m/s.
    """
    _check(position_uncertainty, "[length]", "position_uncertainty")
    dx = position_uncertainty.to("m").magnitude
    if dx <= 0:
        raise ValueError("position_uncertainty must be positive")
    return Quantity(magnitude=_HBAR / (2.0 * dx), unit="kg*m/s")


def minimum_position_uncertainty(*, momentum_uncertainty: Quantity) -> Quantity:
    """The minimum position uncertainty, Δx = ℏ/(2·Δp).

    The smallest position spread compatible with a momentum spread ``momentum_uncertainty`` Δp, the
    inverse of :func:`minimum_momentum_uncertainty`: Δx = ℏ/(2·Δp). A well-defined momentum
    (small Δp) means the particle is delocalized over a large Δx. Returns the position uncertainty
    in m.
    """
    _check(momentum_uncertainty, "[momentum]", "momentum_uncertainty")
    dp = momentum_uncertainty.to("kg*m/s").magnitude
    if dp <= 0:
        raise ValueError("momentum_uncertainty must be positive")
    return Quantity(magnitude=_HBAR / (2.0 * dp), unit="m")


def minimum_energy_uncertainty(*, lifetime: Quantity) -> Quantity:
    """The minimum energy uncertainty, ΔE = ℏ/(2·Δt).

    The smallest energy spread of a state that lives for a time ``lifetime`` Δt, from the
    energy-time uncertainty relation: ΔE = ℏ/(2·Δt). A short-lived excited state has a broad energy,
    the natural linewidth of a spectral line, wider for faster-decaying states. Returns the energy
    uncertainty in J (convert to eV).
    """
    _check(lifetime, "[time]", "lifetime")
    dt = lifetime.to("s").magnitude
    if dt <= 0:
        raise ValueError("lifetime must be positive")
    return Quantity(magnitude=_HBAR / (2.0 * dt), unit="J")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
