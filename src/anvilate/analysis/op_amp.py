"""T1 analytical operational-amplifier checks (closed-form, ideal op-amp).

An operational amplifier with negative feedback sets its gain almost entirely from a pair of
external resistors, not from the amplifier's own huge open-loop gain — the design principle behind
nearly every analog signal-conditioning stage. But that gain is not free: a real op-amp has a fixed
gain-bandwidth product, so the more gain you take, the less bandwidth remains. These ideal relations
are the first sizing step for a preamp or filter stage, distinct from the switching regulator of
:mod:`anvilate.analysis.dc_dc_converter` (which sets a voltage, not an amplification).

A non-inverting amplifier gives a closed-loop gain of 1 + Rf/Rg, from the feedback resistor Rf and
the ground-leg resistor Rg (always at least one, and in phase with the input). An inverting stage
gives -Rf/Rin, from the feedback and input resistors (any magnitude, but phase-flipped). The
gain-bandwidth product GBW then caps the usable bandwidth at f = GBW / |A| for a closed-loop gain A,
so a 1 MHz-gain-bandwidth part run at a gain of 100 has only 10 kHz of bandwidth left.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "gain_bandwidth_limited_bandwidth",
    "inverting_gain",
    "noninverting_gain",
]


def noninverting_gain(*, feedback_resistance: Quantity, ground_resistance: Quantity) -> float:
    """The non-inverting closed-loop gain, A = 1 + Rf/Rg.

    The gain of a non-inverting op-amp stage: the ``feedback_resistance`` Rf over the ground-leg
    ``ground_resistance`` Rg, plus one, A = 1 + Rf/Rg. The output is in phase with the input and the
    gain is always at least one (a unity-follower has Rf = 0). Returns the gain as a plain float.
    """
    _check(feedback_resistance, "[electric_potential]/[current]", "feedback_resistance")
    _check(ground_resistance, "[electric_potential]/[current]", "ground_resistance")
    rf = feedback_resistance.to("ohm").magnitude
    rg = ground_resistance.to("ohm").magnitude
    if rf < 0:
        raise ValueError("feedback_resistance must be non-negative")
    if rg <= 0:
        raise ValueError("ground_resistance must be positive")
    return 1.0 + rf / rg


def inverting_gain(*, feedback_resistance: Quantity, input_resistance: Quantity) -> float:
    """The inverting closed-loop gain, A = -Rf/Rin.

    The gain of an inverting op-amp stage: minus the ``feedback_resistance`` Rf over the
    ``input_resistance`` Rin, A = -Rf/Rin. The output is phase-inverted (the negative sign), and the
    magnitude can be above or below one. Returns the gain as a plain float (negative).
    """
    _check(feedback_resistance, "[electric_potential]/[current]", "feedback_resistance")
    _check(input_resistance, "[electric_potential]/[current]", "input_resistance")
    rf = feedback_resistance.to("ohm").magnitude
    rin = input_resistance.to("ohm").magnitude
    if rf < 0:
        raise ValueError("feedback_resistance must be non-negative")
    if rin <= 0:
        raise ValueError("input_resistance must be positive")
    return -rf / rin


def gain_bandwidth_limited_bandwidth(
    *, gain_bandwidth_product: Quantity, closed_loop_gain: float
) -> Quantity:
    """The bandwidth left at a chosen gain, f = GBW / |A|.

    A real op-amp trades gain for bandwidth at a fixed ``gain_bandwidth_product`` GBW: the -3 dB
    bandwidth remaining at a ``closed_loop_gain`` A is f = GBW / |A|. Taking more gain leaves less
    bandwidth, which is why a high-gain stage is often split into cascaded lower-gain stages.
    Returns the bandwidth in Hz.
    """
    _check(gain_bandwidth_product, "1/[time]", "gain_bandwidth_product")
    gbw = gain_bandwidth_product.to("Hz").magnitude
    if gbw <= 0:
        raise ValueError("gain_bandwidth_product must be positive")
    if closed_loop_gain == 0:
        raise ValueError("closed_loop_gain must be non-zero")
    return Quantity(magnitude=gbw / abs(closed_loop_gain), unit="Hz")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
