"""T1 analytical switching DC-DC converter checks (closed-form, ideal / continuous conduction).

A switching regulator sets its output voltage by the fraction of each cycle its switch is on — the
duty cycle D — rather than by burning off the excess as a linear regulator does. The three canonical
non-isolated topologies each convert the input a different way: the buck steps voltage down, the
boost steps it up, and the buck-boost can do either (with an inverted output). These ideal transfer
functions (loss-free, continuous-conduction) are the first sizing step for any point-of-load supply,
and they are distinct from the fixed-ratio :mod:`anvilate.analysis.electrical` transformer (which
needs AC and cannot change its ratio on the fly).

For the buck, V_out = D * V_in, always at or below the input. For the boost, V_out = V_in / (1 - D),
always at or above it, rising steeply as D approaches 1. For the buck-boost, V_out = V_in*D/(1 - D)
(magnitude; the real output is inverted), below the input for D < 0.5 and above it for D > 0.5. In
every case the duty cycle is the single control knob, and these relations set the operating D a
target output needs.

Sources: Erickson & Maksimovic, *Fundamentals of Power Electronics*, for the
buck/boost conversion ratios, ripple and continuous-conduction boundary relations.
"""

from __future__ import annotations

from ..units import Quantity
from ..units.rotation import count_rate_per_second

__all__ = [
    "boost_duty_cycle_for_output",
    "boost_output_voltage",
    "buck_boost_duty_cycle_for_output",
    "buck_boost_output_voltage",
    "buck_duty_cycle_for_output",
    "buck_inductor_peak_current",
    "buck_inductor_ripple_current",
    "buck_minimum_inductance_for_ccm",
    "buck_output_voltage",
    "buck_output_voltage_ripple",
]


def buck_output_voltage(*, input_voltage: Quantity, duty_cycle: float) -> Quantity:
    """The buck (step-down) output voltage, V_out = D * V_in.

    A buck converter's ideal output: the ``input_voltage`` V_in scaled by the ``duty_cycle`` D (the
    fraction of each switching cycle the high-side switch conducts), V_out = D * V_in. The output is
    always at or below the input, and D is the single control knob a feedback loop turns. Assumes an
    ideal, continuous-conduction converter. Returns the output voltage in V.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    v_in = input_voltage.to("V").magnitude
    if not 0.0 < duty_cycle < 1.0:
        raise ValueError("duty_cycle must be in (0, 1)")
    return Quantity(magnitude=duty_cycle * v_in, unit="V")


def buck_duty_cycle_for_output(*, input_voltage: Quantity, output_voltage: Quantity) -> float:
    """The buck duty cycle for a target output, D = V_out/V_in.

    The design inverse of :func:`buck_output_voltage`: the fraction of each switching cycle the
    high-side switch must conduct to hold the ``output_voltage`` V_out from the ``input_voltage``
    V_in is D = V_out/V_in. Because a buck only steps down, the output must be below the input (D in
    (0, 1)); asking for V_out ≥ V_in is rejected. Assumes an ideal, continuous-conduction converter.
    Returns the dimensionless duty cycle.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    _check(output_voltage, "[electric_potential]", "output_voltage")
    v_in = input_voltage.to("V").magnitude
    v_out = output_voltage.to("V").magnitude
    if v_in <= 0:
        raise ValueError("input_voltage must be positive")
    if v_out <= 0:
        raise ValueError("output_voltage must be positive")
    if v_out >= v_in:
        raise ValueError("output_voltage must be below input_voltage (a buck only steps down)")
    return v_out / v_in


def boost_output_voltage(*, input_voltage: Quantity, duty_cycle: float) -> Quantity:
    """The boost (step-up) output voltage, V_out = V_in / (1 - D).

    A boost converter's ideal output: the ``input_voltage`` V_in divided by (1 - ``duty_cycle`` D),
    V_out = V_in / (1 - D). The output is always at or above the input and rises steeply as D nears
    1 (where losses and stress make the ideal relation optimistic). Assumes an ideal,
    continuous-conduction converter. Returns the output voltage in V.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    v_in = input_voltage.to("V").magnitude
    if not 0.0 < duty_cycle < 1.0:
        raise ValueError("duty_cycle must be in (0, 1)")
    return Quantity(magnitude=v_in / (1.0 - duty_cycle), unit="V")


def boost_duty_cycle_for_output(*, input_voltage: Quantity, output_voltage: Quantity) -> float:
    """The boost duty cycle for a target output, D = 1 − V_in/V_out.

    The design inverse of :func:`boost_output_voltage`: the duty cycle needed to raise the
    ``input_voltage`` V_in up to the ``output_voltage`` V_out is D = 1 − V_in/V_out. Because a boost
    only steps up, the output must exceed the input; asking for V_out ≤ V_in is rejected. The duty
    approaches 1 as the step-up ratio grows, where the ideal relation turns optimistic. Assumes an
    ideal, continuous-conduction converter. Returns the dimensionless duty cycle.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    _check(output_voltage, "[electric_potential]", "output_voltage")
    v_in = input_voltage.to("V").magnitude
    v_out = output_voltage.to("V").magnitude
    if v_in <= 0:
        raise ValueError("input_voltage must be positive")
    if v_out <= 0:
        raise ValueError("output_voltage must be positive")
    if v_out <= v_in:
        raise ValueError("output_voltage must exceed input_voltage (a boost only steps up)")
    return 1.0 - v_in / v_out


