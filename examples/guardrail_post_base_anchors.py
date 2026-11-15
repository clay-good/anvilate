"""Worked example: the two anchors a hand on a guardrail pulls out of the slab.

29 CFR 1910.29(b)(3) applies 200 lbf to a guardrail's top rail in any direction at any
point. That is a hand. It arrives at the post base as a moment, and the moment arrives at
the anchors as tension.

A 1,070 mm post on a four-bolt base plate at **150 mm** centres puts **3,098 N** into
each of the two windward anchors — three kilonewtons, from a hand. The post's own weight
contributes almost nothing: 300 N at the pattern's centre resists **2.4%** of the
overturning moment, so the anchors carry essentially the whole of it. The shear is the
easy part, **222 N** in each of the four.

The lever is the anchor spacing and nothing else, so the repair is the pattern. Opening
the bolts to **300 mm** takes the tension to **1,512 N** — a shade better than half —
without changing the post, the rail or the plate.

Two bolts instead of four is where this gets sharp. **Along** the load they take
**6,196 N** each, double the four-bolt figure, because only one is ever in tension.
**Across** it they take nothing at all, and the screen refuses rather than returning a
number: two anchors on one line cannot resist a moment about that line. A two-bolt base
plate is a detail that works or is a mechanism depending on which way it is turned, and
nothing on the drawing says which.

The example reports the tension at three spacings, the weight's share of the resistance,
and what the two-bolt patterns do.

Run it directly (``python examples/guardrail_post_base_anchors.py``);
:func:`guardrail_post_base_anchors` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import anchor_pattern_demand
from anvilate.analysis.anchorage import AnchorageDemand, AnchorPosition
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

#: 29 CFR 1910.29(b)(3): 200 lbf in any downward or outward direction at any point.
TOP_RAIL_FORCE = Q("200 lbf")
#: 1910.29(b)(1) puts the top rail 42 in (1,070 mm) above the walking surface.
POST_HEIGHT = Q("1070 mm")
#: A tube post, its base plate and the grout under it.
POST_WEIGHT = Q("300 N")


def _at(tag: str, x: float, y: float) -> AnchorPosition:
    return AnchorPosition(tag=tag, x=Q(f"{x} mm"), y=Q(f"{y} mm"))


def square_pattern(spacing_mm: float) -> tuple[AnchorPosition, ...]:
    """Four anchors on a square of ``spacing_mm`` centres."""
    half = spacing_mm / 2
    return (
        _at("front_left", -half, -half),
        _at("front_right", -half, half),
        _at("back_left", half, -half),
        _at("back_right", half, half),
    )


def demand(anchors: tuple[AnchorPosition, ...]) -> AnchorageDemand:
    """The clause load on that pattern, pushing outward across the rail."""
    return anchor_pattern_demand(
        anchors=anchors,
        weight=POST_WEIGHT,
        lateral_force=TOP_RAIL_FORCE,
        height=POST_HEIGHT,
        direction=(1.0, 0.0),
    )


def two_bolts_along() -> AnchorageDemand:
    """Two anchors in line with the load, 150 mm apart: only one is ever in tension."""
    return demand((_at("front", -75, 0), _at("back", 75, 0)))


def two_bolts_across() -> str:
    """Two anchors across the load, which resist no moment at all: the refusal, in words."""
    try:
        demand((_at("left", 0, -75), _at("right", 0, 75)))
    except RefusalError as refused:
        return str(refused)
    raise AssertionError("a pattern on one line across the load must be refused")


def guardrail_post_base_anchors() -> dict[str, float]:
    """The figures this example's prose turns on."""
    tight, wide = demand(square_pattern(150)), demand(square_pattern(300))
    pair = two_bolts_along()
    return {
        "tension_at_150_n": tight.governing.tension.to("N").magnitude,
        "tension_at_200_n": demand(square_pattern(200)).governing.tension.to("N").magnitude,
        "tension_at_300_n": wide.governing.tension.to("N").magnitude,
        "shear_each_n": tight.governing.shear.to("N").magnitude,
        "weight_share_percent": 100.0 * tight.stability_ratio,
        "two_bolt_tension_n": pair.governing.tension.to("N").magnitude,
        "wide_over_tight": wide.governing.tension.to("N").magnitude
        / tight.governing.tension.to("N").magnitude,
    }


def main() -> None:
    for spacing in (150, 200, 300):
        result = demand(square_pattern(spacing))
        print(f"--- four anchors at {spacing} mm")
        print(f"  {result}")
        for anchor in result.anchors:
            print(f"    {anchor}")
    print()
    print(f"--- two anchors along the load\n  {two_bolts_along()}")
    print(f"--- two anchors across the load\n  refused: {two_bolts_across()}")
    print()
    for name, value in guardrail_post_base_anchors().items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
