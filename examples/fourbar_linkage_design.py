"""Worked example: the linkage that turned freely but pushed badly.

A crank-rocker linkage drives an oscillating output — a wiper arm, a feeder paddle
— from a continuously turning input crank. Getting the input to rotate all the way
round is the easy half: any Grashof linkage with the crank as its shortest link
does that. The hard half is transmitting force cleanly through the whole turn.

Force transmission is measured by the transmission angle, the angle between the
coupler and the output link. Near 90 degrees the coupler force becomes output
torque; as it swings toward 0 or 180 the linkage binds, the bearings load up, and
the output stalls. Good practice keeps the transmission angle above 45 degrees
everywhere in the cycle.

Both candidates here are proper crank-rockers, so both turn. The long-coupler
design looks tidy but its transmission angle collapses to 21 degrees at one crank
position (a 0.46 margin against the 45 degree floor) — it will bind there. Rebalancing
the coupler and output lengths lifts the worst-case angle to 48 degrees (1.07) and
the linkage pushes cleanly all the way round. Rotatability is necessary but not
sufficient; the transmission angle is what decides whether the mechanism works.

Run it directly (``python examples/fourbar_linkage_design.py``);
:func:`screen_fourbar_linkage` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import fourbar_transmission_angle, fourbar_type
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity

MIN_TRANSMISSION_ANGLE = 45.0  # degrees

CANDIDATES = {
    "long-coupler crank-rocker": (
        Quantity.parse("100 mm"),  # ground
        Quantity.parse("28 mm"),  # input (shortest -> crank)
        Quantity.parse("108 mm"),  # coupler
        Quantity.parse("40 mm"),  # output
    ),
    "balanced crank-rocker": (
        Quantity.parse("100 mm"),
        Quantity.parse("30 mm"),
        Quantity.parse("90 mm"),
        Quantity.parse("80 mm"),
    ),
}


def worst_transmission_angle(links: tuple[Quantity, Quantity, Quantity, Quantity]) -> float:
    """The transmission angle furthest from 90 deg over a full input turn (deg),
    sampled at one-degree steps -- the binding-risk worst case."""
    ground, input_link, coupler, output_link = links
    worst = 90.0
    angle = 0
    while angle < 360:
        mu = fourbar_transmission_angle(
            ground=ground,
            input_link=input_link,
            coupler=coupler,
            output_link=output_link,
            input_angle=float(angle),
        )
        # Track whichever extreme (low or high) is closest to a bind.
        deviation = min(mu, 180.0 - mu)
        if deviation < min(worst, 180.0 - worst):
            worst = mu
        angle += 1
    return worst


def screen_fourbar_linkage() -> Scorecard:
    """Screen each candidate: it must be a crank-rocker AND keep its worst-case
    transmission angle above the 45 deg floor (safety factor = worst / floor)."""
    entries = []
    for name, links in CANDIDATES.items():
        ground, input_link, coupler, output_link = links
        kind = fourbar_type(
            ground=ground, input_link=input_link, coupler=coupler, output_link=output_link
        )
        if kind != "crank-rocker":
            entries.append(
                ScorecardEntry(
                    name=f"{name} is a crank-rocker",
                    status=CheckStatus.FAIL,
                    detail=f"classified as {kind}, not crank-rocker",
                )
            )
            continue
        worst = worst_transmission_angle(links)
        deviation = min(worst, 180.0 - worst)
        entries.append(
            ScorecardEntry.from_safety_factor(
                name, computed=deviation / MIN_TRANSMISSION_ANGLE, required=1.0
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, links in CANDIDATES.items():
        print(f"{name}: worst transmission angle {worst_transmission_angle(links):.0f} deg")
    print(screen_fourbar_linkage())


if __name__ == "__main__":
    main()
