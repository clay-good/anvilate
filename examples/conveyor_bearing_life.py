"""Worked example: the bearing that fit but wore out.

A conveyor pulley carries a 4 kN radial load on its bearing and turns at 900 rpm,
around the clock. The maintenance target is 30,000 hours of service (about three
and a half years continuous) before the bearing is changed out. The bearing that
drops onto the shaft seat, a 6208 rated at 29.6 kN dynamic capacity, is the
obvious pick -- and it lasts barely 7,500 hours, a quarter of the target.

The ISO 281 basic rating life goes as (C/P) cubed for a ball bearing, so life is
brutally sensitive to the margin between the dynamic capacity C and the load P.
Stepping up to the medium 6308 (42.3 kN) triples the life to ~22,000 hours --
closer, but still short. Only the heavy 6310 (61.8 kN), with more than 15x the
load margin in life terms, clears 30,000 hours. The lesson is the exponent: you
do not buy bearing life a little at a time, you buy it in cubes, so the first
bearing that fits is rarely the one that lasts.

The dynamic load ratings are catalogue values (manufacturer- and design-specific,
so declared inline rather than read from the ISO 15 boundary-dimension table).

Run it directly (``python examples/conveyor_bearing_life.py``);
:func:`screen_pulley_bearing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import bearing_life_hours
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

RADIAL_LOAD = Quantity.parse("4 kN")
SPEED = Quantity.parse("900 rpm")
REQUIRED_LIFE = Quantity.parse("30000 hour")

# (designation, catalogue dynamic load rating C) -- inline catalogue inputs.
CANDIDATES = (
    ("6208 (light)", Quantity.parse("29.6 kN")),
    ("6308 (medium)", Quantity.parse("42.3 kN")),
    ("6310 (heavy)", Quantity.parse("61.8 kN")),
)


def life_hours(dynamic_load_rating: Quantity) -> Quantity:
    """The L10 life in hours of a candidate bearing under the pulley duty."""
    return bearing_life_hours(
        dynamic_load_rating=dynamic_load_rating,
        equivalent_load=RADIAL_LOAD,
        speed=SPEED,
    )


def screen_pulley_bearing() -> Scorecard:
    """Screen each candidate bearing's L10 life against the 30,000-hour target
    (the safety factor is the life margin, life / required life)."""
    required = REQUIRED_LIFE.to("hour").magnitude
    entries = []
    for name, rating in CANDIDATES:
        margin = life_hours(rating).to("hour").magnitude / required
        entries.append(ScorecardEntry.from_safety_factor(name, computed=margin, required=1.0))
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_pulley_bearing()
    for (_name, rating), entry in zip(CANDIDATES, card.entries, strict=True):
        print(f"{entry}  ->  L10 {life_hours(rating).to('hour').magnitude:.0f} h")
    print(card)


if __name__ == "__main__":
    main()
