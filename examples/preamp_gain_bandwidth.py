"""Worked example: sizing an op-amp preamp and hitting its gain-bandwidth limit.

An op-amp gain stage is set by two resistors, but the gain you choose spends the amplifier's fixed
gain-bandwidth product: the more you amplify, the less bandwidth is left. Designing a preamp means
picking the resistor ratio for the gain, then checking the bandwidth that a real part's GBW leaves —
and splitting into stages if it is not enough. This example does both for a 10 MHz gain-bandwidth op
amp.

A non-inverting stage with a 90 kohm feedback and 10 kohm ground resistor gives a gain of 10 (an
inverting stage with 100 kohm and 10 kohm gives -10, the same magnitude, phase-flipped). At a gain
of 10, the 10 MHz gain-bandwidth part leaves 1 MHz of bandwidth. Push the same part to a gain of 100
and only 100 kHz remains — which is why a high-gain, wide-band preamp is built as two cascaded
gain-of-10 stages (10 MHz / 10 = 1 MHz each) rather than one gain-of-100 stage. The example reports
the non-inverting gain and the bandwidth at gains of 10 and 100.

Run it directly (``python examples/preamp_gain_bandwidth.py``);
:func:`preamp_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import gain_bandwidth_limited_bandwidth, noninverting_gain
from anvilate.units import Quantity

FEEDBACK_RESISTANCE = Quantity.parse("90 kohm")
GROUND_RESISTANCE = Quantity.parse("10 kohm")
GAIN_BANDWIDTH_PRODUCT = Quantity(magnitude=10e6, unit="Hz")
HIGH_GAIN = 100.0


def preamp_design() -> dict[str, float]:
    """Return the gain-of-10 stage gain and the bandwidth at gains of 10 and 100."""
    gain = noninverting_gain(
        feedback_resistance=FEEDBACK_RESISTANCE, ground_resistance=GROUND_RESISTANCE
    )
    bw_at_10 = gain_bandwidth_limited_bandwidth(
        gain_bandwidth_product=GAIN_BANDWIDTH_PRODUCT, closed_loop_gain=gain
    )
    bw_at_100 = gain_bandwidth_limited_bandwidth(
        gain_bandwidth_product=GAIN_BANDWIDTH_PRODUCT, closed_loop_gain=HIGH_GAIN
    )
    return {
        "stage_gain": gain,
        "bandwidth_at_gain_10_khz": bw_at_10.to("kHz").magnitude,
        "bandwidth_at_gain_100_khz": bw_at_100.to("kHz").magnitude,
    }


def main() -> None:
    d = preamp_design()
    print(f"non-inverting stage gain: {d['stage_gain']:.0f}")
    print(f"bandwidth at gain 10: {d['bandwidth_at_gain_10_khz']:.0f} kHz")
    print(f"bandwidth at gain 100: {d['bandwidth_at_gain_100_khz']:.0f} kHz")


if __name__ == "__main__":
    main()
