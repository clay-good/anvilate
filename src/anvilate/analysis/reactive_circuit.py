"""T1 analytical reactive-component checks (energy storage and LC resonance, closed-form).

Capacitors and inductors store energy in fields rather than dissipate it, and a pair of them
exchange that energy back and forth at a resonant frequency — the relations power-electronics and
filter design lean on.

A capacitor holds E = ½·C·V² in its electric field, from the ``capacitance`` C and the ``voltage`` V
across it — the energy a DC-link or snubber capacitor must absorb, or a flash bank must dump. An
inductor holds E = ½·L·I² in its magnetic field, from the ``inductance`` L and the ``current`` I —
the energy that must go somewhere when a switch opens, which is why inductive circuits need
freewheeling paths.

Put the two together and the energy sloshes between them at the LC resonant frequency
f₀ = 1/(2π·√(L·C)) — the tuning of a filter, the ring of a switching node, the frequency a tank
circuit selects. Paired instead with a resistor, a single reactive element gives a first-order
response with time constant τ = R·C (or L/R) and an RC filter corner at f_c = 1/(2π·R·C).

Before any of that, a capacitor's capacitance comes from its geometry: a parallel-plate capacitor of
area A and gap d has C = ε₀·ε_r·A/d, it holds charge Q = C·V at voltage V, and the field between its
plates is the uniform E = V/d.

Sources: standard AC circuit theory (Nilsson & Riedel, *Electric Circuits*;
Irwin, *Basic Engineering Circuit Analysis*) for reactance, resonance and quality factor.
"""

from __future__ import annotations

from math import exp, pi, sqrt

from ..units import Quantity
from ..units.rotation import count_rate_per_second

_VACUUM_PERMITTIVITY = 8.8541878128e-12  # F/m

__all__ = [
    "capacitive_reactance",
    "capacitor_charge",
    "capacitor_stored_energy",
    "inductive_reactance",
    "inductor_stored_energy",
    "lc_resonant_frequency",
    "parallel_plate_capacitance",
    "parallel_plate_field",
    "capacitance_for_reactance",
    "inductance_for_reactance",
    "first_order_highpass_gain",
    "first_order_lowpass_gain",
    "rc_charging_voltage",
    "rc_cutoff_frequency",
    "rc_time_constant",
    "resonator_bandwidth",
    "rl_time_constant",
    "series_rlc_quality_factor",
]


def capacitor_stored_energy(*, capacitance: Quantity, voltage: Quantity) -> Quantity:
    """The energy stored in a capacitor, E = ½·C·V².

    The energy held in a capacitor's electric field, E = ½·C·V², from the ``capacitance`` C and the
    ``voltage`` V across it. It rises with the *square* of voltage, so a capacitor charged to twice
    the voltage holds four times the energy — the number that sizes a DC-link or snubber capacitor
    for the transient it must ride, and that a discharge (a flash lamp, a spot welder) delivers.
    Returns the stored energy in joules.
    """
    _check(capacitance, "[capacitance]", "capacitance")
    _check(voltage, "[electric_potential]", "voltage")
    c = capacitance.to("F").magnitude
    v = voltage.to("V").magnitude
    if c <= 0:
        raise ValueError("capacitance must be positive")
    return Quantity(magnitude=0.5 * c * v**2, unit="J")


def inductor_stored_energy(*, inductance: Quantity, current: Quantity) -> Quantity:
    """The energy stored in an inductor, E = ½·L·I².

    The energy held in an inductor's magnetic field, E = ½·L·I², from the ``inductance`` L and the
    ``current`` I through it. Rising with the square of current, it is the energy that has to go
    somewhere the instant a switch interrupts the current — dumped into a freewheeling diode or a
    snubber, or it appears as a destructive arc across the opening contacts. Returns the energy in
    joules.
    """
    _check(inductance, "[inductance]", "inductance")
    _check(current, "[current]", "current")
    length = inductance.to("H").magnitude
    i = current.to("A").magnitude
    if length <= 0:
        raise ValueError("inductance must be positive")
    return Quantity(magnitude=0.5 * length * i**2, unit="J")


