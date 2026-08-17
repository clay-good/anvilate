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
from math import asin, degrees, log, log10, pi, sqrt

from ..units import Quantity

__all__ = [
    "eyring_reverberation_time",
    "acoustic_impedance",
    "acoustic_reflection_coefficient",
    "acoustic_transmission_coefficient",
    "beat_frequency",
    "closed_pipe_resonance_frequency",
    "doppler_shifted_frequency",
    "doppler_velocity_from_shift",
    "helmholtz_resonator_frequency",
    "inverse_square_attenuation",
    "mach_cone_angle",
    "coincidence_critical_frequency",
    "composite_transmission_loss",
    "mass_law_transmission_loss",
    "room_constant",
    "critical_distance",
    "room_sound_pressure_level",
    "noise_dose_fraction",
    "open_pipe_resonance_frequency",
    "permissible_exposure_time",
    "sabine_reverberation_time",
    "schroeder_frequency",
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


def composite_transmission_loss(
    *,
    areas: Sequence[Quantity],
    transmission_losses: Sequence[float],
) -> float:
    """The transmission loss of a partition made of several elements, weighted by area.

    :func:`mass_law_transmission_loss` describes one uniform leaf. Real partitions have a door, a
    window, a duct penetration — and sound leaks through the weakest element far out of
    proportion to its area, because the elements combine by *transmitted energy*, not by their
    decibel ratings:

        TL_c = 10·log₁₀( ΣSᵢ / Σ(Sᵢ·10^(−TLᵢ/10)) )

    This is the single most common mistake in noise-control layout. An 18 m² wall rated 50 dB with
    2 m² of 25 dB glazing — a tenth of the area — delivers **34.9 dB**, not 50: the glazing passes
    about 30 times the energy the wall does. Worse, a small hole is effectively TL = 0: a 1% open
    gap caps the whole partition near 20 dB no matter what the wall is made of. The practical rule
    falls straight out of the formula — improving the *best* element buys nothing until the worst
    one is fixed.

    ``areas`` and ``transmission_losses`` are parallel sequences of equal length: each element's
    area as a Quantity and its transmission loss in dB. Returns the composite TL in dB as a plain
    float.
    """
    if len(areas) != len(transmission_losses):
        raise ValueError(
            f"areas and transmission_losses must be the same length; got {len(areas)} and "
            f"{len(transmission_losses)}"
        )
    if len(areas) == 0:
        raise ValueError("areas must contain at least one element")
    total_area = 0.0
    transmitted = 0.0
    for area, loss in zip(areas, transmission_losses, strict=True):
        _check(area, "[area]", "areas entry")
        square_metres = area.to("m**2").magnitude
        if square_metres <= 0:
            raise ValueError(f"each area must be positive; got {area}")
        if loss < 0:
            raise ValueError(f"each transmission loss must be non-negative; got {loss} dB")
        total_area += square_metres
        transmitted += square_metres * 10.0 ** (-loss / 10.0)
    return 10.0 * log10(total_area / transmitted)


def coincidence_critical_frequency(
    *,
    thickness: Quantity,
    density: Quantity,
    youngs_modulus: Quantity,
    poissons_ratio: float,
    sound_speed: Quantity | None = None,
) -> Quantity:
    """The coincidence critical frequency, f_c = (c²/2π)·√(m″/D).

    :func:`mass_law_transmission_loss` says in its own docstring that real partitions dip at their
    coincidence frequency, and then gives no way to find it. This does.

    Above f_c the bending wavelength in the panel can match the trace wavelength of sound arriving
    at some angle. When they coincide the panel couples to the air almost perfectly and radiates
    the sound straight through, so the transmission loss collapses 10–15 dB below the mass law in
    a band around f_c. The frequency follows from the surface density m″ = ρ·t and the bending
    stiffness D = E·t³/(12(1−ν²)) — note the stiffness rises as t³ while the mass rises as t, so a
    *thicker* panel of the same material has a *lower* critical frequency.

    That inverse dependence is the design lever and the trap. 6 mm float glass dips at 1993 Hz and
    12.7 mm gypsum board at 2578 Hz — both squarely in the speech band, which is why a window or a
    stud wall measured in the field underperforms the mass law exactly where it matters most. The
    fix is a thinner leaf, a limp one, or two dissimilar leaves so the dips do not align.

    ``sound_speed`` in air defaults to 343 m/s. Returns the critical frequency in Hz.
    """
    _check(thickness, "[length]", "thickness")
    _check(density, "[mass]/[length]**3", "density")
    _check(youngs_modulus, "[pressure]", "youngs_modulus")
    t_m = thickness.to("m").magnitude
    rho = density.to("kg/m**3").magnitude
    e_pa = youngs_modulus.to("Pa").magnitude
    if t_m <= 0:
        raise ValueError(f"thickness must be positive; got {thickness}")
    if rho <= 0:
        raise ValueError(f"density must be positive; got {density}")
    if e_pa <= 0:
        raise ValueError(f"youngs_modulus must be positive; got {youngs_modulus}")
    if not -1.0 < poissons_ratio < 0.5:
        raise ValueError(f"poissons_ratio must lie in (-1, 0.5); got {poissons_ratio}")
    if sound_speed is None:
        c = 343.0
    else:
        _check(sound_speed, "[length]/[time]", "sound_speed")
        c = sound_speed.to("m/s").magnitude
        if c <= 0:
            raise ValueError(f"sound_speed must be positive; got {sound_speed}")
    surface_density = rho * t_m
    bending_stiffness = e_pa * t_m**3 / (12.0 * (1.0 - poissons_ratio**2))
    return Quantity(
        magnitude=c * c / (2.0 * pi) * sqrt(surface_density / bending_stiffness), unit="Hz"
    )


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


def schroeder_frequency(*, reverberation_time: Quantity, room_volume: Quantity) -> Quantity:
    """The Schroeder (crossover) frequency of a room, f_s = 2000·√(T₆₀/V).

    The frequency that divides a room's two acoustic regimes: f_s = 2000·√(T₆₀/V), from the
    ``reverberation_time`` T₆₀ (see :func:`sabine_reverberation_time`) and the ``room_volume`` V.
    Below f_s the room's individual standing-wave modes are sparse and stand apart, so the response
    is lumpy and dominated by discrete resonances (the domain of bass traps and speaker/listener
    placement); above it the modes overlap three or more to a bandwidth and merge into the
    statistical, diffuse field that Sabine's equation assumes (the domain of broadband absorption).
    A small, live room pushes f_s high — into the hundreds of hertz — leaving most of the bass
    modal; a large hall drops it below the audible range. The 2000 constant is metric (T₆₀ in
    seconds, V in m³). Returns the crossover frequency in hertz.
    """
    _check(reverberation_time, "[time]", "reverberation_time")
    _check(room_volume, "[length]**3", "room_volume")
    t60 = reverberation_time.to("s").magnitude
    v = room_volume.to("m**3").magnitude
    if t60 <= 0:
        raise ValueError("reverberation_time must be positive")
    if v <= 0:
        raise ValueError("room_volume must be positive")
    return Quantity(magnitude=2000.0 * sqrt(t60 / v), unit="Hz")


def room_constant(
    *, total_surface_area: Quantity, average_absorption_coefficient: float
) -> Quantity:
    """The room constant, R = S·ᾱ/(1 − ᾱ).

    The measure of how much a room soaks up its own reverberant sound: R = ``total_surface_area`` S
    · ``average_absorption_coefficient`` ᾱ / (1 − ᾱ). A live, hard room (small ᾱ) has a small R and
    a strong reverberant field; a dead, absorptive room has a large R. It sets the steady reverb
    level a source builds up and, with the source directivity, the critical distance (see
    :func:`critical_distance`). ᾱ must lie in (0, 1). Returns the room constant in m² (sabins).
    """
    _check(total_surface_area, "[length]**2", "total_surface_area")
    s = total_surface_area.to("m**2").magnitude
    if s <= 0:
        raise ValueError("total_surface_area must be positive")
    if not 0.0 < average_absorption_coefficient < 1.0:
        raise ValueError("average_absorption_coefficient must be in (0, 1)")
    a_bar = average_absorption_coefficient
    return Quantity(magnitude=s * a_bar / (1.0 - a_bar), unit="m**2")


def critical_distance(*, room_constant: Quantity, directivity_factor: float = 1.0) -> Quantity:
    """The critical (reverberation) distance, d_c = 0.141·√(Q·R).

    The distance from a source at which the direct sound and the reverberant field are equal:
    d_c = 0.141·√(``directivity_factor`` Q · ``room_constant`` R). Closer than d_c the direct sound
    dominates (move the listener or talker in and the level rises with 1/r); beyond it the room's
    reverberant field takes over and the level flattens out — so a PA loudspeaker or a machine's
    noise stops getting quieter with distance past d_c. Q is 1 for an omnidirectional source, 2 near
    a wall, 4 in a corner. Returns the critical distance in metres.
    """
    _check(room_constant, "[length]**2", "room_constant")
    r = room_constant.to("m**2").magnitude
    if r <= 0:
        raise ValueError("room_constant must be positive")
    if directivity_factor <= 0:
        raise ValueError("directivity_factor must be positive")
    return Quantity(magnitude=0.141 * (directivity_factor * r) ** 0.5, unit="m")


def room_sound_pressure_level(
    *,
    sound_power_level: float,
    room_constant: Quantity,
    distance: Quantity,
    directivity_factor: float = 1.0,
) -> float:
    """The room sound-pressure level from a source, L_p = L_W + 10·log₁₀(Q/(4π·r²) + 4/R).

    The steady sound level at a point in an enclosed room, adding the direct field that falls off as
    1/r² to the diffuse reverberant field the room builds up: L_p = ``sound_power_level`` L_W +
    10·log₁₀(Q/(4π·r²) + 4/R), from the source's ``directivity_factor`` Q, the ``distance`` r to the
    listener, and the ``room_constant`` R (:func:`room_constant`). Close to the source (r < the
    :func:`critical_distance`) the first term dominates and the level drops with distance; far out
    the 4/R reverberant term flattens it, so a noisy machine in a live room stays loud everywhere.
    It is the core prediction of industrial-noise and room-acoustics design. ``sound_power_level``
    is a dB level; Q is 1 (free), 2 (wall), 4 (corner). Returns the sound-pressure level in dB.
    """
    _check(room_constant, "[length]**2", "room_constant")
    _check(distance, "[length]", "distance")
    r_const = room_constant.to("m**2").magnitude
    r = distance.to("m").magnitude
    if r_const <= 0:
        raise ValueError("room_constant must be positive")
    if r <= 0:
        raise ValueError("distance must be positive")
    if directivity_factor <= 0:
        raise ValueError("directivity_factor must be positive")
    field = directivity_factor / (4.0 * pi * r**2) + 4.0 / r_const
    return sound_power_level + 10.0 * log10(field)


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
    Returns the permissible exposure time in hours (call ``.to("minute")`` for the short
    allowances a high level gives).
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


def doppler_shifted_frequency(
    *,
    source_frequency: Quantity,
    speed_of_sound: Quantity,
    source_velocity: Quantity,
    observer_velocity: Quantity,
) -> Quantity:
    """The Doppler-shifted frequency, f' = f·(c + v_o)/(c − v_s).

    The frequency a moving observer hears from a moving source: from the ``source_frequency`` f, the
    ``speed_of_sound`` c, the ``source_velocity`` v_s, and the ``observer_velocity`` v_o (each taken
    positive when that party moves *toward* the other), f' = f·(c + v_o)/(c − v_s). Closing the gap
    raises the pitch, opening it lowers it — the up-then-down of a passing siren. The source speed
    must stay below the speed of sound. Returns the observed frequency in Hz.
    """
    _check(source_frequency, "1/[time]", "source_frequency")
    _check(speed_of_sound, "[length]/[time]", "speed_of_sound")
    _check(source_velocity, "[length]/[time]", "source_velocity")
    _check(observer_velocity, "[length]/[time]", "observer_velocity")
    f = source_frequency.to("Hz").magnitude
    c = speed_of_sound.to("m/s").magnitude
    v_s = source_velocity.to("m/s").magnitude
    v_o = observer_velocity.to("m/s").magnitude
    if f <= 0:
        raise ValueError("source_frequency must be positive")
    if c <= 0:
        raise ValueError("speed_of_sound must be positive")
    if v_s >= c:
        raise ValueError("source_velocity must be below the speed of sound")
    if v_o <= -c:
        raise ValueError("observer_velocity must exceed minus the speed of sound")
    return Quantity(magnitude=f * (c + v_o) / (c - v_s), unit="Hz")


def doppler_velocity_from_shift(
    *, source_frequency: Quantity, observed_frequency: Quantity, speed_of_sound: Quantity
) -> Quantity:
    """The source speed from a Doppler shift, v_s = c·(f' − f)/f'.

    Inverting the Doppler relation (:func:`doppler_shifted_frequency`) for a stationary observer:
    the speed at which a source approaches, recovered from the ``source_frequency`` f it emits, the
    ``observed_frequency`` f' measured, and the ``speed_of_sound`` c, v_s = c·(f' − f)/f'. A shift
    up (f' > f) gives a positive closing speed; a shift down, a negative (receding) one. It is how
    Doppler radar, sonar, and acoustic tachometry turn a frequency into a target's velocity. Returns
    the source velocity in m/s (positive when approaching).
    """
    _check(source_frequency, "1/[time]", "source_frequency")
    _check(observed_frequency, "1/[time]", "observed_frequency")
    _check(speed_of_sound, "[length]/[time]", "speed_of_sound")
    f = source_frequency.to("Hz").magnitude
    f_obs = observed_frequency.to("Hz").magnitude
    c = speed_of_sound.to("m/s").magnitude
    if f <= 0:
        raise ValueError("source_frequency must be positive")
    if f_obs <= 0:
        raise ValueError("observed_frequency must be positive")
    if c <= 0:
        raise ValueError("speed_of_sound must be positive")
    return Quantity(magnitude=c * (f_obs - f) / f_obs, unit="m/s")


def beat_frequency(*, frequency_1: Quantity, frequency_2: Quantity) -> Quantity:
    """The beat frequency, f_beat = |f₁ − f₂|.

    When two tones of nearly equal pitch sound together their amplitude swells and fades at the
    difference of their frequencies: from ``frequency_1`` f₁ and ``frequency_2`` f₂,
    f_beat = |f₁ − f₂|. It is the throb a musician nulls to zero when tuning one string against
    another, and the same difference-frequency a heterodyne receiver mixes down to. Returns the beat
    frequency in Hz.
    """
    _check(frequency_1, "1/[time]", "frequency_1")
    _check(frequency_2, "1/[time]", "frequency_2")
    f1 = frequency_1.to("Hz").magnitude
    f2 = frequency_2.to("Hz").magnitude
    if f1 <= 0 or f2 <= 0:
        raise ValueError("frequencies must be positive")
    return Quantity(magnitude=abs(f1 - f2), unit="Hz")


def mach_cone_angle(*, mach_number: float) -> float:
    """The Mach cone half-angle, μ = arcsin(1/M).

    The half-angle of the shock cone a supersonic source drags behind it: from the ``mach_number`` M
    (which must exceed 1), μ = arcsin(1/M). The pressure disturbances a subsonic source makes outrun
    it, but a supersonic one leaves them behind on a cone whose angle narrows as it goes faster —
    the Mach cone that trails a bullet or an airplane and arrives as the crack of a sonic boom.
    Returns the cone half-angle in degrees.
    """
    if mach_number <= 1.0:
        raise ValueError(f"mach_number must exceed 1 (a Mach cone needs M > 1); got {mach_number}")
    return degrees(asin(1.0 / mach_number))


def acoustic_impedance(*, density: Quantity, wave_speed: Quantity) -> Quantity:
    """The characteristic acoustic impedance, Z = ρ·c.

    The resistance a medium offers to a sound wave: its ``density`` ρ times the ``wave_speed`` c,
    Z = ρ·c. It is what governs how sound reflects and transmits at a boundary — a large impedance
    mismatch (as between tissue and air) bounces almost all the sound back, which is why ultrasound
    needs a coupling gel. Water is ~1.48 MRayl, steel ~46 MRayl. Feed two of these to
    :func:`acoustic_reflection_coefficient`. Returns the impedance in kg/(m²·s) (the Rayl).
    """
    _check(density, "[mass]/[length]**3", "density")
    _check(wave_speed, "[length]/[time]", "wave_speed")
    rho = density.to("kg/m**3").magnitude
    c = wave_speed.to("m/s").magnitude
    if rho <= 0:
        raise ValueError("density must be positive")
    if c <= 0:
        raise ValueError("wave_speed must be positive")
    return Quantity(magnitude=rho * c, unit="kg/(m**2*s)")


def acoustic_reflection_coefficient(*, impedance_1: Quantity, impedance_2: Quantity) -> float:
    """The acoustic intensity reflection coefficient, R = ((Z₂ − Z₁)/(Z₂ + Z₁))².

    The fraction of a sound wave's intensity reflected at a normal-incidence boundary between two
    media of acoustic impedance ``impedance_1`` Z₁ and ``impedance_2`` Z₂ (from
    :func:`acoustic_impedance`): R = ((Z₂ − Z₁)/(Z₂ + Z₁))². Matched impedances (Z₁ = Z₂) reflect
    nothing and pass the wave through; a large mismatch reflects nearly all of it — the physics an
    ultrasonic flaw detector uses to see a crack (a steel-to-air interface) as a bright echo.
    Returns the dimensionless reflection coefficient (0 to 1) as a plain float.
    """
    _check(impedance_1, "[mass]/([length]**2*[time])", "impedance_1")
    _check(impedance_2, "[mass]/([length]**2*[time])", "impedance_2")
    z1 = impedance_1.to("kg/(m**2*s)").magnitude
    z2 = impedance_2.to("kg/(m**2*s)").magnitude
    if z1 <= 0 or z2 <= 0:
        raise ValueError("acoustic impedances must be positive")
    return ((z2 - z1) / (z2 + z1)) ** 2


def acoustic_transmission_coefficient(*, impedance_1: Quantity, impedance_2: Quantity) -> float:
    """The acoustic intensity transmission coefficient, T = 4·Z₁·Z₂/(Z₁ + Z₂)².

    The fraction of a sound wave's intensity transmitted across a normal-incidence boundary between
    media of acoustic impedance ``impedance_1`` Z₁ and ``impedance_2`` Z₂: T = 4·Z₁·Z₂/(Z₁ + Z₂)²,
    the complement of the reflection coefficient (T + R = 1, see
    :func:`acoustic_reflection_coefficient`). It peaks at 1 for matched impedances and collapses for
    a large mismatch — the reason a thin matching layer is bonded to an ultrasonic transducer to
    couple it to the part. Returns the dimensionless transmission coefficient (0 to 1) as a plain
    float.
    """
    _check(impedance_1, "[mass]/([length]**2*[time])", "impedance_1")
    _check(impedance_2, "[mass]/([length]**2*[time])", "impedance_2")
    z1 = impedance_1.to("kg/(m**2*s)").magnitude
    z2 = impedance_2.to("kg/(m**2*s)").magnitude
    if z1 <= 0 or z2 <= 0:
        raise ValueError("acoustic impedances must be positive")
    return 4.0 * z1 * z2 / (z1 + z2) ** 2


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def eyring_reverberation_time(
    *, volume: Quantity, total_surface_area: Quantity, average_absorption_coefficient: float
) -> Quantity:
    """The Eyring reverberation time, T₆₀ = 0.161·V/(−S·ln(1 − ᾱ)).

    The time for sound to decay 60 dB in a room, computed the way that stays honest when the room
    is absorptive. :func:`sabine_reverberation_time` is the module's only reverberation model and
    it assumes each reflection removes a small fraction of the energy — fine in a live hall, badly
    wrong in a treated one.

    Eyring replaces Sabine's ᾱ with −ln(1 − ᾱ), the exact per-reflection energy loss, using the
    ``volume`` V, the ``total_surface_area`` S, and the ``average_absorption_coefficient`` ᾱ.
    The two converge as ᾱ → 0, since −ln(1 − ᾱ) → ᾱ, so this is a strict generalisation rather
    than a competing model.

    The divergence is large exactly where it matters: Sabine over-predicts by 39% at ᾱ = 0.50 and
    by 101% at ᾱ = 0.80, and it never reaches zero even at ᾱ = 1 — it would have an anechoic
    chamber ringing for a fifth of a second. Anyone sizing absorption for a studio, a control
    room, or a lined plant room is in that regime, and Sabine tells them they are finished when
    they are not. ᾱ is the area-weighted mean over all surfaces, in (0, 1). Returns the
    reverberation time in s.
    """
    _check(volume, "[volume]", "volume")
    _check(total_surface_area, "[area]", "total_surface_area")
    if not 0.0 < average_absorption_coefficient < 1.0:
        raise ValueError(
            "average_absorption_coefficient must lie in (0, 1); got "
            f"{average_absorption_coefficient}"
        )
    v = volume.to("m**3").magnitude
    s = total_surface_area.to("m**2").magnitude
    if v <= 0:
        raise ValueError("volume must be positive")
    if s <= 0:
        raise ValueError("total_surface_area must be positive")
    return Quantity(
        magnitude=0.161 * v / (-s * log(1.0 - average_absorption_coefficient)), unit="s"
    )
