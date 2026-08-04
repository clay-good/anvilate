"""Worked example: a retaining wall declared once, screened into a stability scorecard.

The geotechnical pack's retaining-wall screen is the external-stability check as the library does
everything — declare the wall and its backfill once, get back a scorecard, not two loose ratios,
with overturning and sliding each named, cited, and PASS or FAIL. This example screens two walls
retaining the same kind of backfill: a well-proportioned one that passes both checks comfortably,
and an under-built one — taller backfill, less stabilizing weight, a slicker base — that fails both
overturning and sliding at once. The scorecard reports the whole verdict together, so the failure
isn't a single number you have to interpret but a clear, reviewable result.

Run it directly (``python examples/retaining_wall_scorecard.py``);
:func:`wall_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.geotechnical import RetainingWall, screen_retaining_wall
from anvilate.units import Quantity


def wall_scorecards() -> dict[str, str]:
    """Return the scorecard status for a well-proportioned wall and an under-built one."""
    good = RetainingWall(
        retained_height=Quantity.parse("4 m"),
        backfill_unit_weight=Quantity.parse("18 kN/m**3"),
        backfill_friction_angle=30.0,
        vertical_load=Quantity.parse("200 kN/m"),
        load_arm=Quantity.parse("1.6 m"),
        base_friction_coefficient=0.5,
    )
    weak = RetainingWall(
        retained_height=Quantity.parse("5 m"),
        backfill_unit_weight=Quantity.parse("19 kN/m**3"),
        backfill_friction_angle=28.0,
        vertical_load=Quantity.parse("150 kN/m"),
        load_arm=Quantity.parse("1.2 m"),
        base_friction_coefficient=0.45,
    )
    good_card = screen_retaining_wall(good)
    weak_card = screen_retaining_wall(weak)
    return {
        "good_status": good_card.status.value,
        "weak_status": weak_card.status.value,
        "weak_failures": ", ".join(e.name for e in weak_card.failures()),
    }


def main() -> None:
    w = wall_scorecards()
    print(f"well-proportioned wall : {w['good_status'].upper()}")
    print(f"under-built wall       : {w['weak_status'].upper()} (fails: {w['weak_failures']})")
    print("  -> declare the wall once; overturning and sliding come back cited and pass/fail")


if __name__ == "__main__":
    main()
