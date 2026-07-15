"""Worked example: the bolt that passed on the wrong area.

An M12 x 1.75 class-8.8 bracket bolt carries a 38 kN external tension. Sized
the quick way — force over the nominal shank area (pi/4 * d^2 = 113 mm^2) — the
axial stress reads 336 MPa against the 580 MPa proof strength, a tidy SF 1.7,
and the bolt is signed off. But a threaded bolt does not neck down to failure
on its shank; it fails through the threads, on the smaller ISO 898 tensile
stress area A_t = (pi/4)(d - 0.9382*P)^2 = 84.3 mm^2. On that area the same
38 kN works at 451 MPa — SF 1.29, under the 1.5 requirement. Same bolt, same
load; the only difference is which area the tension is spread over, and the
threads are where it counts. The fix is the correct area, not a bigger bolt (a
size up would pass on both) — the point is that the shank-area screen is not
conservative, it is wrong.

Run it directly (``python examples/bolt_tension_thread_area.py``);
:func:`screen_bolt_tension` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    axial_stress,
    bolt_axial_stress,
    circular_area,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

TENSION = Quantity.parse("38 kN")
NOMINAL_DIAMETER = Quantity.parse("12 mm")  # M12
PITCH = Quantity.parse("1.75 mm")  # M12 coarse (from the standards thread table)
PROOF_STRENGTH = Quantity.parse("580 MPa")  # ISO 898-1 property class 8.8
REQUIRED_SF = 1.5


def screen_bolt_tension() -> Scorecard:
    """Screen the bolt tension two ways: over the nominal shank area (the quick,
    wrong way) and over the ISO 898 tensile stress area (the threads that fail)."""
    shank_stress = axial_stress(force=TENSION, area=circular_area(NOMINAL_DIAMETER))
    thread_stress = bolt_axial_stress(
        tension=TENSION, nominal_diameter=NOMINAL_DIAMETER, pitch=PITCH
    )
    return Scorecard(
        entries=(
            strength_scorecard(
                "shank-area tension (nominal)",
                stress=shank_stress,
                allowable=PROOF_STRENGTH,
                required=REQUIRED_SF,
            ),
            strength_scorecard(
                "tensile-area tension (threads)",
                stress=thread_stress,
                allowable=PROOF_STRENGTH,
                required=REQUIRED_SF,
            ),
        )
    )


def main() -> None:
    card = screen_bolt_tension()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
