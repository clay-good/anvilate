"""Worked example: the O-ring groove that seals, then blows out.

A hydraulic cap seals with a 3.53 mm (AS568-2xx) O-ring. The designer sizes the gland
depth carefully -- 2.79 mm, a textbook 21 % squeeze, comfortably in the 15-30 % static
band -- and the seal works on the test bench. The squeeze check passes at a safety factor
of 1.40 over the 15 % floor. It looks like a good gland.

But the groove was cut narrow, 3.8 mm wide, to save space. Squeeze fixes the *depth*;
it says nothing about the *width*, and the width sets how much of the groove the rubber
fills. Here the ring already occupies 92 % of the groove cross-section, past the 90 %
ceiling. Rubber is nearly incompressible, so when the ring warms with the fluid and swells
a few percent it has nowhere to go: it is forced into the extrusion gap and shaves off,
and the seal that passed on the bench blows out in service. The fill check fails at 0.97.

The lesson is that an O-ring groove has two independent dimensions and two independent
checks. Depth sets squeeze (sealing contact); width sets fill (room to swell). A gland can
pass one and fail the other, and squeezing correctly is no guarantee the groove is wide
enough. The fix here is not a shallower groove -- that would spoil the good squeeze -- but
a *wider* one: opening the groove to 4.7 mm drops the fill to 75 %, in band, while the
squeeze is untouched.

Run it directly (``python examples/o_ring_gland_fill.py``);
:func:`screen_gland` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import o_ring
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

CROSS_SECTION = Quantity.parse("3.53 mm")
GLAND_DEPTH = Quantity.parse("2.79 mm")  # sets a 21% squeeze
NARROW_GROOVE_WIDTH = Quantity.parse("3.8 mm")  # cut narrow to save space
WIDE_GROOVE_WIDTH = Quantity.parse("4.7 mm")  # the fix
MIN_SQUEEZE = 0.15
MAX_FILL = 0.90


def _screen(groove_width: Quantity) -> Scorecard:
    squeeze = o_ring.o_ring_squeeze_fraction(
        cross_section_diameter=CROSS_SECTION, gland_depth=GLAND_DEPTH
    )
    fill = o_ring.o_ring_gland_fill_fraction(
        cross_section_diameter=CROSS_SECTION, gland_depth=GLAND_DEPTH, groove_width=groove_width
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "squeeze vs 15% floor",
                computed=squeeze / MIN_SQUEEZE,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "gland fill vs 90% ceiling",
                computed=MAX_FILL / fill,
                required=1.0,
            ),
        )
    )


def screen_gland() -> Scorecard:
    """Screen the narrow groove: correct squeeze, but overfilled and prone to extrude."""
    return _screen(NARROW_GROOVE_WIDTH)


def screen_widened_gland() -> Scorecard:
    """Screen the widened groove: same squeeze, fill now back in band."""
    return _screen(WIDE_GROOVE_WIDTH)


def main() -> None:
    print("narrow groove (3.8 mm):")
    print(screen_gland())
    print("\nwidened groove (4.7 mm):")
    print(screen_widened_gland())


if __name__ == "__main__":
    main()
