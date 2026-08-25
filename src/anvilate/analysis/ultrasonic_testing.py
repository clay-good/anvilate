"""T1 analytical ultrasonic non-destructive-testing checks (closed-form).

An ultrasonic flaw detector sends a short pulse into a part and listens for echoes off the back wall
and any internal defects. Three bits of geometry govern where it can see and how well: the
near-field length over which the beam is a chaotic mess of interference before it settles, the angle
at which it then spreads, and the depth an echo's round-trip time implies. These are the
transducer-and-timing companions to the acoustic impedance and reflection of
:mod:`anvilate.analysis.acoustics` (which set how much of the pulse an interface returns).

A flat circular probe of diameter D at frequency f radiates a wavelength λ = c/f into a material of
sound speed c. Out to the near-field length N = D²·f/(4·c) the beam is collimated but its on-axis
pressure oscillates wildly, so flaws there cannot be sized reliably — the usable range starts beyond
N. Past it the beam opens into a cone of half-angle θ = arcsin(1.22·c/(f·D)), the same diffraction
spread as an optical aperture. And a defect or back wall at depth d returns an echo after a
round-trip time t, so the pulse-echo depth is d = c·t/2. Diameters, frequencies, speeds, and times
are dimension-checked :class:`~anvilate.units.Quantity` values; the divergence angle is a plain
float in degrees.

Sources: Krautkramer & Krautkramer, *Ultrasonic Testing of Materials* — the near-field length N
= D²/(4·lambda) that bounds where an amplitude reading means anything, the far-field beam
divergence, and the thickness a pulse-echo transit time gives.
"""

from __future__ import annotations

from math import asin, degrees

from ..units import Quantity
from ..units.rotation import count_rate_per_second

__all__ = [
    "near_field_length",
    "ultrasonic_beam_divergence",
    "pulse_echo_thickness",
]


def near_field_length(
    *, transducer_diameter: Quantity, frequency: Quantity, sound_speed: Quantity
) -> Quantity:
    """The ultrasonic near-field (Fresnel) length, N = D²·f/(4·c).

    The distance over which a flat circular probe's beam stays collimated but its on-axis pressure
    swings through a series of maxima and minima — the messy zone where a flaw's echo amplitude is
    unreliable, so testing is done *beyond* it. From the ``transducer_diameter`` D, the probe
    ``frequency`` f, and the material ``sound_speed`` c, N = D²·f/(4·c) (= D²/(4·λ)). A bigger or
    higher-frequency probe pushes the near field deeper, moving the last on-axis maximum — the
    natural focus — out with it. Returns the near-field length in metres.
    """
    _check(transducer_diameter, "[length]", "transducer_diameter")
    _check(frequency, "1/[time]", "frequency")
    _check(sound_speed, "[velocity]", "sound_speed")
    d = transducer_diameter.to("m").magnitude
    f = count_rate_per_second(frequency, name="frequency")
    c = sound_speed.to("m/s").magnitude
    if d <= 0:
        raise ValueError("transducer_diameter must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    if c <= 0:
        raise ValueError("sound_speed must be positive")
    return Quantity(magnitude=d**2 * f / (4.0 * c), unit="m")


def ultrasonic_beam_divergence(
    *, transducer_diameter: Quantity, frequency: Quantity, sound_speed: Quantity
) -> float:
    """The ultrasonic far-field beam divergence half-angle, θ = arcsin(1.22·c/(f·D)).

    Beyond the near field (:func:`near_field_length`) the beam opens into a cone whose half-angle to
    the first null is θ = arcsin(1.22·c/(f·D)) — the same diffraction spread a circular optical
    aperture makes — from the material ``sound_speed`` c, the probe ``frequency`` f, and the
    ``transducer_diameter`` D. A bigger or higher-frequency probe makes a tighter, more directional
    beam; a small low-frequency one sprays wide. It sets how the beam widens with depth and thus the
    lateral resolution far out. Requires 1.22·c/(f·D) ≤ 1 (otherwise the beam is not directional).
    Returns the divergence half-angle in degrees.
    """
    _check(transducer_diameter, "[length]", "transducer_diameter")
    _check(frequency, "1/[time]", "frequency")
    _check(sound_speed, "[velocity]", "sound_speed")
    d = transducer_diameter.to("m").magnitude
    f = count_rate_per_second(frequency, name="frequency")
    c = sound_speed.to("m/s").magnitude
    if d <= 0:
        raise ValueError("transducer_diameter must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    if c <= 0:
        raise ValueError("sound_speed must be positive")
    ratio = 1.22 * c / (f * d)
    if ratio > 1.0:
        raise ValueError(
            "beam is not directional: 1.22*c/(f*D) exceeds 1 (the wavelength is too large for "
            "the probe)"
        )
    return degrees(asin(ratio))


def pulse_echo_thickness(*, time_of_flight: Quantity, sound_speed: Quantity) -> Quantity:
    """The pulse-echo depth to a reflector, d = c·t/2.

    The depth of a back wall or defect from the round-trip travel time of its echo: the pulse covers
    twice the depth (down and back) at the material ``sound_speed`` c, so d = c·t/2 for the
    round-trip ``time_of_flight`` t. It is the basis of ultrasonic thickness gauging (remaining wall
    against corrosion) and of flaw-depth sizing — the number a detector converts each echo into.
    Returns the depth in metres.
    """
    _check(time_of_flight, "[time]", "time_of_flight")
    _check(sound_speed, "[velocity]", "sound_speed")
    t = time_of_flight.to("s").magnitude
    c = sound_speed.to("m/s").magnitude
    if t <= 0:
        raise ValueError("time_of_flight must be positive")
    if c <= 0:
        raise ValueError("sound_speed must be positive")
    return Quantity(magnitude=c * t / 2.0, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
