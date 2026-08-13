"""Worked example: the trawler that cannot make its scheduled speed.

A small displacement trawler is scheduled to cruise at 8 knots between fishing grounds. As first
drawn it has a 7.6 m (25 ft) waterline. A displacement hull cannot economically exceed its hull
speed v = sqrt(g*L/(2*pi)), where its own bow wave grows to the waterline length and wave-making
drag climbs a wall; for a 7.6 m waterline that ceiling is only 6.7 knots. The 8-knot schedule sits
above it, a safety factor of 0.84, so the boat would have to be dragged past hull speed at
disproportionate power -- burning fuel to pile up a stern wave, not to go faster. No bigger engine
fixes it cleanly; the limit is the length of the hull.

Stretching the waterline to 12.2 m (40 ft) moves the wall: hull speed rises with the square root of
length to 8.5 knots, and the 8-knot cruise now sits below it with a 1.06 margin, in the efficient
displacement regime. The longer boat is the faster boat.

The lesson is that a displacement hull's speed is bought with waterline length, not horsepower:
size the waterline so the scheduled speed stays under sqrt(g*L/(2*pi)), and if it does not, lengthen
the hull (or accept a planing hull) rather than force it past its own wave.

Run it directly (``python examples/trawler_hull_speed.py``);
:func:`screen_short_hull` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import hull_speed
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

SCHEDULED_SPEED = Quantity.parse("8 knot")
SHORT_WATERLINE = Quantity.parse("7.62 m")  # 25 ft
LONG_WATERLINE = Quantity.parse("12.19 m")  # 40 ft


def _screen(waterline_length: Quantity) -> Scorecard:
    v_hull = hull_speed(waterline_length=waterline_length)
    margin = v_hull.to("knot").magnitude / SCHEDULED_SPEED.to("knot").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "hull speed vs scheduled speed",
                computed=margin,
                required=1.0,
            ),
        )
    )


def screen_short_hull() -> Scorecard:
    """Screen the 25 ft waterline: its hull speed falls short of the 8-knot schedule."""
    return _screen(SHORT_WATERLINE)


def screen_long_hull() -> Scorecard:
    """Screen the 40 ft waterline: the longer hull clears the schedule efficiently."""
    return _screen(LONG_WATERLINE)


def main() -> None:
    print("short waterline (25 ft):")
    print(screen_short_hull())
    print("\nlong waterline (40 ft):")
    print(screen_long_hull())


if __name__ == "__main__":
    main()
