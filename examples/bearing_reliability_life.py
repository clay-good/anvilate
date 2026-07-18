"""Worked example: the reliability the catalogue L10 does not promise.

A ball bearing carries a 4 kN equivalent load and turns at 1200 rpm. Its catalogue
dynamic rating gives a basic rating life L10 of about 18,500 hours -- comfortably
past a 10,000-hour service target. But L10 is a *10% failure* number: it is the life
only 90% of a population of these bearings reach. For most machinery that is the
right design point. For a critical one -- a machine whose bearing failure stops a
line or endangers people -- 90% is nowhere near enough.

Designing for a higher reliability costs life, and the ISO 281 a1 factor says how
much. The Weibull scatter of bearing fatigue means the life for reliability R scales
as (ln(1/R)/ln(1/0.90))^(1/1.5) of L10. Push the target from 90% to 95% and the
usable life falls to 11,400 hours; push it to 99% and it collapses to 3,900 hours --
below the 10,000-hour target the bearing seemed to clear with ease. The catalogue
number was never a promise of the reliability a critical design needs.

The point is that L10 answers a question -- "when do 10% fail?" -- that is not the
question a high-reliability application is asking. Size the bearing (or cut the load)
for the reliability you actually require, not the one the catalogue happens to
tabulate. The rating and load are declared inline.

Run it directly (``python examples/bearing_reliability_life.py``);
:func:`screen_bearing_reliability` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import bearing_life_hours, bearing_reliability_life_factor
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DYNAMIC_RATING = Quantity.parse("44 kN")
EQUIVALENT_LOAD = Quantity.parse("4 kN")
SPEED = Quantity.parse("1200 rpm")
REQUIRED_SERVICE_LIFE = Quantity.parse("10000 hour")
RELIABILITIES = (0.90, 0.95, 0.99)


def screen_bearing_reliability() -> Scorecard:
    """Screen the reliability-adjusted bearing life against the required service life
    at each reliability target (safety factor = adjusted life / required life)."""
    l10 = (
        bearing_life_hours(
            dynamic_load_rating=DYNAMIC_RATING, equivalent_load=EQUIVALENT_LOAD, speed=SPEED
        )
        .to("hour")
        .magnitude
    )
    required = REQUIRED_SERVICE_LIFE.to("hour").magnitude
    entries = []
    for reliability in RELIABILITIES:
        a1 = bearing_reliability_life_factor(reliability=reliability)
        adjusted = a1 * l10
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"life at {reliability:.0%} reliability",
                computed=adjusted / required,
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    l10 = (
        bearing_life_hours(
            dynamic_load_rating=DYNAMIC_RATING, equivalent_load=EQUIVALENT_LOAD, speed=SPEED
        )
        .to("hour")
        .magnitude
    )
    print(f"basic rating life L10 (90% reliability): {l10:,.0f} hours")
    for reliability in RELIABILITIES:
        a1 = bearing_reliability_life_factor(reliability=reliability)
        print(f"life at {reliability:.0%}: {a1 * l10:,.0f} hours (a1 = {a1:.2f})")
    print(screen_bearing_reliability())


if __name__ == "__main__":
    main()
