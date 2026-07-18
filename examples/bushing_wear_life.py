"""Worked example: the bushing that wears out on lubrication, not load.

A bronze plain bushing carries an 800 N radial load on a 25 mm shaft turning at 50 rpm, and
it must last an 8,000-hour maintenance interval before the wear opens its clearance past the
0.25 mm the machine tolerates. Nothing about this is a strength problem -- the bearing
pressure is a gentle 1.1 MPa, nowhere near crushing the bronze. It is a *wear* problem, and
wear answers to Archard's law: the depth worn is K·p·s/H, driven by how far the surfaces
slide (2,800 km over 8,000 hours here) and, above all, by the wear coefficient K that lumps
in the lubrication.

At a marginal boundary-lubricated K of 1e-7 the bushing reaches its 0.25 mm wear allowance
after only 1,400 km of sliding -- three quarters of the way through the interval, a safety
factor of 0.75 -- and it is worn out before its first scheduled service. The fix is not a
bigger shaft or a stronger bronze; the pressure was never the issue. It is a *better film*:
improving the lubrication to halve the wear coefficient to 5e-8 doubles the life to 2,800 km,
clearing the interval at a safety factor of 1.49.

The lesson is that sliding-wear life is dominated by the wear coefficient -- the tribology of
the pair and its lubrication -- far more than by the load. K spans four orders of magnitude
from dry to well-lubricated, so it, not the bearing pressure, is the number that decides
whether a bushing reaches its service interval. Wear is designed by the film, and Archard's
law is an order-of-magnitude screen for ranking that choice, not a precise life.

Run it directly (``python examples/bushing_wear_life.py``);
:func:`screen_bushing` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import sliding_distance_for_wear_depth
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

SHAFT_DIAMETER = Quantity.parse("25 mm")
BUSHING_LENGTH = Quantity.parse("30 mm")
RADIAL_LOAD = Quantity.parse("800 N")
SPEED = Quantity.parse("50 rpm")
HARDNESS = Quantity.parse("600 MPa")  # bronze
ALLOWABLE_WEAR = Quantity.parse("0.25 mm")
SERVICE_HOURS = 8000.0

MARGINAL_WEAR_COEFFICIENT = 1e-7  # boundary lubrication
IMPROVED_WEAR_COEFFICIENT = 5e-8  # a better film


def _bearing_pressure() -> Quantity:
    """The projected bearing pressure p = F/(d*L)."""
    area_mm2 = SHAFT_DIAMETER.to("mm").magnitude * BUSHING_LENGTH.to("mm").magnitude
    return Quantity(magnitude=RADIAL_LOAD.to("N").magnitude / area_mm2, unit="MPa")


def _required_sliding_distance() -> float:
    """The sliding distance (m) the surface travels over the service interval."""
    circumference = pi * SHAFT_DIAMETER.to("m").magnitude
    revolutions = SPEED.to("rpm").magnitude * 60.0 * SERVICE_HOURS
    return circumference * revolutions


def _screen(wear_coefficient: float) -> Scorecard:
    life_distance = sliding_distance_for_wear_depth(
        wear_coefficient=wear_coefficient,
        contact_pressure=_bearing_pressure(),
        hardness=HARDNESS,
        allowable_depth=ALLOWABLE_WEAR,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "wear life vs service interval",
                computed=life_distance.to("m").magnitude / _required_sliding_distance(),
                required=1.0,
            ),
        )
    )


def screen_bushing() -> Scorecard:
    """Screen the marginally-lubricated bushing: it wears out before its service."""
    return _screen(MARGINAL_WEAR_COEFFICIENT)


def screen_better_lubricated_bushing() -> Scorecard:
    """Screen the better-lubricated bushing: halving the wear coefficient doubles the life."""
    return _screen(IMPROVED_WEAR_COEFFICIENT)


def main() -> None:
    print(f"bearing pressure: {_bearing_pressure().to('MPa').magnitude:.2f} MPa")
    print("marginal lubrication (K = 1e-7):")
    print(screen_bushing())
    print("\nbetter film (K = 5e-8):")
    print(screen_better_lubricated_bushing())


if __name__ == "__main__":
    main()
