"""Worked example: the flip-top hinge that cracks after a week.

A polypropylene shampoo cap flips open on a moulded living hinge. As first drawn the hinge
is a short, sharp web -- 0.4 mm thick and only 1.2 mm long -- because a tight crease looks
clean on the model. Folded flat to open, that web stretches its outer fibre to 52 % strain
(ε = π·t/(2·L) for a 180-degree fold). Polypropylene is the living-hinge material precisely
because it shrugs off high fold strain, but 52 % is past even its repeated-flex allowable of
about 30 %: a safety factor of 0.57. The cap opens fine on the sample and whitens, crazes,
and tears through after a few hundred flips in a bathroom.

The strain is set by the *geometry of the fold*, and the only knobs are the web's thickness
and its length. Thinning the web helps but there is a moulding floor to how thin it can fill;
the real fix is a *longer* web. Stretching it from 1.2 mm to 2.2 mm spreads the same 180-degree
fold over more material, dropping the strain to 29 % -- a safety factor of 1.05, now inside the
allowable. Inverting the strain relation says the web must be at least 2.09 mm long to hold 30 %.

The lesson is that a living hinge is not a crease -- it is a *coined web*, deliberately thin,
wide, and long, and the instinct to make it short and sharp is exactly backwards. Fold strain
falls as the web lengthens, so a hinge that cracks is lengthened (or thinned), never tightened.

Run it directly (``python examples/living_hinge_flip_cap.py``);
:func:`screen_hinge` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import living_hinge_fold_strain
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

WEB_THICKNESS = Quantity.parse("0.4 mm")
AS_DRAWN_WEB_LENGTH = Quantity.parse("1.2 mm")  # short, sharp crease
REDESIGNED_WEB_LENGTH = Quantity.parse("2.2 mm")  # coined, longer web
FOLD_ANGLE = 180.0
PERMISSIBLE_STRAIN = 0.30  # polypropylene, repeated flexing


def _screen(web_length: Quantity) -> Scorecard:
    strain = living_hinge_fold_strain(
        web_thickness=WEB_THICKNESS, web_length=web_length, fold_angle=FOLD_ANGLE
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "fold strain vs PP allowable",
                computed=PERMISSIBLE_STRAIN / strain,
                required=1.0,
            ),
        )
    )


def screen_hinge() -> Scorecard:
    """Screen the short, sharp hinge as first drawn: it over-strains and cracks."""
    return _screen(AS_DRAWN_WEB_LENGTH)


def screen_redesigned_hinge() -> Scorecard:
    """Screen the longer coined web: the same fold now within the flexural allowable."""
    return _screen(REDESIGNED_WEB_LENGTH)


def main() -> None:
    print("as drawn (1.2 mm web):")
    print(screen_hinge())
    print("\nredesigned (2.2 mm web):")
    print(screen_redesigned_hinge())


if __name__ == "__main__":
    main()
