"""Worked example: the gear pair that is a geometry problem before a strength one.

A 2:1 spur reduction has to fit a fixed 54 mm shaft-centre distance. Two tooth-count choices
both land exactly on that centre, and the tempting one is the coarse pinion: 12 teeth on the
pinion, 24 on the gear, which at a 54 mm centre needs a chunky 3 mm module. Big teeth look
strong, and the layout closes.

It undercuts. Below about 18 teeth a standard 20-degree pinion cannot be cut without the
hob gouging into the tooth flank near the root -- the *undercut* that thins the tooth base
exactly where the bending stress is highest, weakening the very teeth the coarse module was
supposed to strengthen. The 12-tooth pinion sits at a safety factor of 0.67 against the
18-tooth minimum, so the coarse-module layout is self-defeating: it buys big teeth and then
undercuts them.

The fix is the opposite of the instinct: *more, finer* teeth. Holding the same 54 mm centre
and 2:1 ratio with a 20-tooth pinion (40-tooth gear) drops the module to 1.8 mm and clears
the undercut minimum at a safety factor of 1.11. The teeth are smaller but whole, and a whole
smaller tooth beats a gouged bigger one. The lesson is that a gear pair is a geometry problem
before it is a strength problem: the centre distance and ratio fix a module-versus-tooth-count
trade, and the pinion must clear the undercut minimum first -- checking tooth stress on an
undercut pinion is checking the strength of a tooth that was never fully there.

Run it directly (``python examples/gear_pair_layout.py``);
:func:`screen_pinion` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    gear_center_distance,
    gear_module_for_center_distance,
    minimum_teeth_to_avoid_undercut,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

CENTER_DISTANCE = Quantity.parse("54 mm")
RATIO = 2  # gear teeth / pinion teeth
PRESSURE_ANGLE = 20.0

COARSE_PINION_TEETH = 12  # tempting big teeth
FINE_PINION_TEETH = 20  # the fix


def _screen(pinion_teeth: int) -> Scorecard:
    gear_teeth = RATIO * pinion_teeth
    # The fixed centre distance and tooth counts pin the module.
    module = gear_module_for_center_distance(
        center_distance=CENTER_DISTANCE, pinion_teeth=pinion_teeth, gear_teeth=gear_teeth
    )
    # Sanity: that module does put the pair on the target centre.
    assert gear_center_distance(module=module, pinion_teeth=pinion_teeth, gear_teeth=gear_teeth).to(
        "mm"
    ).magnitude == round(CENTER_DISTANCE.to("mm").magnitude, 6)
    min_teeth = minimum_teeth_to_avoid_undercut(pressure_angle=PRESSURE_ANGLE)
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "pinion teeth vs undercut minimum",
                computed=pinion_teeth / min_teeth,
                required=1.0,
            ),
        )
    )


def screen_pinion() -> Scorecard:
    """Screen the coarse 12-tooth pinion: it fits the centre but undercuts."""
    return _screen(COARSE_PINION_TEETH)


def screen_finer_pinion() -> Scorecard:
    """Screen the finer 20-tooth pinion: same centre and ratio, clear of undercut."""
    return _screen(FINE_PINION_TEETH)


def main() -> None:
    for label, teeth in (
        ("coarse (12-tooth)", COARSE_PINION_TEETH),
        ("fine (20-tooth)", FINE_PINION_TEETH),
    ):
        module = gear_module_for_center_distance(
            center_distance=CENTER_DISTANCE, pinion_teeth=teeth, gear_teeth=RATIO * teeth
        )
        print(f"{label}: module {module.to('mm').magnitude:.2f} mm")
    print("\ncoarse 12-tooth pinion:")
    print(screen_pinion())
    print("\nfiner 20-tooth pinion:")
    print(screen_finer_pinion())


if __name__ == "__main__":
    main()
