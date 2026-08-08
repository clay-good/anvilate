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
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "rectangular_waveguide_cutoff_frequency",
    "waveguide_guide_wavelength",
    "waveguide_phase_velocity",
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
    f = operating_frequency.to("Hz").magnitude
    f_c = cutoff_frequency.to("Hz").magnitude
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
    f = operating_frequency.to("Hz").magnitude
    f_c = cutoff_frequency.to("Hz").magnitude
    if f <= 0:
        raise ValueError("operating_frequency must be positive")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    if f <= f_c:
        raise ValueError("operating_frequency must exceed the cutoff frequency to propagate")
    return Quantity(magnitude=_SPEED_OF_LIGHT / sqrt(1.0 - (f_c / f) ** 2), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