def buck_boost_output_voltage(*, input_voltage: Quantity, duty_cycle: float) -> Quantity:
    """The buck-boost output voltage magnitude, V_out = V_in * D / (1 - D).

    A buck-boost converter's ideal output magnitude: the ``input_voltage`` V_in times
    ``duty_cycle`` D over (1 - D), V_out = V_in * D/(1 - D) (the physical output is inverted in
    polarity). It steps down for D < 0.5 and up for D > 0.5, so one topology spans both. Assumes an
    ideal, continuous-conduction converter. Returns the output voltage magnitude in V.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    v_in = input_voltage.to("V").magnitude
    if not 0.0 < duty_cycle < 1.0:
        raise ValueError("duty_cycle must be in (0, 1)")
    return Quantity(magnitude=v_in * duty_cycle / (1.0 - duty_cycle), unit="V")


def buck_boost_duty_cycle_for_output(*, input_voltage: Quantity, output_voltage: Quantity) -> float:
    """The buck-boost duty cycle for a target output, D = V_out/(V_in + V_out).

    The design inverse of :func:`buck_boost_output_voltage`: for a target output magnitude V_out
    from the ``input_voltage`` V_in, solving V_out = V_in·D/(1 − D) gives D = V_out/(V_in + V_out).
    Because the topology spans both directions, any positive output is reachable — D < 0.5 steps
    down, D > 0.5 steps up, and D = 0.5 gives unity. ``output_voltage`` is the magnitude (the
    physical output is polarity-inverted). Assumes an ideal, continuous-conduction converter.
    Returns the dimensionless duty cycle.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    _check(output_voltage, "[electric_potential]", "output_voltage")
    v_in = input_voltage.to("V").magnitude
    v_out = output_voltage.to("V").magnitude
    if v_in <= 0:
        raise ValueError("input_voltage must be positive")
    if v_out <= 0:
        raise ValueError("output_voltage must be positive")
    return v_out / (v_in + v_out)


