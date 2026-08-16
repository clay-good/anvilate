"""Worked example: the double-slit bench whose fringes are too fine to read.

A teaching lab measures a helium-neon laser's wavelength (633 nm) with a double slit. The slide has
its two slits 0.5 mm apart, and the screen sits 1 m away. Young's law puts the bright fringes a
distance dy = lambda*L/d = 633e-9 * 1 / 0.5e-3 = 1.27 mm apart. The lab rule is that a fringe
pattern
is only readable when the bands are at least 2 mm apart -- closer than that and a student cannot
count them cleanly against a millimetre ruler. At 1.27 mm the pattern fails that check, a safety
factor of 0.63, and the measured wavelength comes out noisy.

The fix costs nothing but bench length: fringe spacing grows in direct proportion to the screen
distance, so moving the screen out to 2 m doubles the spacing to 2.53 mm -- a safety factor of 1.27,
now comfortably readable. Nothing about the slits or the laser changed; the pattern was simply
projected onto a longer lever arm.

The lesson is that a two-slit measurement trades bench length for fringe legibility: with the slit
separation and wavelength fixed, push the screen back until dy = lambda*L/d clears whatever your
detector (eye, ruler, or camera) can resolve, and the same setup that read noisy reads clean.

Run it directly (``python examples/double_slit_wavelength_bench.py``);
:func:`screen_short_bench` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import double_slit_fringe_spacing
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

WAVELENGTH = Quantity.parse("633 nm")
SLIT_SEPARATION = Quantity.parse("0.5 mm")
READABLE_FRINGE_SPACING = Quantity.parse("2 mm")
SHORT_SCREEN_DISTANCE = Quantity.parse("1 m")
LONG_SCREEN_DISTANCE = Quantity.parse("2 m")


def _screen(screen_distance: Quantity) -> Scorecard:
    spacing = double_slit_fringe_spacing(
        wavelength=WAVELENGTH,
        slit_separation=SLIT_SEPARATION,
        screen_distance=screen_distance,
    )
    margin = spacing.to("mm").magnitude / READABLE_FRINGE_SPACING.to("mm").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "fringe spacing vs readable limit",
                computed=margin,
                required=1.0,
            ),
        )
    )


def screen_short_bench() -> Scorecard:
    """Screen the 1 m bench: the fringes are too fine to read cleanly."""
    return _screen(SHORT_SCREEN_DISTANCE)


def screen_long_bench() -> Scorecard:
    """Screen the 2 m bench: the wider fringes clear the readable limit."""
    return _screen(LONG_SCREEN_DISTANCE)


def main() -> None:
    print("1 m screen distance:")
    print(screen_short_bench())
    print("\n2 m screen distance:")
    print(screen_long_bench())


if __name__ == "__main__":
    main()
