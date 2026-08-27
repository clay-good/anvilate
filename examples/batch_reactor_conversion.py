"""Worked example: the batch that cannot hit its conversion in the shift.

A batch reactor runs a first-order decomposition and the recipe calls for 95% conversion before the
product is drawn off. The plant gives the reaction a 2-hour hold. At the operating temperature the
rate constant is 0.5 /hr, and the first-order law inverts to a conversion time t = -ln(1 - X)/k =
-ln(0.05)/0.5 = 6.0 hours. That is three times the hold available -- a safety factor of 0.33 -- so
the batch is drawn at barely 63% converted and fails spec. No amount of stirring fixes it; the
kinetics, not the mixing, set the clock, and the exponential tail means the last few percent of
conversion cost as much time as the first ninety.

Raising the temperature to lift the rate constant to 2.0 /hr (an Arrhenius effect) cuts the 95%
conversion time to 1.5 hours -- a safety factor of 1.34 -- so the same 2-hour hold now clears the
target with margin. The reaction, not the schedule, moved.

The lesson is that batch time is spent against the reaction's own clock: size the hold to
-ln(1 - X)/k for the target conversion, and if it does not fit, change the rate constant
(temperature,
catalyst), because chasing the last nines of conversion by waiting is exponentially expensive.

Run it directly (``python examples/batch_reactor_conversion.py``);
:func:`screen_slow_batch` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import first_order_time_for_conversion
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TARGET_CONVERSION = 0.95
AVAILABLE_HOLD = Quantity.parse("2 hour")
SLOW_RATE_CONSTANT = Quantity.parse("0.5 1/hour")  # at the base temperature
FAST_RATE_CONSTANT = Quantity.parse("2.0 1/hour")  # at the raised temperature


def _screen(rate_constant: Quantity) -> Scorecard:
    required_time = first_order_time_for_conversion(
        rate_constant=rate_constant, conversion=TARGET_CONVERSION
    )
    margin = AVAILABLE_HOLD.to("hour").magnitude / required_time.to("hour").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "available hold vs conversion time",
                computed=margin,
                required=1.0,
            ),
        )
    )


def screen_slow_batch() -> Scorecard:
    """Screen the base-temperature batch: it cannot reach 95% in the 2-hour hold."""
    return _screen(SLOW_RATE_CONSTANT)


def screen_hot_batch() -> Scorecard:
    """Screen the raised-temperature batch: the faster rate constant fits the hold."""
    return _screen(FAST_RATE_CONSTANT)


def main() -> None:
    print("base temperature (k = 0.5 /hr):")
    print(screen_slow_batch())
    print("\nraised temperature (k = 2.0 /hr):")
    print(screen_hot_batch())


if __name__ == "__main__":
    main()
