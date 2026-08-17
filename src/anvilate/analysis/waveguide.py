"""T1 analytical rectangular-waveguide checks (closed-form, dominant TE10 mode).

A hollow metal waveguide carries microwaves only above a cutoff frequency set by its cross-section:
below it the wave is evanescent and does not propagate. Above cutoff the guide is dispersive — the
wavelength inside is longer than in free space and the phase velocity exceeds the speed of light
(the energy still travels slower). This governs the sizing of radar and satellite plumbing, and it
is distinct from the unbounded free-space propagation of :mod:`anvilate.analysis.antenna`: the walls
impose a cutoff and stretch the guide wavelength.

For the dominant TE10 mode of a rectangular guide, the cutoff frequency is f_c = c/(2*a), from the
broad inside dimension a — a wider guide passes lower frequencies. Above f_c the guide wavelength is
lambda_g = (c/f) / sqrt(1 - (f_c/f)^2), always longer than the free-space c/f, and the phase
velocity is v_p = c / sqrt(1 - (f_c/f)^2), greater than c. Both diverge as the operating frequency
nears cutoff, which is why a guide is run well above f_c. Air-filled guide is assumed (speed c).

Sources: Pozar, *Microwave Engineering*, and Balanis, *Advanced Engineering
Electromagnetics*, for the cutoff-frequency and mode relations.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.rotation import count_rate_per_second

_SPEED_OF_LIGHT = 299792458.0  # m/s
_FREE_SPACE_IMPEDANCE = 376.730313668  # ohm, eta_0

__all__ = [
    "waveguide_tm_wave_impedance",
    "rectangular_waveguide_cutoff_frequency",
    "rectangular_waveguide_mode_cutoff_frequency",
    "waveguide_group_velocity",
    "waveguide_guide_wavelength",
    "waveguide_phase_velocity",
    "waveguide_te_wave_impedance",
]


def rectangular_waveguide_cutoff_frequency(*, broad_dimension: Quantity) -> Quantity:
    """The dominant-mode cutoff frequency, f_c = c/(2*a).

    The lowest frequency a rectangular waveguide passes, set by its broad inside dimension
    ``broad_dimension`` a for the dominant TE10 mode: f_c = c/(2*a). Below it the wave is evanescent
    and dies away; a wider guide has a lower cutoff and carries lower bands. Returns f_c in Hz.
    """
    _check(broad_dimension, "[length]", "broad_dimension")
    a = broad_dimension.to("m").magnitude
    if a <= 0:
        raise ValueError("broad_dimension must be positive")
    return Quantity(magnitude=_SPEED_OF_LIGHT / (2.0 * a), unit="Hz")


def waveguide_guide_wavelength(
    *, operating_frequency: Quantity, cutoff_frequency: Quantity
) -> Quantity:
    """The guide wavelength, lambda_g = (c/f) / sqrt(1 - (f_c/f)^2).

    The wavelength of the wave inside the guide at ``operating_frequency`` f, given the
    ``cutoff_frequency`` f_c: lambda_g = (c/f) / sqrt(1 - (f_c/f)^2). It is always longer than the
    free-space wavelength c/f and grows without bound as f approaches cutoff. It sets the spacing of
    slots and irises in waveguide components. The operating frequency must exceed cutoff. Returns
    the guide wavelength in m.
    """
    _check(operating_frequency, "1/[time]", "operating_frequency")
    _check(cutoff_frequency, "1/[time]", "cutoff_frequency")
    f = count_rate_per_second(operating_frequency, name="operating_frequency")
    f_c = count_rate_per_second(cutoff_frequency, name="cutoff_frequency")
    if f <= 0:
        raise ValueError("operating_frequency must be positive")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    if f <= f_c:
        raise ValueError("operating_frequency must exceed the cutoff frequency to propagate")
    return Quantity(magnitude=(_SPEED_OF_LIGHT / f) / sqrt(1.0 - (f_c / f) ** 2), unit="m")


def waveguide_phase_velocity(
    *, operating_frequency: Quantity, cutoff_frequency: Quantity
) -> Quantity:
    """The phase velocity, v_p = c / sqrt(1 - (f_c/f)^2).

    The speed of the wave's phase fronts inside the guide at ``operating_frequency`` f above the
    ``cutoff_frequency`` f_c: v_p = c / sqrt(1 - (f_c/f)^2). It exceeds the speed of light (energy
    and information travel at the slower group velocity, c^2/v_p), and diverges near cutoff — a
    hallmark of the guide's dispersion. The operating frequency must exceed cutoff. Returns v_p in
    m/s.
    """
    _check(operating_frequency, "1/[time]", "operating_frequency")
    _check(cutoff_frequency, "1/[time]", "cutoff_frequency")
    f = count_rate_per_second(operating_frequency, name="operating_frequency")
    f_c = count_rate_per_second(cutoff_frequency, name="cutoff_frequency")
    if f <= 0:
        raise ValueError("operating_frequency must be positive")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    if f <= f_c:
        raise ValueError("operating_frequency must exceed the cutoff frequency to propagate")
    return Quantity(magnitude=_SPEED_OF_LIGHT / sqrt(1.0 - (f_c / f) ** 2), unit="m/s")


def waveguide_group_velocity(
    *, operating_frequency: Quantity, cutoff_frequency: Quantity
) -> Quantity:
    """The waveguide group velocity, v_g = c·√(1 − (f_c/f)²).

    The speed at which energy and a signal's envelope actually travel down the guide — the physical
    counterpart to the superluminal phase velocity (:func:`waveguide_phase_velocity`), with which it
    obeys v_p·v_g = c². At ``operating_frequency`` f above the ``cutoff_frequency`` f_c,
    v_g = c·√(1 − (f_c/f)²): it is always below c, and falls to zero as f approaches cutoff (where
    the wave stops propagating). It sets the signal delay and the dispersion of a pulse through the
    guide. The operating frequency must exceed cutoff. Returns v_g in m/s.
    """
    _check(operating_frequency, "1/[time]", "operating_frequency")
    _check(cutoff_frequency, "1/[time]", "cutoff_frequency")
    f = count_rate_per_second(operating_frequency, name="operating_frequency")
    f_c = count_rate_per_second(cutoff_frequency, name="cutoff_frequency")
    if f <= 0:
        raise ValueError("operating_frequency must be positive")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    if f <= f_c:
        raise ValueError("operating_frequency must exceed the cutoff frequency to propagate")
    return Quantity(magnitude=_SPEED_OF_LIGHT * sqrt(1.0 - (f_c / f) ** 2), unit="m/s")


def waveguide_te_wave_impedance(
    *, operating_frequency: Quantity, cutoff_frequency: Quantity
) -> Quantity:
    """The TE-mode wave impedance in a waveguide, Z_TE = η₀/√(1 − (f_c/f)²).

    The ratio of transverse electric to magnetic field for a transverse-electric mode, which sets
    how the guide matches to a load or another section: Z_TE = η₀/√(1 − (f_c/f)²), with the
    free-space impedance η₀ ≈ 377 Ω, the ``operating_frequency`` f, and the ``cutoff_frequency``
    f_c. It is *higher* than η₀ (and diverges at cutoff), the opposite of the TM-mode impedance — a
    TE mode looks inductive relative to free space. The operating frequency must exceed cutoff.
    Returns the wave impedance in ohms.
    """
    _check(operating_frequency, "1/[time]", "operating_frequency")
    _check(cutoff_frequency, "1/[time]", "cutoff_frequency")
    f = count_rate_per_second(operating_frequency, name="operating_frequency")
    f_c = count_rate_per_second(cutoff_frequency, name="cutoff_frequency")
    if f <= 0:
        raise ValueError("operating_frequency must be positive")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    if f <= f_c:
        raise ValueError("operating_frequency must exceed the cutoff frequency to propagate")
    return Quantity(magnitude=_FREE_SPACE_IMPEDANCE / sqrt(1.0 - (f_c / f) ** 2), unit="ohm")


def rectangular_waveguide_mode_cutoff_frequency(
    *,
    broad_dimension: Quantity,
    narrow_dimension: Quantity,
    mode_m: int = 1,
    mode_n: int = 0,
) -> Quantity:
    """Any TE_mn / TM_mn mode's cutoff frequency, f_c = (c/2)·√((m/a)² + (n/b)²).

    The general form that :func:`rectangular_waveguide_cutoff_frequency` gives only the dominant
    case of. From the ``broad_dimension`` a, the ``narrow_dimension`` b, and the mode indices
    ``mode_m`` and ``mode_n`` (half-wave variations across a and b respectively):
    f_c = (c/2)·√((m/a)² + (n/b)²). At m = 1, n = 0 it reduces exactly to c/(2a), the dominant TE10
    result.

    The reason to have it is the *second* mode, not the first. A waveguide is only useful over the
    band where exactly one mode propagates, and the top of that band is set by whichever higher
    mode cuts on next — TE20 at c/a for a standard 2:1 guide, giving the familiar single-mode
    octave. Run a guide above that and power splits between modes with different phase velocities,
    which shows up as dispersion and unrepeatable phase rather than as an obvious failure. Both
    indices must be non-negative and not both zero (there is no TE00 mode). Returns f_c in Hz.
    """
    _check(broad_dimension, "[length]", "broad_dimension")
    _check(narrow_dimension, "[length]", "narrow_dimension")
    a = broad_dimension.to("m").magnitude
    b = narrow_dimension.to("m").magnitude
    if a <= 0 or b <= 0:
        raise ValueError("broad_dimension and narrow_dimension must be positive")
    if int(mode_m) != mode_m or int(mode_n) != mode_n:
        raise ValueError(f"mode indices must be whole numbers; got m = {mode_m}, n = {mode_n}")
    m, n = int(mode_m), int(mode_n)
    if m < 0 or n < 0:
        raise ValueError(f"mode indices must be non-negative; got m = {m}, n = {n}")
    if m == 0 and n == 0:
        raise ValueError("there is no TE00 mode: the mode indices must not both be zero")
    cutoff = 0.5 * _SPEED_OF_LIGHT * sqrt((m / a) ** 2 + (n / b) ** 2)
    return Quantity(magnitude=cutoff, unit="Hz")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def waveguide_tm_wave_impedance(
    *, operating_frequency: Quantity, cutoff_frequency: Quantity
) -> Quantity:
    """The TM-mode wave impedance, Z_TM = η₀·sqrt(1 − (f_c/f)²).

    The ratio of transverse electric to transverse magnetic field for a TM mode in a hollow
    waveguide. :func:`waveguide_te_wave_impedance`'s own docstring refers to "the opposite of the
    TM-mode impedance", which did not exist in the library, even though
    :func:`rectangular_waveguide_mode_cutoff_frequency` already covers TM_mn cutoffs.

    The two are reciprocal about the free-space impedance: a TE mode looks *inductive*, rising
    above η₀ = 376.7 Ω and diverging at cutoff, while a TM mode looks *capacitive*, falling below
    η₀ and going to zero at cutoff. In WR-90 (f_c = 6.557 GHz) at 10 GHz the TE impedance is 499 Ω
    and the TM impedance 284 Ω — matching a TM-mode launcher or a dielectric window with the TE
    number designs in a 1.75× mismatch, roughly VSWR 1.75, before anything is built.

    The same square-root factor is the group-velocity ratio of :func:`waveguide_group_velocity`,
    so Z_TM/η₀ and v_g/c are the same number. The operating frequency must exceed the cutoff, or
    the mode is evanescent and carries no power. Returns the wave impedance in ohm.
    """
    _check(operating_frequency, "[frequency]", "operating_frequency")
    _check(cutoff_frequency, "[frequency]", "cutoff_frequency")
    f = count_rate_per_second(operating_frequency, name="operating_frequency")
    f_c = count_rate_per_second(cutoff_frequency, name="cutoff_frequency")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    if f <= f_c:
        raise ValueError(
            f"operating_frequency {operating_frequency} must exceed cutoff_frequency "
            f"{cutoff_frequency}; below cutoff the mode is evanescent"
        )
    return Quantity(magnitude=_FREE_SPACE_IMPEDANCE * sqrt(1.0 - (f_c / f) ** 2), unit="ohm")
