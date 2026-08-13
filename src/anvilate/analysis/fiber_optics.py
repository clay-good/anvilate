"""T1 analytical fiber-optic chromatic-dispersion checks (closed-form).

An optical fiber carries different wavelengths at slightly different speeds, so a light pulse —
never perfectly monochromatic — spreads out as it travels. This chromatic dispersion is what
ultimately limits how fast and how far a fiber link can run: spread the pulses too much and adjacent
bits blur into each other. It is the reach-limiting companion to the numerical aperture and
acceptance angle of :mod:`anvilate.analysis.optics`, which govern getting light *into* the fiber.

The pulse broadening over a link is Δτ = D·L·Δλ, from the fiber dispersion parameter D (about
17 ps/(nm·km) for standard single-mode fiber at 1550 nm), the length L, and the source spectral
width Δλ. Keeping the spread within a bit slot caps the bit rate at roughly B = 1/(4·Δτ), and
inverting that gives the dispersion-limited reach L = 1/(4·B·D·Δλ) for a target bit rate — the span
beyond which a link needs dispersion compensation or a narrower source. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

_SINGLE_MODE_CUTOFF_V = 2.405  # first zero of the Bessel function J0

__all__ = [
    "chromatic_dispersion_broadening",
    "dispersion_limited_bit_rate",
    "dispersion_limited_distance",
    "fiber_mode_count",
    "fiber_single_mode_cutoff_wavelength",
    "fiber_v_number",
]


def chromatic_dispersion_broadening(
    *, dispersion_parameter: Quantity, length: Quantity, spectral_width: Quantity
) -> Quantity:
    """The chromatic-dispersion pulse broadening, Δτ = D·L·Δλ.

    How much a pulse spreads over a fiber link, from the ``dispersion_parameter`` D, the ``length``
    L, and the source ``spectral_width`` Δλ: Δτ = D·L·Δλ. A wider source or a longer span spreads
    the pulse more; it is the spread that must stay within a bit slot. Returns the broadening in s.
    """
    _check(dispersion_parameter, "[time]/[length]**2", "dispersion_parameter")
    _check(length, "[length]", "length")
    _check(spectral_width, "[length]", "spectral_width")
    d = dispersion_parameter.to("s/m**2").magnitude
    ell = length.to("m").magnitude
    dlam = spectral_width.to("m").magnitude
    if ell < 0:
        raise ValueError("length must be non-negative")
    if dlam < 0:
        raise ValueError("spectral_width must be non-negative")
    return Quantity(magnitude=abs(d) * ell * dlam, unit="s")


def dispersion_limited_bit_rate(*, pulse_broadening: Quantity) -> Quantity:
    """The dispersion-limited bit rate, B = 1/(4·Δτ).

    The greatest bit rate a link tolerates before dispersion smears adjacent bits together, from the
    ``pulse_broadening`` Δτ: B = 1/(4·Δτ) (the common quarter-bit-slot criterion). A tighter pulse
    allows a faster line. Returns the bit rate in bit/s.
    """
    _check(pulse_broadening, "[time]", "pulse_broadening")
    dtau = pulse_broadening.to("s").magnitude
    if dtau <= 0:
        raise ValueError("pulse_broadening must be positive")
    return Quantity(magnitude=1.0 / (4.0 * dtau), unit="1/s")


def dispersion_limited_distance(
    *, bit_rate: Quantity, dispersion_parameter: Quantity, spectral_width: Quantity
) -> Quantity:
    """The dispersion-limited reach, L = 1/(4·B·D·Δλ).

    The longest span a fiber link can run at a target ``bit_rate`` B before chromatic dispersion
    limits it, from the ``dispersion_parameter`` D and the source ``spectral_width`` Δλ, by
    inverting the bit-rate criterion: L = 1/(4·B·D·Δλ). Faster rates and wider sources shorten it.
    Returns the maximum distance in m.
    """
    _check(bit_rate, "1/[time]", "bit_rate")
    _check(dispersion_parameter, "[time]/[length]**2", "dispersion_parameter")
    _check(spectral_width, "[length]", "spectral_width")
    b = bit_rate.to("1/s").magnitude
    d = abs(dispersion_parameter.to("s/m**2").magnitude)
    dlam = spectral_width.to("m").magnitude
    if b <= 0:
        raise ValueError("bit_rate must be positive")
    if d <= 0:
        raise ValueError("dispersion_parameter must be nonzero")
    if dlam <= 0:
        raise ValueError("spectral_width must be positive")
    return Quantity(magnitude=1.0 / (4.0 * b * d * dlam), unit="m")


def fiber_v_number(
    *,
    core_radius: Quantity,
    wavelength: Quantity,
    numerical_aperture: float,
) -> float:
    """The fiber V-number (normalized frequency), V = (2π·a/λ)·NA.

    The single dimensionless parameter that governs how many modes a step-index fiber guides:
    V = (2π·a/λ)·NA, from the ``core_radius`` a, the operating ``wavelength`` λ, and the
    ``numerical_aperture`` NA (:func:`~anvilate.analysis.optics.fiber_numerical_aperture`). When
    V ≤ 2.405 (the first zero of the Bessel function J₀) only the fundamental mode propagates and
    the fiber is single-mode; above it the fiber is multimode and the mode count grows as V².
    Shrinking the core or moving to a longer wavelength lowers V — the two knobs that turn a
    multimode fiber single-mode. Returns the dimensionless V-number.
    """
    _check(core_radius, "[length]", "core_radius")
    _check(wavelength, "[length]", "wavelength")
    a = core_radius.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if a <= 0:
        raise ValueError("core_radius must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if numerical_aperture <= 0:
        raise ValueError("numerical_aperture must be positive")
    return 2.0 * pi * a / lam * numerical_aperture


def fiber_mode_count(*, v_number: float) -> float:
    """The approximate number of modes in a step-index fiber, M ≈ V²/2.

    For a multimode step-index fiber well above cutoff, the number of guided modes (summed over both
    polarizations) is M ≈ V²/2, from the ``v_number`` V (:func:`fiber_v_number`). It counts the
    parallel spatial channels the fiber offers — the basis of its high coupling efficiency and
    étendue — but each carries a slightly different group delay, so a large mode count also means
    strong intermodal dispersion that limits the bandwidth. The estimate is asymptotic; near cutoff
    (V approaching 2.405, where M should be 1) it overpredicts. Returns the approximate mode count
    as a plain float.
    """
    if v_number <= 0:
        raise ValueError("v_number must be positive")
    return v_number**2 / 2.0


def fiber_single_mode_cutoff_wavelength(
    *,
    core_radius: Quantity,
    numerical_aperture: float,
) -> Quantity:
    """The single-mode cutoff wavelength of a fiber, λc = 2π·a·NA/2.405.

    The shortest wavelength at which a step-index fiber still carries only the fundamental mode:
    setting the V-number to its 2.405 cutoff and solving for wavelength gives λc = 2π·a·NA/2.405,
    from the ``core_radius`` a and the ``numerical_aperture`` NA. Above λc the fiber is single-mode;
    below it a second mode appears and it goes multimode. It is the number a fiber is specified by —
    a link must operate above its fiber's cutoff to stay single-mode. Returns the cutoff wavelength
    in metres.
    """
    _check(core_radius, "[length]", "core_radius")
    a = core_radius.to("m").magnitude
    if a <= 0:
        raise ValueError("core_radius must be positive")
    if numerical_aperture <= 0:
        raise ValueError("numerical_aperture must be positive")
    return Quantity(magnitude=2.0 * pi * a * numerical_aperture / _SINGLE_MODE_CUTOFF_V, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
