"""T1 analytical acoustics checks (sound-level arithmetic, closed-form).

Industrial and plant engineers assess machinery noise for hearing conservation and equipment
specifications, and two relations do most of the work — both of which trip up intuition because
sound levels are logarithmic.

Sound levels do not add arithmetically: because the decibel is a log scale, combining sources means
summing their *energies* and converting back, L_total = 10·log₁₀(Σ 10^(Lᵢ/10)). Two equal sources
are only 3 dB louder than one, not double; a source 10 dB below another adds almost nothing.

A point source in the open loses level with distance by the inverse-square law, which in decibels is
L₂ = L₁ − 20·log₁₀(r₂/r₁) — a clean 6 dB drop for every doubling of distance. Levels are plain
decibel numbers (a dimensionless ratio); distances are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log10, pi, sqrt

from ..units import Quantity

__all__ = [
    "closed_pipe_resonance_frequency",
    "helmholtz_resonator_frequency",
    "inverse_square_attenuation",
    "mass_law_transmission_loss",
    "noise_dose_fraction",
    "open_pipe_resonance_frequency",
    "permissible_exposure_time",
    "sabine_reverberation_time",
    "sound_level_sum",
    "sound_power_level_from_intensity",
    "sound_pressure_from_power_level",
]


def sound_level_sum(*, levels: Sequence[float]) -> float:
    """The combined sound level of several incoherent sources, L = 10·log₁₀(Σ 10^(Lᵢ/10)).

    Decibels are logarithmic, so noise sources add by energy, not arithmetic: L = 10·log₁₀(Σ
    10^(Lᵢ/10)). ``levels`` is the sequence of individual sound levels in dB. Two equal sources come
    out only 3 dB above one, and a source more than ~10 dB below the loudest barely moves the
    total — which is why quieting the single loudest machine is what actually lowers a plant's
    noise. Returns the combined level in dB.
    """
    if not levels:
        raise ValueError("levels must contain at least one sound level")
    total = sum(10.0 ** (level / 10.0) for level in levels)
    return 10.0 * log10(total)


def inverse_square_attenuation(
    *,
    reference_level: float,
    reference_distance: Quantity,
    distance: Quantity,
) -> float:
    """The sound level at a distance from a point source, L₂ = L₁ − 20·log₁₀(r₂/r₁).

    A point source radiating into the open spreads its energy over an expanding sphere, so its level
    falls by the inverse-square law — 6 dB for every doubling of distance:
    L₂ = L₁ − 20·log₁₀(r₂/r₁). ``reference_level`` L₁ is the level (dB) measured at
    ``reference_distance`` r₁, and ``distance``
    r₂ is where you want the level. Valid in a free field (no reflecting surfaces or reverberation).
    Returns the sound level at r₂ in dB.
    """
    _check(reference_distance, "[length]", "reference_distance")
    _check(distance, "[length]", "distance")
    r1 = reference_distance.to("m").magnitude
    r2 = distance.to("m").magnitude
    if r1 <= 0 or r2 <= 0:
        raise ValueError("reference_distance and distance must be positive")
    return reference_level - 20.0 * log10(r2 / r1)


def mass_law_transmission_loss(*, frequency: Quantity, surface_density: Quantity) -> float:
    """The sound transmission loss of a single partition by the mass law, TL = 20·log₁₀(f·m) − 47.

    How much a wall or panel cuts airborne sound depends mostly on how heavy it is: the field-
    incidence mass law gives TL = 20·log₁₀(f·m_s) − 47 dB, from the ``frequency`` f (Hz) and the
    partition's ``surface_density`` m_s (mass per unit area, kg/m²). The two big consequences are
    baked in: the loss rises 6 dB for every doubling of frequency (partitions insulate treble far
    better than bass) and 6 dB for every doubling of mass (to quiet a wall, make it heavier). It is
    an idealization — real partitions dip at their coincidence and resonance frequencies — but it is
    the first number a noise-control layout works from. Returns the transmission loss in dB.
    """
    _check(frequency, "1/[time]", "frequency")
    _check(surface_density, "[mass]/[length]**2", "surface_density")
    f = frequency.to("Hz").magnitude
    m_s = surface_density.to("kg/m**2").magnitude
    if f <= 0 or m_s <= 0:
        raise ValueError("frequency and surface_density must be positive")
    return 20.0 * log10(f * m_s) - 47.0


def sabine_reverberation_time(*, volume: Quantity, total_absorption: Quantity) -> Quantity:
    """The reverberation time of a room by Sabine's equation, T₆₀ = 0.161·V/A.

    How long sound lingers after a source stops is set by how big the room is against how much its
    surfaces soak up: T₆₀ = 0.161·V/A, where ``volume`` V is the room volume (m³) and
    ``total_absorption`` A is the summed absorption Σ Sᵢ·αᵢ — each surface's area times its
    absorption coefficient — in sabins (m²). The 0.161 s/m constant is metric. A hard, empty plant
    room (little absorption) rings for seconds and pumps up the reverberant field a worker stands
    in; adding absorption is the lever that shortens it. Sabine assumes a diffuse field and fairly
    even absorption. Returns the reverberation time (the 60 dB decay) as a time Quantity.
    """
    _check(volume, "[length]**3", "volume")
    _check(total_absorption, "[length]**2", "total_absorption")
    v = volume.to("m**3").magnitude
    a = total_absorption.to("m**2").magnitude
    if v <= 0 or a <= 0:
        raise ValueError("volume and total_absorption must be positive")
    return Quantity(magnitude=0.161 * v / a, unit="s")


def permissible_exposure_time(
    *,
    sound_level: float,
    criterion_level: float,
    exchange_rate: float,
    criterion_duration: Quantity,
) -> Quantity:
    """The time a steady noise level may be endured, T = T₀ / 2^((L − L_c)/q).

    Hearing-conservation standards trade level against time on a fixed exchange rate: every ``q`` dB
    (the ``exchange_rate``) above the ``criterion_level`` L_c halves the permissible time. Starting
    from the reference exposure — ``criterion_duration`` T₀ (the shift the criterion level is set
    for, typically 8 h) — the time a worker may spend at ``sound_level`` L is
    T = T₀ / 2^((L − L_c)/q). The criterion level and exchange rate are the standard's own values,
    supplied by the caller: OSHA uses L_c = 90 dBA with q = 5 dB, NIOSH L_c = 85 dBA with q = 3 dB.
    Returns the permissible exposure time as a Quantity in the units of the criterion duration.
    """
    _check(criterion_duration, "[time]", "criterion_duration")
    if exchange_rate <= 0:
        raise ValueError("exchange_rate (dB) must be positive")
    t0 = criterion_duration.to("hour").magnitude
    if t0 <= 0:
        raise ValueError("criterion_duration must be positive")
    t = t0 / 2.0 ** ((sound_level - criterion_level) / exchange_rate)
    return Quantity(magnitude=t, unit="hour")


def noise_dose_fraction(*, exposure_time: Quantity, permissible_time: Quantity) -> float:
    """The noise dose a single exposure accrues, D = C/T (1.0 is the full permissible dose).

    A worker's dose is the time actually spent at a level, ``exposure_time`` C, over the permissible
    time at that level, ``permissible_time`` T (from :func:`permissible_exposure_time`): D = C/T. A
    dose of 1.0 means the worker has reached the standard's limit for the shift; above 1.0 the
    permissible exposure has been exceeded. (For several different levels across a shift the total
    dose is the sum of each interval's C/T — combine the fractions this returns.) Returns the dose
    as a dimensionless fraction; multiply by 100 for the percent dose the standards report.
    """
    _check(exposure_time, "[time]", "exposure_time")
    _check(permissible_time, "[time]", "permissible_time")
    c = exposure_time.to("hour").magnitude
    t = permissible_time.to("hour").magnitude
    if c < 0:
        raise ValueError("exposure_time must be non-negative")
    if t <= 0:
        raise ValueError("permissible_time must be positive")
    return c / t


def sound_power_level_from_intensity(
    *,
    intensity_level: float,
    measurement_area: Quantity,
) -> float:
    """The sound power level of a source from a measured intensity, L_w = L_I + 10·log₁₀(S/S₀).

    The intensity method of sound-power determination (ISO 9614): scanning a sound-intensity probe
    over a surface enclosing the source gives the average ``intensity_level`` L_I (dB re 1 pW/m²),
    and the total power radiated through that surface is L_w = L_I + 10·log₁₀(S/S₀), from the
    ``measurement_area`` S (S₀ = 1 m²). Unlike a pressure measurement, intensity rejects steady
    background noise, so this works on a noisy plant floor without an anechoic room. Over a 1 m²
    surface L_w equals L_I. Returns the sound power level in dB.
    """
    _check(measurement_area, "[length]**2", "measurement_area")
    s = measurement_area.to("m**2").magnitude
    if s <= 0:
        raise ValueError("measurement_area must be positive")
    return intensity_level + 10.0 * log10(s)


def sound_pressure_from_power_level(
    *,
    sound_power_level: float,
    distance: Quantity,
    directivity_factor: float = 2.0,
) -> float:
    """The sound pressure level from a source's power level, L_p = L_w + 10·log₁₀(Q/(4π·r²)).

    A machine is rated by its sound *power* level L_w (a fixed property of the source), but what a
    worker hears is a *pressure* level L_p that falls with distance and depends on where the machine
    sits: L_p = L_w + 10·log₁₀(Q/(4π·r²)), from the ``sound_power_level`` L_w (dB re 1 pW), the
    ``distance`` r, and the ``directivity_factor`` Q — 1 in free space, 2 on a reflecting floor (the
    usual plant case), 4 against a wall, 8 in a corner, each reflection adding 3 dB. In a free field
    at 1 m the pressure level is about L_w − 11 dB. Feed the result to the noise-exposure screen.
    Returns the sound pressure level in dB.
    """
    _check(distance, "[length]", "distance")
    r = distance.to("m").magnitude
    if r <= 0:
        raise ValueError("distance must be positive")
    if directivity_factor <= 0:
        raise ValueError("directivity_factor must be positive")
    return sound_power_level + 10.0 * log10(directivity_factor / (4.0 * pi * r**2))


def helmholtz_resonator_frequency(
    *,
    speed_of_sound: Quantity,
    neck_area: Quantity,
    cavity_volume: Quantity,
    neck_length: Quantity,
) -> Quantity:
    """The Helmholtz resonance, f = (c/2π)·√(A/(V·L)).

    The natural frequency of a cavity-and-neck resonator — the plug of air in the ``neck_area`` A of
    ``neck_length`` L bouncing on the springiness of the ``cavity_volume`` V — from the
    ``speed_of_sound`` c, f = (c/2π)·√(A/(V·L)). It is the tone a blown bottle sounds, the tuning of
    bass-reflex port, and the frequency a Helmholtz muffler or cavity absorber is built to kill.
    Returns the resonant frequency in Hz.
    """
    _check(speed_of_sound, "[length]/[time]", "speed_of_sound")
    _check(neck_area, "[area]", "neck_area")
    _check(cavity_volume, "[volume]", "cavity_volume")
    _check(neck_length, "[length]", "neck_length")
    c = speed_of_sound.to("m/s").magnitude
    a = neck_area.to("m**2").magnitude
    v = cavity_volume.to("m**3").magnitude
    length = neck_length.to("m").magnitude
    if c <= 0:
        raise ValueError("speed_of_sound must be positive")
    if a <= 0:
        raise ValueError("neck_area must be positive")
    if v <= 0:
        raise ValueError("cavity_volume must be positive")
    if length <= 0:
        raise ValueError("neck_length must be positive")
    return Quantity(magnitude=c / (2.0 * pi) * sqrt(a / (v * length)), unit="Hz")


def open_pipe_resonance_frequency(
    *, speed_of_sound: Quantity, pipe_length: Quantity, mode: int = 1
) -> Quantity:
    """The open-pipe resonance, f_n = n·c/(2L).

    The resonant frequencies of a pipe open at both ends (or the acoustic modes between two parallel
    room surfaces): from the ``speed_of_sound`` c, the ``pipe_length`` L, and the harmonic ``mode``
    n, f_n = n·c/(2L). A pipe open at both ends supports all integer harmonics, the full series
    n = 1, 2, 3, …; the fundamental is c/(2L). It is the pitch of a flute or an open organ pipe and
    the axial modes that colour a room. Returns the resonant frequency in Hz.
    """
    _check(speed_of_sound, "[length]/[time]", "speed_of_sound")
    _check(pipe_length, "[length]", "pipe_length")
    c = speed_of_sound.to("m/s").magnitude
    length = pipe_length.to("m").magnitude
    if c <= 0:
        raise ValueError("speed_of_sound must be positive")
    if length <= 0:
        raise ValueError("pipe_length must be positive")
    if not isinstance(mode, int) or mode < 1:
        raise ValueError("mode must be an integer of at least 1")
    return Quantity(magnitude=mode * c / (2.0 * length), unit="Hz")


def closed_pipe_resonance_frequency(
    *, speed_of_sound: Quantity, pipe_length: Quantity, mode: int = 1
) -> Quantity:
    """The closed-pipe resonance, f_n = (2n − 1)·c/(4L).

    The resonant frequencies of a pipe closed at one end and open at the other: from the
    ``speed_of_sound`` c, the ``pipe_length`` L, and the harmonic ``mode`` n, f_n = (2n − 1)·c/(4L).
    A closed pipe fits only a quarter-wave and its odd multiples, so it supports only odd harmonics
    (1, 3, 5, …) and its fundamental c/(4L) is an octave below an open pipe of the same length — the
    reason a stopped organ pipe sounds deep for its size. Returns the resonant frequency in Hz.
    """
    _check(speed_of_sound, "[length]/[time]", "speed_of_sound")
    _check(pipe_length, "[length]", "pipe_length")
    c = speed_of_sound.to("m/s").magnitude
    length = pipe_length.to("m").magnitude
    if c <= 0:
        raise ValueError("speed_of_sound must be positive")
    if length <= 0:
        raise ValueError("pipe_length must be positive")
    if not isinstance(mode, int) or mode < 1:
        raise ValueError("mode must be an integer of at least 1")
    return Quantity(magnitude=(2 * mode - 1) * c / (4.0 * length), unit="Hz")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
