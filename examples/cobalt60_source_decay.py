"""Worked example: the decay of a Co-60 source — how much is left, and how long until it is spent.

A sealed radioactive source loses strength by exponential decay, halving its activity once per
half-life no matter how much remains. Sizing the use of a source turns on two questions: how much
activity is left after a service interval, and how long a source (or activated material) must sit
before it has decayed to a level low enough to replace, handle, or dispose of.

This example follows a Co-60 industrial source (half-life 5.27 years) starting at 100 GBq. Its decay
constant is about 0.132 per year. After 10 years — nearly two half-lives — about 26.8 GBq remains,
just over a quarter of the original. Asking the inverse, it takes about 17.5 years for the source to
fall to 10 GBq (10% of its start), which sets the replacement interval for a device that needs at
least that activity. The example reports the decay constant, the activity after 10 years, and the
time to decay to 10%.

Run it directly (``python examples/cobalt60_source_decay.py``);
:func:`source_decay` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    decay_constant_from_half_life,
    remaining_activity,
    time_for_activity_decay,
)
from anvilate.units import Quantity

HALF_LIFE = Quantity.parse("5.27 yr")
INITIAL_ACTIVITY = Quantity.parse("100 GBq")
SERVICE_INTERVAL = Quantity.parse("10 yr")
END_OF_LIFE_ACTIVITY = Quantity.parse("10 GBq")


def source_decay() -> dict[str, float]:
    """Return the decay constant, the activity after 10 years, and the time to decay to 10 GBq."""
    decay_constant = decay_constant_from_half_life(half_life=HALF_LIFE)
    activity_after = remaining_activity(
        initial_activity=INITIAL_ACTIVITY,
        elapsed_time=SERVICE_INTERVAL,
        half_life=HALF_LIFE,
    )
    replacement_time = time_for_activity_decay(
        initial_activity=INITIAL_ACTIVITY,
        final_activity=END_OF_LIFE_ACTIVITY,
        half_life=HALF_LIFE,
    )
    return {
        "decay_constant_per_year": decay_constant.to("1/yr").magnitude,
        "activity_after_10yr_gbq": activity_after.to("GBq").magnitude,
        "time_to_10pct_yr": replacement_time.to("yr").magnitude,
    }


def main() -> None:
    d = source_decay()
    print(f"decay constant: {d['decay_constant_per_year']:.3f} /yr")
    print(f"activity after 10 yr: {d['activity_after_10yr_gbq']:.1f} GBq")
    print(f"time to decay to 10 GBq: {d['time_to_10pct_yr']:.1f} yr")


if __name__ == "__main__":
    main()
