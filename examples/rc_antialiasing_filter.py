"""Worked example: an RC anti-aliasing filter — the cutoff it sets and the settling it costs.

A single resistor and capacitor make the simplest low-pass filter, used everywhere to keep
high-frequency noise out of a sampled sensor signal. Its behaviour is a trade between two numbers
that move together. This example sizes a 10 kΩ / 100 nF RC filter ahead of an analog-to-digital
converter and reports both: the −3 dB cutoff frequency f_c = 1/(2π·R·C), which must sit below half
the sample rate to do its anti-aliasing job, and the time constant τ = R·C, which sets how long the
filter takes to settle after a step (about five time constants to within 1%). Lowering the cutoff to
reject more noise raises the time constant and slows the response — the same RC cannot be both sharp
and fast, which is the compromise every first-order filter forces.

Run it directly (``python examples/rc_antialiasing_filter.py``);
:func:`rc_filter` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rc_cutoff_frequency, rc_time_constant
from anvilate.units import Quantity

RESISTANCE = Quantity.parse("10 kohm")
CAPACITANCE = Quantity.parse("100 nF")


def rc_filter() -> dict[str, float]:
    """Return the RC filter's cutoff frequency (Hz), time constant (ms), and settling time (ms)."""
    cutoff = rc_cutoff_frequency(resistance=RESISTANCE, capacitance=CAPACITANCE)
    tau = rc_time_constant(resistance=RESISTANCE, capacitance=CAPACITANCE)
    tau_ms = tau.to("ms").magnitude
    return {
        "cutoff_hz": cutoff.to("Hz").magnitude,
        "time_constant_ms": tau_ms,
        "settling_ms": 5.0 * tau_ms,  # ~5 tau to within 1%
    }


def main() -> None:
    r = rc_filter()
    print(f"cutoff frequency f_c : {r['cutoff_hz']:.0f} Hz (put well below the Nyquist rate)")
    print(f"time constant τ      : {r['time_constant_ms']:.1f} ms")
    print(f"settling (~5τ)       : {r['settling_ms']:.0f} ms to within 1% of a step")
    print(
        "  -> a lower cutoff rejects more noise but settles slower; one RC can't be sharp and fast"
    )


if __name__ == "__main__":
    main()