def lc_resonant_frequency(*, inductance: Quantity, capacitance: Quantity) -> Quantity:
    """The resonant frequency of an LC circuit, f₀ = 1/(2π·√(L·C)).

    An inductor and capacitor trade energy back and forth at a natural frequency set only by their
    values: f₀ = 1/(2π·√(L·C)), from the ``inductance`` L and ``capacitance`` C. It is the tuning of
    an LC filter or oscillator, the frequency a switching node rings at, and the pole a resonant
    converter is driven around. Returns the resonant frequency in hertz.
    """
    _check(inductance, "[inductance]", "inductance")
    _check(capacitance, "[capacitance]", "capacitance")
    length = inductance.to("H").magnitude
    c = capacitance.to("F").magnitude
    if length <= 0 or c <= 0:
        raise ValueError("inductance and capacitance must be positive")
    return Quantity(magnitude=1.0 / (2.0 * pi * sqrt(length * c)), unit="Hz")


def series_rlc_quality_factor(
    *, resistance: Quantity, inductance: Quantity, capacitance: Quantity
) -> float:
    """The quality factor of a series RLC resonator, Q = (1/R)·√(L/C).

    How sharply a series RLC circuit resonates — the ratio of energy stored to energy dissipated per
    cycle: Q = (1/R)·√(L/C), from the loss ``resistance`` R, the ``inductance`` L, and the
    ``capacitance`` C (equivalently Q = ω₀L/R at the :func:`lc_resonant_frequency`). A high Q gives
    a tall, narrow resonance peak — a selective filter or a clean oscillator — while a low Q is
    broad and heavily damped. It sets the resonance bandwidth (see :func:`resonator_bandwidth`) and
    voltage magnification across the reactances at resonance. Returns the dimensionless quality
    factor.
    """
    _check(resistance, "[resistance]", "resistance")
    _check(inductance, "[inductance]", "inductance")
    _check(capacitance, "[capacitance]", "capacitance")
    r = resistance.to("ohm").magnitude
    length = inductance.to("H").magnitude
    c = capacitance.to("F").magnitude
    if r <= 0:
        raise ValueError("resistance must be positive")
    if length <= 0 or c <= 0:
        raise ValueError("inductance and capacitance must be positive")
    return sqrt(length / c) / r


def resonator_bandwidth(*, resonant_frequency: Quantity, quality_factor: float) -> Quantity:
    """The −3 dB bandwidth of a resonator, BW = f₀/Q.

    The width of the resonance peak between its half-power points: BW = f₀/Q, from the
    ``resonant_frequency`` f₀ (see :func:`lc_resonant_frequency`) and the ``quality_factor`` Q (see
    :func:`series_rlc_quality_factor`). A high-Q resonator has a narrow bandwidth — the basis of a
    selective radio front-end or a stable oscillator — and a low-Q one passes a broad band. It is
    the number that says whether a tuned circuit can separate two nearby channels. Returns the
    bandwidth in hertz.
    """
    _check(resonant_frequency, "1/[time]", "resonant_frequency")
    f0 = count_rate_per_second(resonant_frequency, name="resonant_frequency")
    if f0 <= 0:
        raise ValueError("resonant_frequency must be positive")
    if quality_factor <= 0:
        raise ValueError("quality_factor must be positive")
    return Quantity(magnitude=f0 / quality_factor, unit="Hz")


