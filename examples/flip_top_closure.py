"""Capstone: a plastic flip-top closure, hinge and latch and thumb together.

One moulded polypropylene shampoo cap has to pass three unrelated checks every time it is
used, and they come from two different feature families. Open it and the *living hinge*
folds flat; close it and the *snap latch* flexes over its lip and catches; and a thumb has
to supply the closing force. A cap that nails one of these can still fail another, so all
three go on one scorecard:

1. **Hinge fold strain** -- the outer-fibre strain when the living hinge folds 180°, against
   polypropylene's repeated-flex allowable.
2. **Latch flex strain** -- the root strain when the snap finger deflects over its lip,
   against the same allowable.
3. **Thumb close force** -- the mating force to push the latch home, against a comfortable
   one-thumb push.

At the chosen geometry all three pass, but not by the same margin, and the pattern is worth
seeing. The latch has a safety factor of 1.42 and the thumb force a roomy 4.31, while the
**hinge fold strain is the tightest at 1.20** -- which makes sense, because the hinge takes
the largest deflection (a full fold) of anything in the part, every single use. The closure
is governed by its hinge, not its latch or its feel.

The lesson is that a multi-feature moulded part is only as good as its worst feature, and on
a flip-top that is almost always the hinge: it flexes furthest and most often. A design pass
checks the hinge, the latch, *and* the hand -- three gates from two feature families on one
piece of polypropylene.

Run it directly (``python examples/flip_top_closure.py``);
:func:`screen_closure` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    living_hinge_fold_strain,
    snap_fit_deflection_force,
    snap_fit_mating_force,
    snap_fit_strain,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

PP_ELASTIC_MODULUS = Quantity.parse("1300 MPa")
PP_PERMISSIBLE_STRAIN = 0.30  # living hinge, full fold, repeated
PP_LATCH_PERMISSIBLE_STRAIN = 0.02  # snap finger, repeated flex

HINGE_WEB_THICKNESS = Quantity.parse("0.35 mm")
HINGE_WEB_LENGTH = Quantity.parse("2.2 mm")

LATCH_LENGTH = Quantity.parse("8 mm")
LATCH_THICKNESS = Quantity.parse("1 mm")
LATCH_WIDTH = Quantity.parse("4 mm")
LATCH_UNDERCUT = Quantity.parse("0.6 mm")
LATCH_INSERTION_ANGLE = 40.0
LATCH_FRICTION = 0.3
THUMB_CLOSE_LIMIT = Quantity.parse("10 N")


def screen_closure() -> Scorecard:
    """Screen the closure on hinge fold strain, latch flex strain, and thumb close force."""
    hinge_strain = living_hinge_fold_strain(
        web_thickness=HINGE_WEB_THICKNESS, web_length=HINGE_WEB_LENGTH
    )
    latch_strain = snap_fit_strain(
        deflection=LATCH_UNDERCUT, length=LATCH_LENGTH, thickness=LATCH_THICKNESS
    )
    deflection_force = snap_fit_deflection_force(
        permissible_strain=latch_strain,
        width=LATCH_WIDTH,
        thickness=LATCH_THICKNESS,
        length=LATCH_LENGTH,
        elastic_modulus=PP_ELASTIC_MODULUS,
    )
    mating_force = snap_fit_mating_force(
        deflection_force=deflection_force,
        insertion_angle=LATCH_INSERTION_ANGLE,
        friction_coefficient=LATCH_FRICTION,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "hinge fold strain",
                computed=PP_PERMISSIBLE_STRAIN / hinge_strain,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "latch flex strain",
                computed=PP_LATCH_PERMISSIBLE_STRAIN / latch_strain,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "thumb close force",
                computed=THUMB_CLOSE_LIMIT.to("N").magnitude / mating_force.to("N").magnitude,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(screen_closure())


if __name__ == "__main__":
    main()
