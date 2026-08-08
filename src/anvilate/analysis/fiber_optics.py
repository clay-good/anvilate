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

from ..units import Quantity

__all__ = [
    "chromatic_dispersion_broadening",
    "dispersion_limited_bit_rate",
    "dispersion_limited_distance",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