def capacitive_reactance(*, capacitance: Quantity, frequency: Quantity) -> Quantity:
    """The capacitive reactance, X_C = 1/(2π·f·C).

    The opposition a capacitor presents to alternating current, X_C = 1/(2π·f·C), from the
    ``capacitance`` C and the ``frequency`` f. It falls as the frequency rises, so a capacitor
    blocks DC and low frequencies but passes high ones — the basis of coupling and bypass
    capacitors and the high-pass corner of an RC filter. Returns the reactance in ohms.
    """
    _check(capacitance, "[capacitance]", "capacitance")
    _check(frequency, "1/[time]", "frequency")
    c = capacitance.to("F").magnitude
    f = count_rate_per_second(frequency, name="frequency")
    if c <= 0:
        raise ValueError("capacitance must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    return Quantity(magnitude=1.0 / (2.0 * pi * f * c), unit="ohm")


def inductive_reactance(*, inductance: Quantity, frequency: Quantity) -> Quantity:
    """The inductive reactance, X_L = 2π·f·L.

    The opposition an inductor presents to alternating current, X_L = 2π·f·L, from the
    ``inductance`` L and the ``frequency`` f. It rises with frequency, so an inductor passes DC
    freely but chokes high frequencies — the basis of chokes and the low-pass roll-off of an RL
    filter, and the mirror of :func:`capacitive_reactance`. Returns the reactance in ohms.
    """
    _check(inductance, "[inductance]", "inductance")
    _check(frequency, "1/[time]", "frequency")
    length = inductance.to("H").magnitude
    f = count_rate_per_second(frequency, name="frequency")
    if length <= 0:
        raise ValueError("inductance must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    return Quantity(magnitude=2.0 * pi * f * length, unit="ohm")


def capacitance_for_reactance(*, reactance: Quantity, frequency: Quantity) -> Quantity:
    """The capacitor for a target reactance, C = 1/(2π·f·X_C).

    The design inverse of :func:`capacitive_reactance`: the capacitance that presents a chosen
    ``reactance`` X_C at a ``frequency`` f is C = 1/(2π·f·X_C). It is how a coupling or bypass
    capacitor is picked so its reactance is small compared with the impedance it faces at the
    frequency of interest, and how the shunt capacitor of an impedance-matching network is sized to
    a target reactance. Returns the capacitance in farads.
    """
    _check(reactance, "[resistance]", "reactance")
    _check(frequency, "1/[time]", "frequency")
    x = reactance.to("ohm").magnitude
    f = count_rate_per_second(frequency, name="frequency")
    if x <= 0:
        raise ValueError("reactance must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    return Quantity(magnitude=1.0 / (2.0 * pi * f * x), unit="F")


def inductance_for_reactance(*, reactance: Quantity, frequency: Quantity) -> Quantity:
    """The inductor for a target reactance, L = X_L/(2π·f).

    The design inverse of :func:`inductive_reactance`: the inductance that presents a chosen
    ``reactance`` X_L at a ``frequency`` f is L = X_L/(2π·f). It sizes a choke to a target
    impedance, or the series inductor of a matching network to a needed reactance — the mirror of
    :func:`capacitance_for_reactance`. Returns the inductance in henries.
    """
    _check(reactance, "[resistance]", "reactance")
    _check(frequency, "1/[time]", "frequency")
    x = reactance.to("ohm").magnitude
    f = count_rate_per_second(frequency, name="frequency")
    if x <= 0:
        raise ValueError("reactance must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    return Quantity(magnitude=x / (2.0 * pi * f), unit="H")


def rc_time_constant(*, resistance: Quantity, capacitance: Quantity) -> Quantity:
    """The time constant of an RC circuit, τ = R·C.

    A resistor charging a capacitor settles exponentially with the time constant τ = R·C, from the
    ``resistance`` R and ``capacitance`` C — after one τ the capacitor is 63% of the way to its
    final voltage, and after ~5τ it is essentially there. It sets the debounce delay of an RC
    network, the ripple decay of a filter, and the response time of a first-order sensor. Returns
    the time constant in seconds.
    """
    _check(resistance, "[resistance]", "resistance")
    _check(capacitance, "[capacitance]", "capacitance")
    r = resistance.to("ohm").magnitude
    c = capacitance.to("F").magnitude
    if r <= 0 or c <= 0:
        raise ValueError("resistance and capacitance must be positive")
    return Quantity(magnitude=r * c, unit="s")


def rc_charging_voltage(
    *, supply_voltage: Quantity, time: Quantity, time_constant: Quantity
) -> Quantity:
    """The capacitor voltage while charging through a resistor, V(t) = V_s·(1 − e^(−t/τ)).

    The RC step response — the electrical twin of the lumped-capacitance thermal transient: a
    capacitor charged toward a ``supply_voltage`` V_s through a resistor rises as
    V(t) = V_s·(1 − e^(−t/τ)), from the ``time_constant`` τ = R·C (see
    :func:`rc_time_constant`). It reaches 63% of V_s after one τ, 95% after three, and ~99% after
    five (effectively settled). It sets when an RC delay crosses a logic threshold, how fast a
    sample-and-hold acquires, and the turn-on ramp of a soft-start — the discharge from an initial
    V₀ follows the same shape decayed, V₀·e^(−t/τ). Returns the capacitor voltage in volts.
    """
    _check(supply_voltage, "[electric_potential]", "supply_voltage")
    _check(time, "[time]", "time")
    _check(time_constant, "[time]", "time_constant")
    v_s = supply_voltage.to("V").magnitude
    t = time.to("s").magnitude
    tau = time_constant.to("s").magnitude
    if v_s <= 0:
        raise ValueError("supply_voltage must be positive")
    if t < 0:
        raise ValueError("time must be non-negative")
    if tau <= 0:
        raise ValueError("time_constant must be positive")
    return Quantity(magnitude=v_s * (1.0 - exp(-t / tau)), unit="V")


def rl_time_constant(*, inductance: Quantity, resistance: Quantity) -> Quantity:
    """The time constant of an RL circuit, τ = L/R.

    The current in an inductor driven through a resistor rises (or decays) exponentially with the
    time constant τ = L/R, from the ``inductance`` L and ``resistance`` R. A large inductance or a
    small resistance makes the current sluggish to change — the reason a relay coil or a motor
    winding does not switch its current instantly, and needs a snubber to absorb what is left when
    it tries to. Returns the time constant in seconds.
    """
    _check(inductance, "[inductance]", "inductance")
    _check(resistance, "[resistance]", "resistance")
    length = inductance.to("H").magnitude
    r = resistance.to("ohm").magnitude
    if length <= 0 or r <= 0:
        raise ValueError("inductance and resistance must be positive")
    return Quantity(magnitude=length / r, unit="s")


def rc_cutoff_frequency(*, resistance: Quantity, capacitance: Quantity) -> Quantity:
    """The −3 dB cutoff frequency of a first-order RC filter, f_c = 1/(2π·R·C).

    A single resistor and capacitor make a first-order low- or high-pass filter whose corner — the
    frequency at which the output has fallen 3 dB (to 1/√2 of the passband) — is f_c = 1/(2π·R·C),
    from the ``resistance`` R and ``capacitance`` C. It is the reciprocal of 2π times the RC time
    constant, and the number that sets an anti-alias filter's edge, a sensor's bandwidth, or a tone
    control's turnover. Returns the cutoff frequency in hertz.
    """
    _check(resistance, "[resistance]", "resistance")
    _check(capacitance, "[capacitance]", "capacitance")
    r = resistance.to("ohm").magnitude
    c = capacitance.to("F").magnitude
    if r <= 0 or c <= 0:
        raise ValueError("resistance and capacitance must be positive")
    return Quantity(magnitude=1.0 / (2.0 * pi * r * c), unit="Hz")


def first_order_lowpass_gain(*, frequency: Quantity, cutoff_frequency: Quantity) -> float:
    """The gain magnitude of a first-order low-pass filter, |H| = 1/√(1 + (f/f_c)²).

    How much a single-pole RC low-pass passes a signal at ``frequency`` f relative to its cutoff:
    |H| = 1/√(1 + (f/f_c)²), from f and the −3 dB ``cutoff_frequency`` f_c (see
    :func:`rc_cutoff_frequency`). Well below f_c the gain is ~1 (the passband); at f_c it is 1/√2 ≈
    0.707 (the −3 dB point); far above it rolls off as f_c/f, a first-order 20 dB/decade slope. It
    is the number that says how much an anti-alias or noise filter attenuates a given interfering
    frequency, and how far out the corner must sit to leave the signal band flat. Returns the
    dimensionless voltage gain in (0, 1].
    """
    _check(frequency, "1/[time]", "frequency")
    _check(cutoff_frequency, "1/[time]", "cutoff_frequency")
    f = count_rate_per_second(frequency, name="frequency")
    f_c = count_rate_per_second(cutoff_frequency, name="cutoff_frequency")
    if f < 0:
        raise ValueError("frequency must be non-negative")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    return 1.0 / (1.0 + (f / f_c) ** 2) ** 0.5


def first_order_highpass_gain(*, frequency: Quantity, cutoff_frequency: Quantity) -> float:
    """The gain magnitude of a first-order high-pass filter, |H| = 1/√(1 + (f_c/f)²).

    The complement of :func:`first_order_lowpass_gain`: a single-pole RC high-pass passes
    ``frequency`` f relative to its ``cutoff_frequency`` f_c as |H| = 1/√(1 + (f_c/f)²) =
    (f/f_c)/√(1 + (f/f_c)²). It blocks DC (|H| → 0 as f → 0), reaches 1/√2 (−3 dB) at the corner,
    and approaches 1 well above it — the response of an AC-coupling capacitor, a DC-blocking
    input, or a rumble filter. Its squared magnitude and the low-pass's sum to 1 at every frequency
    (the two split the spectrum at f_c). Returns the dimensionless voltage gain in [0, 1).
    """
    _check(frequency, "1/[time]", "frequency")
    _check(cutoff_frequency, "1/[time]", "cutoff_frequency")
    f = count_rate_per_second(frequency, name="frequency")
    f_c = count_rate_per_second(cutoff_frequency, name="cutoff_frequency")
    if f < 0:
        raise ValueError("frequency must be non-negative")
    if f_c <= 0:
        raise ValueError("cutoff_frequency must be positive")
    if f == 0.0:
        return 0.0
    return 1.0 / (1.0 + (f_c / f) ** 2) ** 0.5


def parallel_plate_capacitance(
    *, plate_area: Quantity, separation: Quantity, relative_permittivity: float = 1.0
) -> Quantity:
    """The parallel-plate capacitance, C = ε₀·ε_r·A/d.

    The capacitance of two parallel plates of ``plate_area`` A separated by a gap ``separation`` d,
    with a dielectric of ``relative_permittivity`` ε_r (1 for vacuum/air): C = ε₀·ε_r·A/d. Larger
    plates, a thinner gap, or a higher-permittivity dielectric all raise it. Returns the capacitance
    in F.
    """
    _check(plate_area, "[area]", "plate_area")
    _check(separation, "[length]", "separation")
    a = plate_area.to("m**2").magnitude
    d = separation.to("m").magnitude
    if a <= 0:
        raise ValueError("plate_area must be positive")
    if d <= 0:
        raise ValueError("separation must be positive")
    if relative_permittivity < 1.0:
        raise ValueError("relative_permittivity must be at least 1")
    return Quantity(magnitude=_VACUUM_PERMITTIVITY * relative_permittivity * a / d, unit="F")


def capacitor_charge(*, capacitance: Quantity, voltage: Quantity) -> Quantity:
    """The stored charge, Q = C·V.

    The charge a capacitor of ``capacitance`` C holds at ``voltage`` V: Q = C·V. It is the charge a
    circuit must supply to bring the capacitor to that voltage, and what it releases on discharge.
    Returns the charge in C (coulombs).
    """
    _check(capacitance, "[capacitance]", "capacitance")
    _check(voltage, "[electric_potential]", "voltage")
    c = capacitance.to("F").magnitude
    v = voltage.to("V").magnitude
    if c <= 0:
        raise ValueError("capacitance must be positive")
    return Quantity(magnitude=c * v, unit="C")


def parallel_plate_field(*, voltage: Quantity, separation: Quantity) -> Quantity:
    """The field between parallel plates, E = V/d.

    The uniform electric field between two parallel plates at ``voltage`` V separated by a gap
    ``separation`` d: E = V/d. It sets the dielectric stress — exceed the material's breakdown
    strength and the capacitor arcs over. Returns the field in V/m.
    """
    _check(voltage, "[electric_potential]", "voltage")
    _check(separation, "[length]", "separation")
    v = voltage.to("V").magnitude
    d = separation.to("m").magnitude
    if d <= 0:
        raise ValueError("separation must be positive")
    return Quantity(magnitude=v / d, unit="V/m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
