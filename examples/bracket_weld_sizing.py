"""Worked example: the default fillet that couldn't.

A bracket transfers a 100 kN shear into a column through a fillet weld 120 mm
long. The drawing carries the shop's habitual 5 mm fillet, but habit is not a
calculation: on the effective throat (0.707 x 5 mm) that load runs 236 MPa
against the 290 MPa allowable for an E70 electrode, a safety factor of only 1.23
where the connection wants 2.0. Inverting the throat-shear check for the same
load and length shows the weld actually needs about an 8 mm leg, so a 10 mm
fillet (two passes) carries it comfortably at 2.46. A fillet size is something
you size, not something you default; the throat is small, and 0.707 of a guess
is a smaller guess.

Run it directly (``python examples/bracket_weld_sizing.py``);
:func:`screen_bracket_weld` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    fillet_weld_leg_for_load,
    fillet_weld_throat_stress,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

LOAD = Quantity.parse("100 kN")
WELD_LENGTH = Quantity.parse("120 mm")
ALLOWABLE_SHEAR = Quantity.parse("290 MPa")  # 0.6 * E70 electrode (F_EXX = 483 MPa)
REQUIRED_SF = 2.0
AS_DRAWN_LEG = Quantity.parse("5 mm")  # the shop default
REVISED_LEG = Quantity.parse("10 mm")  # two passes


def required_leg() -> Quantity:
    """The exact fillet leg the load and length need at the design margin."""
    return fillet_weld_leg_for_load(
        force=LOAD,
        length=WELD_LENGTH,
        allowable_shear=ALLOWABLE_SHEAR,
        required_safety_factor=REQUIRED_SF,
    )


def screen_bracket_weld() -> Scorecard:
    """Screen the throat shear of the as-drawn 5 mm fillet and the revised 10 mm
    one against the E70 allowable."""
    entries = []
    for name, leg in (
        ("5 mm fillet (as drawn)", AS_DRAWN_LEG),
        ("10 mm fillet (revised)", REVISED_LEG),
    ):
        stress = fillet_weld_throat_stress(force=LOAD, leg_size=leg, length=WELD_LENGTH)
        entries.append(
            strength_scorecard(
                f"{name} throat shear",
                stress=stress,
                allowable=ALLOWABLE_SHEAR,
                required=REQUIRED_SF,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    print(f"required fillet leg: {required_leg().to('mm')}")
    card = screen_bracket_weld()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
