"""Worked example: the step response of a tuned servo positioner.

A servo, a suspension, or any second-order system answers a sudden command by overshooting and
ringing before it settles. The damping ratio alone fixes how much it overshoots, and with the
natural frequency it sets how quickly it peaks and settles — the numbers a control designer tunes.

A positioner tuned to a damping ratio of 0.5 and an undamped natural frequency of about 1.59 Hz
(ω_n = 10 rad/s) overshoots its target by about 16% on a step command. It reaches that first peak in
about 0.36 s and settles within 2% of the final position in about 0.80 s. Raising the damping toward
0.7 would cut the overshoot below 5% at the cost of a slower response. This example reports the
percent overshoot, the peak time, and the settling time.

Run it directly (``python examples/servo_step_response.py``);
:func:`servo_step_response` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    step_response_peak_time,
    step_response_percent_overshoot,
    step_response_settling_time,
)
from anvilate.units import Quantity

DAMPING_RATIO = 0.5
NATURAL_FREQUENCY = Quantity(magnitude=10.0 / (2.0 * 3.141592653589793), unit="Hz")  # omega_n=10


def servo_step_response() -> dict[str, float]:
    """Return the percent overshoot, the peak time, and the settling time."""
    overshoot = step_response_percent_overshoot(damping_ratio=DAMPING_RATIO)
    peak = step_response_peak_time(natural_frequency=NATURAL_FREQUENCY, damping_ratio=DAMPING_RATIO)
    settling = step_response_settling_time(
        natural_frequency=NATURAL_FREQUENCY, damping_ratio=DAMPING_RATIO
    )
    return {
        "percent_overshoot": overshoot,
        "peak_time_s": peak.to("s").magnitude,
        "settling_time_s": settling.to("s").magnitude,
    }


def main() -> None:
    d = servo_step_response()
    print(f"percent overshoot: {d['percent_overshoot']:.1f}%")
    print(f"peak time: {d['peak_time_s']:.3f} s")
    print(f"settling time (2%): {d['settling_time_s']:.3f} s")


if __name__ == "__main__":
    main()
