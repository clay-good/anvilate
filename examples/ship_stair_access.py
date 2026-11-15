"""Worked example: the ship stair that is legal as a ship stair and not as a stair.

A tank farm needs access to a valve platform and there is no room for a standard stair.
The fabricator draws a steep one: 60 degrees, 150 mm treads, 500 mm wide, with 2.1 m of
headroom and a 900 mm landing. Under 29 CFR 1910.25 that geometry is **three separate
violations** as a standard stair — too steep, treads too shallow, too narrow — and
**compliant** as a ship stair, which is a different paragraph with different numbers.

So `kind` is a declaration and not a detail. The same steel, screened twice, comes out
of the two paragraphs with opposite verdicts, and the card says which one it read.

What the ship-stair paragraph does *not* relax is (b): headroom, landings and the load
rule apply to every stair. The stair here fails one of them, and it is the one nobody
checks: (b)(6) asks for five times the anticipated live load **and never less than the
concentrated load it floors at**, and a lightly loaded access stair sized on the first
half alone misses the second. These treads take the five-times requirement with room to
spare and fall short of the floor.

The example reports the standard-stair violation count, the ship-stair verdict, and the
tread load factor against each half of (b)(6).

Run it directly (``python examples/ship_stair_access.py``);
:func:`ship_stair_access` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.walking_working import (
    LIVE_LOAD_FACTOR,
    MIN_CONCENTRATED_LOAD,
    Regime,
    StairKind,
    StairSystem,
    screen_stair,
)
from anvilate.scorecard import CheckStatus, Scorecard
from anvilate.units import Quantity

Q = Quantity.parse

ANGLE = Q("60 degree")
TREAD_DEPTH = Q("150 mm")
WIDTH = Q("500 mm")
HEADROOM = Q("2100 mm")
LANDING_DEPTH = Q("900 mm")
RISER_HEIGHT = Q("230 mm")
TREAD_CAPACITY = Q("3 kN")
LIVE_LOAD = Q("0.5 kN")


def _stair(kind: StairKind, tread_capacity: Quantity = TREAD_CAPACITY) -> StairSystem:
    return StairSystem(
        regime=Regime.GENERAL_INDUSTRY,
        kind=kind,
        angle=ANGLE,
        riser_height=RISER_HEIGHT,
        tread_depth=TREAD_DEPTH,
        width=WIDTH,
        headroom=HEADROOM,
        tread_capacity=tread_capacity,
        anticipated_live_load=LIVE_LOAD,
        landing_depth=LANDING_DEPTH,
    )


def as_a_standard_stair() -> Scorecard:
    """The same geometry read against 1910.25(c), which is not what it is."""
    return screen_stair(_stair(StairKind.STANDARD))


def as_a_ship_stair() -> Scorecard:
    """The same geometry read against 1910.25(e), which is."""
    return screen_stair(_stair(StairKind.SHIP))


def with_a_stronger_tread() -> Scorecard:
    """The ship stair with treads that carry the clause's concentrated-load floor."""
    return screen_stair(_stair(StairKind.SHIP, tread_capacity=Q("5 kN")))


def ship_stair_access() -> dict[str, float]:
    """The figures this example's prose turns on."""
    standard, ship, stronger = as_a_standard_stair(), as_a_ship_stair(), with_a_stronger_tread()
    geometry = ("stair angle", "stair tread depth", "stair width")

    def of(card: Scorecard, name: str):
        return next(entry for entry in card.entries if entry.name == name)

    return {
        "standard_geometry_failures": float(
            sum(1 for name in geometry if of(standard, name).status is CheckStatus.FAIL)
        ),
        "ship_geometry_failures": float(
            sum(1 for name in geometry if of(ship, name).status is CheckStatus.FAIL)
        ),
        "tread_factor_against_five_times": TREAD_CAPACITY.to("N").magnitude
        / (LIVE_LOAD.to("N").magnitude * LIVE_LOAD_FACTOR),
        "tread_factor_against_the_floor": of(ship, "stair tread load").safety_factor,
        "floor_kn": MIN_CONCENTRATED_LOAD.to("kN").magnitude,
        "ship_fails": float(ship.status is CheckStatus.FAIL),
        "stronger_passes": float(stronger.status is CheckStatus.PASS),
    }


def main() -> None:
    for label, card in (
        ("read as a standard stair", as_a_standard_stair()),
        ("read as a ship stair", as_a_ship_stair()),
        ("ship stair, stronger treads", with_a_stronger_tread()),
    ):
        print(f"--- {label}")
        print(card)
        for entry in card.entries:
            print(f"[{entry.status.name}] {entry.name}: {entry.detail}")
        print()
    for name, value in ship_stair_access().items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