def buck_inductor_ripple_current(
    *,
    input_voltage: Quantity,
    output_voltage: Quantity,
    inductance: Quantity,
    switching_frequency: Quantity,
) -> Quantity:
    """The buck inductor peak-to-peak ripple current, ΔI_L = (V_in − V_out)·V_out/(V_in·L·f_s).

    While the buck's high-side switch is on, the inductor sees V_in − V_out and its current ramps
    up; over the on-time D/f_s (with D = V_out/V_in) that ramp is ΔI_L =
    (V_in − V_out)·V_out/(V_in·L·f_s). It sizes the inductor: too small an L (or too low a
    ``switching_frequency`` f_s) gives a large ripple that raises RMS current and can tip the
    converter into discontinuous conduction. From the ``input_voltage`` V_in, the
    ``output_voltage`` V_out (≤ V_in), the ``inductance`` L, and f_s.
    Returns the peak-to-peak ripple current in A.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    _check(output_voltage, "[electric_potential]", "output_voltage")
    _check(inductance, "[inductance]", "inductance")
    _check(switching_frequency, "1/[time]", "switching_frequency")
    v_in = input_voltage.to("V").magnitude
    v_out = output_voltage.to("V").magnitude
    ind = inductance.to("H").magnitude
    f_s = count_rate_per_second(switching_frequency, name="switching_frequency")
    if v_in <= 0:
        raise ValueError("input_voltage must be positive")
    if not 0.0 < v_out <= v_in:
        raise ValueError(
            "output_voltage must be positive and at most input_voltage (a buck steps down)"
        )
    if ind <= 0:
        raise ValueError("inductance must be positive")
    if f_s <= 0:
        raise ValueError("switching_frequency must be positive")
    ripple = (v_in - v_out) * v_out / (v_in * ind * f_s)
    return Quantity(magnitude=ripple, unit="A")


def buck_inductor_peak_current(
    *,
    load_current: Quantity,
    ripple_current: Quantity,
) -> Quantity:
    """The buck inductor peak current, I_pk = I_load + ΔI_L/2.

    In continuous conduction the inductor current is a triangle centred on the DC ``load_current``
    I_load (which the average inductor current equals in a buck), swinging ±ΔI_L/2 about it, so its
    crest is I_pk = I_load + ``ripple_current``/2 (ΔI_L from :func:`buck_inductor_ripple_current`).
    This peak — not the average — is what the inductor's saturation rating and the switch's current
    limit must clear: run the core past it and the inductance collapses, the ripple runs away, and
    the switch current spikes. A distinct rating from the RMS/ripple that sizes the core loss.
    Returns the peak inductor current in A.
    """
    _check(load_current, "[current]", "load_current")
    _check(ripple_current, "[current]", "ripple_current")
    i_load = load_current.to("A").magnitude
    d_il = ripple_current.to("A").magnitude
    if i_load < 0:
        raise ValueError("load_current must be non-negative")
    if d_il < 0:
        raise ValueError("ripple_current must be non-negative")
    return Quantity(magnitude=i_load + d_il / 2.0, unit="A")


def buck_output_voltage_ripple(
    *,
    inductor_ripple_current: Quantity,
    output_capacitance: Quantity,
    switching_frequency: Quantity,
) -> Quantity:
    """The buck output voltage ripple, ΔV = ΔI_L/(8·C·f_s).

    The output capacitor absorbs the inductor's triangular ripple current, and the charge swing over
    a cycle leaves a peak-to-peak voltage ripple ΔV = ΔI_L/(8·C·f_s) — from the
    ``inductor_ripple_current`` ΔI_L (:func:`buck_inductor_ripple_current`), the
    ``output_capacitance`` C, and the ``switching_frequency`` f_s. The 8 is the geometric factor for
    a triangular charge waveform. It sizes the output cap for a ripple spec (ESR, ignored here, adds
    to it). Returns the peak-to-peak output ripple voltage in V.
    """
    _check(inductor_ripple_current, "[current]", "inductor_ripple_current")
    _check(output_capacitance, "[capacitance]", "output_capacitance")
    _check(switching_frequency, "1/[time]", "switching_frequency")
    d_il = inductor_ripple_current.to("A").magnitude
    cap = output_capacitance.to("F").magnitude
    f_s = count_rate_per_second(switching_frequency, name="switching_frequency")
    if d_il < 0:
        raise ValueError("inductor_ripple_current must be non-negative")
    if cap <= 0:
        raise ValueError("output_capacitance must be positive")
    if f_s <= 0:
        raise ValueError("switching_frequency must be positive")
    return Quantity(magnitude=d_il / (8.0 * cap * f_s), unit="V")


def buck_minimum_inductance_for_ccm(
    *,
    output_voltage: Quantity,
    load_current: Quantity,
    duty_cycle: float,
    switching_frequency: Quantity,
) -> Quantity:
    """The buck critical inductance for continuous conduction, L_min = (1 − D)·V_out/(2·I_out·f_s).

    Continuous conduction holds only while the inductor's average current exceeds half its ripple;
    at the boundary that fixes a minimum inductance L_min = (1 − D)·V_out/(2·I_out·f_s), from the
    ``output_voltage`` V_out, the ``load_current`` I_out, the ``duty_cycle`` D, and the
    ``switching_frequency`` f_s. Below it the converter drops into discontinuous conduction, where
    the output-voltage relation changes and control gets harder; a light load (small I_out) raises
    the bar. Returns the minimum inductance in H.
    """
    _check(output_voltage, "[electric_potential]", "output_voltage")
    _check(load_current, "[current]", "load_current")
    _check(switching_frequency, "1/[time]", "switching_frequency")
    v_out = output_voltage.to("V").magnitude
    i_out = load_current.to("A").magnitude
    f_s = count_rate_per_second(switching_frequency, name="switching_frequency")
    if not 0.0 < duty_cycle < 1.0:
        raise ValueError("duty_cycle must be in (0, 1)")
    if v_out <= 0:
        raise ValueError("output_voltage must be positive")
    if i_out <= 0:
        raise ValueError("load_current must be positive")
    if f_s <= 0:
        raise ValueError("switching_frequency must be positive")
    return Quantity(magnitude=(1.0 - duty_cycle) * v_out / (2.0 * i_out * f_s), unit="H")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
