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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.rotation import count_rate_per_second

_FREQUENCY_SOURCE = "the source's frequency specification or calibrated frequency measurement"
_WAVELENGTH_SOURCE = "the measured or specified wavelength"
_MEDIUM_SOURCE = "the cited wave speed for the propagation medium and wave type"


class _WaveInputError(RefusalError, ValueError):
    """A wave-relation input that cannot be used without correction."""


def _wave_refusal(message: str, *, subject: str, source: str) -> _WaveInputError:
    return _WaveInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _wave_input_source(name: str) -> str:
    if name == "frequency":
        return _FREQUENCY_SOURCE
    if name == "wavelength":
        return _WAVELENGTH_SOURCE
    return _MEDIUM_SOURCE


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
        raise _wave_refusal(
            "frequency must be positive", subject="frequency", source=_FREQUENCY_SOURCE
        )
    if lam <= 0:
        raise _wave_refusal(
            "wavelength must be positive", subject="wavelength", source=_WAVELENGTH_SOURCE
        )
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
        raise _wave_refusal(
            "frequency must be positive", subject="frequency", source=_FREQUENCY_SOURCE
        )
    if v <= 0:
        raise _wave_refusal(
            "wave_speed must be positive", subject="wave_speed", source=_MEDIUM_SOURCE
        )
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
        raise _wave_refusal(
            "wavelength must be positive", subject="wavelength", source=_WAVELENGTH_SOURCE
        )
    if v <= 0:
        raise _wave_refusal(
            "wave_speed must be positive", subject="wave_speed", source=_MEDIUM_SOURCE
        )
    return Quantity(magnitude=v / lam, unit="Hz")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _wave_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_wave_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _wave_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_wave_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
