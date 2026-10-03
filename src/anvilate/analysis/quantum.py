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

Sources: Griffiths, *Introduction to Quantum Mechanics*, for the de Broglie,
particle-in-a-box and photon-energy relations.
"""

from __future__ import annotations

from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.rotation import count_rate_per_second

_RADIATION_SOURCE = "the light source's spectral specification (photon frequency)"
_MATERIAL_SOURCE = "the cited work-function table for the emitter surface"
_PARTICLE_SOURCE = "the particle's rest mass and speed from the experiment record"
_SYSTEM_SOURCE = "the problem statement's confinement, levels, and uncertainties"
_THRESHOLD_SOURCE = "the photon frequency against the emitter's tabulated work function"
_REGIME_SOURCE = "the particle's measured speed, or the relativistic de Broglie form"


class _QuantumInputError(RefusalError, ValueError):
    """A quantum-physics input that cannot be used without correction."""


def _quantum_refusal(message: str, *, subject: str, source: str) -> _QuantumInputError:
    return _QuantumInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _quantum_input_source(name: str) -> str:
    if name == "frequency":
        return _RADIATION_SOURCE
    if name == "work_function":
        return _MATERIAL_SOURCE
    if name in {"mass", "particle_mass", "velocity"}:
        return _PARTICLE_SOURCE
    return _SYSTEM_SOURCE


_PLANCK_CONSTANT = 6.62607015e-34  # J*s
_HBAR = 1.054571817e-34  # J*s, reduced Planck constant
_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "de_broglie_wavelength",
    "minimum_energy_uncertainty",
    "minimum_momentum_uncertainty",
    "minimum_position_uncertainty",
    "particle_in_box_energy",
    "particle_in_box_transition_wavelength",
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
    f = count_rate_per_second(frequency, name="frequency")
    phi = work_function.to("J").magnitude
    if f <= 0:
        raise _quantum_refusal(
            "frequency must be positive", subject="frequency", source=_RADIATION_SOURCE
        )
    if phi <= 0:
        raise _quantum_refusal(
            "work_function must be positive", subject="work_function", source=_MATERIAL_SOURCE
        )
    ke = _PLANCK_CONSTANT * f - phi
    if ke <= 0:
        raise _quantum_refusal(
            "photon energy does not exceed the work function; no photoemission "
            "(frequency is below the threshold)",
            subject="frequency and work_function",
            source=_THRESHOLD_SOURCE,
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
        raise _quantum_refusal(
            "work_function must be positive", subject="work_function", source=_MATERIAL_SOURCE
        )
    return Quantity(magnitude=phi / _PLANCK_CONSTANT, unit="Hz")


# Past a tenth of c the Lorentz factor is over 1.005 and climbing quadratically, which is
# where "well below c" stops being true for a wavelength quoted to three figures.
_NONRELATIVISTIC_SPEED_FRACTION = 0.10


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
        raise _quantum_refusal("mass must be positive", subject="mass", source=_PARTICLE_SOURCE)
    if v <= 0:
        raise _quantum_refusal(
            "velocity must be positive", subject="velocity", source=_PARTICLE_SOURCE
        )
    # h/(mv) is the non-relativistic form and the docstring says so. It has no ceiling: at
    # v = c and beyond it kept returning a finite picometre wavelength. Even inside the
    # range it drifts fast — at the docstring's own motivating case, a 200 kV TEM electron
    # at beta = 0.695, it is 1.39x coarse against h/(gamma*m*v). _SPEED_OF_LIGHT is already
    # defined in this module and was never consulted; `relativity.py` makes this same check.
    if v >= _SPEED_OF_LIGHT:
        raise _quantum_refusal(
            f"velocity is {v:.6g} m/s, at or above the speed of light. The de Broglie form "
            f"here is h/(m*v), which is non-relativistic and has no ceiling; use the "
            f"relativistic h/(gamma*m*v)",
            subject="velocity",
            source=_REGIME_SOURCE,
        )
    if v > _NONRELATIVISTIC_SPEED_FRACTION * _SPEED_OF_LIGHT:
        beta = v / _SPEED_OF_LIGHT
        gamma = 1.0 / sqrt(1.0 - beta**2)
        raise _quantum_refusal(
            f"velocity is {beta:.4g}c, past the non-relativistic range this form holds in. "
            f"h/(m*v) runs {gamma:.4g}x long here against the relativistic h/(gamma*m*v); "
            f"a 200 kV electron microscope already sits at 0.695c",
            subject="velocity",
            source=_REGIME_SOURCE,
        )
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
        raise _quantum_refusal(
            "position_uncertainty must be positive",
            subject="position_uncertainty",
            source=_SYSTEM_SOURCE,
        )
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
        raise _quantum_refusal(
            "momentum_uncertainty must be positive",
            subject="momentum_uncertainty",
            source=_SYSTEM_SOURCE,
        )
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
        raise _quantum_refusal(
            "lifetime must be positive", subject="lifetime", source=_SYSTEM_SOURCE
        )
    return Quantity(magnitude=_HBAR / (2.0 * dt), unit="J")


def particle_in_box_energy(
    *, quantum_number: int, particle_mass: Quantity, box_length: Quantity
) -> Quantity:
    """The energy level of a particle in a 1-D box, E_n = n²·h²/(8·m·L²).

    The canonical bound-state result: a particle of ``particle_mass`` m confined to an infinite
    square well of width ``box_length`` L can only hold the discrete energies E_n = n²·h²/(8·m·L²),
    indexed by the ``quantum_number`` n (1, 2, 3, …). The levels are quantized because only whole
    numbers of half-wavelengths fit the box, and they crowd upward as n². The n = 1 level is the
    zero-point energy — a confined particle can never be perfectly at rest — and the spacing widens
    as the box shrinks, which is why quantum confinement (a smaller box) blue-shifts a quantum dot.
    ``quantum_number`` is a positive integer. Returns the energy in joules.
    """
    _check(particle_mass, "[mass]", "particle_mass")
    _check(box_length, "[length]", "box_length")
    if quantum_number < 1:
        raise _quantum_refusal(
            "quantum_number must be a positive integer",
            subject="quantum_number",
            source=_SYSTEM_SOURCE,
        )
    m = particle_mass.to("kg").magnitude
    length = box_length.to("m").magnitude
    if m <= 0:
        raise _quantum_refusal(
            "particle_mass must be positive", subject="particle_mass", source=_PARTICLE_SOURCE
        )
    if length <= 0:
        raise _quantum_refusal(
            "box_length must be positive", subject="box_length", source=_SYSTEM_SOURCE
        )
    energy = quantum_number**2 * _PLANCK_CONSTANT**2 / (8.0 * m * length**2)
    return Quantity(magnitude=energy, unit="J")


def particle_in_box_transition_wavelength(
    *,
    lower_level: int,
    upper_level: int,
    particle_mass: Quantity,
    box_length: Quantity,
) -> Quantity:
    """The photon wavelength of a particle-in-a-box transition, λ = h·c/(E_upper − E_lower).

    The colour a confined particle absorbs or emits when it jumps between two box levels: the photon
    carries the energy gap ΔE = E_upper − E_lower of :func:`particle_in_box_energy`, so its
    wavelength is λ = h·c/ΔE. This is the simplest model of a quantum dot or a conjugated dye — a
    smaller
    ``box_length`` L widens the gap and shifts the colour toward the blue, which is how quantum-dot
    displays tune their colour by particle size. ``lower_level`` and ``upper_level`` are positive
    integers with the upper above the lower. Returns the transition wavelength in metres.
    """
    _check(particle_mass, "[mass]", "particle_mass")
    _check(box_length, "[length]", "box_length")
    for subject, magnitude in (("lower_level", lower_level), ("upper_level", upper_level)):
        if magnitude < 1:
            raise _quantum_refusal(
                "lower_level and upper_level must be positive integers",
                subject=subject,
                source=_SYSTEM_SOURCE,
            )
    if upper_level <= lower_level:
        raise _quantum_refusal(
            "upper_level must exceed lower_level", subject="upper_level", source=_SYSTEM_SOURCE
        )
    m = particle_mass.to("kg").magnitude
    length = box_length.to("m").magnitude
    if m <= 0:
        raise _quantum_refusal(
            "particle_mass must be positive", subject="particle_mass", source=_PARTICLE_SOURCE
        )
    if length <= 0:
        raise _quantum_refusal(
            "box_length must be positive", subject="box_length", source=_SYSTEM_SOURCE
        )
    prefactor = _PLANCK_CONSTANT**2 / (8.0 * m * length**2)
    delta_e = (upper_level**2 - lower_level**2) * prefactor
    wavelength = _PLANCK_CONSTANT * _SPEED_OF_LIGHT / delta_e
    return Quantity(magnitude=wavelength, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _quantum_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_quantum_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _quantum_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_quantum_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
