"""T1 analytical wave-relation (v = f·λ) checks (closed-form).

Every travelling wave — sound, light, radio, a ripple on water — obeys the same relation between its
speed, frequency, and wavelength: v = f·λ. Solving it for any one from the other two is the first
step in almost any wave problem, from tuning an antenna to reading a musical note. It is the general
form behind the domain-specific speeds of :mod:`anvilate.analysis.elastic_waves` and
:mod:`anvilate.analysis.acoustics` and the photon wavelength of :mod:`anvilate.analysis.photon`.

For a wave of frequency f and wavelength λ, the propagation speed is v = f·λ. Given the speed of the
medium (the speed of sound in air, the speed of light in vacuum, the speed of a wave on a string),
the wavelength a frequency produces is λ = v/f, and the frequency a wavelength corresponds to is
f = v/λ — shorter wavelengths mean higher frequencies at a fixed speed. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Hecht, *Optics* (wave motion) — the relation v = f·lambda between a wave's speed,
frequency and wavelength, and each of its three rearrangements. It holds for any wave, which is
why the module carries no medium of its own.
"""

from __future__ import annotations

from ..units import Quantity
from ..units.rotation import count_rate_per_second

__all__ = [
    "frequency_from_wavelength",
    "wave_speed",
    "wavelength_from_frequency",
]


def wave_speed(*, frequency: Quantity, wavelength: Quantity) -> Quantity:
    """The wave speed, v = f·λ.

    The propagation speed of a wave of ``frequency`` f and ``wavelength`` λ: v = f·λ. For a fixed
    medium the product is constant, so frequency and wavelength trade off inversely. Returns the
    speed in m/s.
    """
    _check(frequency, "1/[time]", "frequency")
    _check(wavelength, "[length]", "wavelength")
    f = count_rate_per_second(frequency, name="frequency")
    lam = wavelength.to("m").magnitude
    if f <= 0:
        raise ValueError("frequency must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return Quantity(magnitude=f * lam, unit="m/s")


def wavelength_from_frequency(*, frequency: Quantity, wave_speed: Quantity) -> Quantity:
    """The wavelength, λ = v/f.

    The wavelength a ``frequency`` f produces at a given ``wave_speed`` v: λ = v/f. A higher
    frequency packs into a shorter wavelength — a 100 MHz FM signal is 3 m long, a 440 Hz tone about
    0.78 m. Returns the wavelength in m.
    """
    _check(frequency, "1/[time]", "frequency")
    _check(wave_speed, "[velocity]", "wave_speed")
    f = count_rate_per_second(frequency, name="frequency")
    v = wave_speed.to("m/s").magnitude
    if f <= 0:
        raise ValueError("frequency must be positive")
    if v <= 0:
        raise ValueError("wave_speed must be positive")
    return Quantity(magnitude=v / f, unit="m")


def frequency_from_wavelength(*, wavelength: Quantity, wave_speed: Quantity) -> Quantity:
    """The frequency, f = v/λ.

    The frequency a ``wavelength`` λ corresponds to at a given ``wave_speed`` v: f = v/λ — how green
    light at 500 nm works out to about 6×10¹⁴ Hz. Returns the frequency in Hz.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(wave_speed, "[velocity]", "wave_speed")
    lam = wavelength.to("m").magnitude
    v = wave_speed.to("m/s").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if v <= 0:
        raise ValueError("wave_speed must be positive")
    return Quantity(magnitude=v / lam, unit="Hz")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
