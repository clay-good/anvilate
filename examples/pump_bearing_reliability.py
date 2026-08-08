"""Worked example: Weibull reliability of a wear-out-limited pump bearing.

A fleet of bearings does not all fail at once — the times to failure spread out, and the Weibull
distribution captures that spread with a characteristic life and a shape parameter. From those two
numbers the survival probability at any age, the instantaneous failure rate, and the population's
mean life all follow in closed form.

Take a bearing with a characteristic life of 1,000 hours and a shape of 2.0 (a classic wear-out
mode: the failure rate climbs with age). At 500 hours about 78% are still running, the hazard rate
has risen to 0.001 per hour, and the mean time to failure is about 886 hours — a little short of the
characteristic life because the wear-out shape pulls the average down. This example reports the
reliability at 500 hours, the hazard rate at 500 hours, and the mean time to failure.

Run it directly (``python examples/pump_bearing_reliability.py``);
:func:`bearing_reliability` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    weibull_hazard_rate,
    weibull_mean_life,
    weibull_reliability,
)
from anvilate.units import Quantity

CHARACTERISTIC_LIFE = Quantity(magnitude=1000.0, unit="hour")
SHAPE = 2.0  # wear-out
AGE = Quantity(magnitude=500.0, unit="hour")


def bearing_reliability() -> dict[str, float]:
    """Return the reliability at 500 h, the hazard rate at 500 h, and the mean time to failure."""
    r = weibull_reliability(time=AGE, characteristic_life=CHARACTERISTIC_LIFE, shape=SHAPE)
    h = weibull_hazard_rate(time=AGE, characteristic_life=CHARACTERISTIC_LIFE, shape=SHAPE)
    mttf = weibull_mean_life(characteristic_life=CHARACTERISTIC_LIFE, shape=SHAPE)
    return {
        "reliability_at_500h": r,
        "hazard_rate_per_hour": h.to("1/hour").magnitude,
        "mean_time_to_failure_h": mttf.to("hour").magnitude,
    }


def main() -> None:
    d = bearing_reliability()
    print(f"reliability at 500 h: {d['reliability_at_500h']:.3f}")
    print(f"hazard rate at 500 h: {d['hazard_rate_per_hour']:.5f} /h")
    print(f"mean time to failure: {d['mean_time_to_failure_h']:.0f} h")


if __name__ == "__main__":
    main()
