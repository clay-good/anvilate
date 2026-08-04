"""Worked example: a masonry wall declared once, screened into a TMS 402 scorecard.

The masonry pack turns a wall check into the reviewable pass/fail the rest of the library produces:
declare the wall's specified strength, slenderness, and the axial and out-of-plane bending stresses
once, and get back a scorecard with the gravity-only axial check and the combined axial-plus-flexure
unity check each named, cited to its TMS 402 clause, and PASS or FAIL. This example screens the same
wall under two wind conditions: a light-wind case that passes both checks, and a design-wind case
whose gravity axial stress still passes comfortably but whose combined unity check tips over 1.0 and
fails — the interaction the pack exists to catch, reported as one scorecard rather than two loose
utilizations.

Run it directly (``python examples/masonry_wall_scorecard.py``);
:func:`wall_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.masonry import MasonryWall, screen_masonry_wall
from anvilate.units import Quantity


def wall_scorecards() -> dict[str, str]:
    """Return the scorecard status for the wall under light wind and under design wind."""
    light_wind = MasonryWall(
        masonry_strength=Quantity.parse("10 MPa"),
        slenderness_ratio=40.0,
        axial_stress=Quantity.parse("1.2 MPa"),
        flexural_stress=Quantity.parse("0.5 MPa"),
    )
    design_wind = MasonryWall(
        masonry_strength=Quantity.parse("10 MPa"),
        slenderness_ratio=40.0,
        axial_stress=Quantity.parse("1.2 MPa"),
        flexural_stress=Quantity.parse("2.2 MPa"),
    )
    light_card = screen_masonry_wall(light_wind)
    design_card = screen_masonry_wall(design_wind)
    return {
        "light_status": light_card.status.value,
        "design_status": design_card.status.value,
        "design_failures": ", ".join(e.name for e in design_card.failures()),
    }


def main() -> None:
    w = wall_scorecards()
    print(f"light wind  : {w['light_status'].upper()}")
    print(f"design wind : {w['design_status'].upper()} (fails: {w['design_failures']})")
    print("  -> gravity axial passes either way; the combined-with-wind unity check governs")


if __name__ == "__main__":
    main()
