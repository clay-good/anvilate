"""Worked example: the retrofit that spans two editions of the same code.

An existing 2018 frame was designed to AISC 360-16. A new mezzanine is being hung off
it, and the new members are designed to -22 because that is what the jurisdiction now
adopts. Both sets of numbers land in one evidence bundle, and the bundle reads as though
every clause came from one book.

That is not a mistake to forbid — it is what a retrofit actually is. It is a mistake to
leave *silent*. Three cases:

* **The new work alone.** Every reference names an edition, one standard, one edition:
  a clean pass.
* **The bundle, unwaived.** AISC 360 appears at both -16 and -22 and the screen FAILS,
  naming the standard and both editions. Nothing about the structural checks changed;
  what failed is the claim the bundle was making about itself.
* **The bundle, waived.** The engineer of record records who accepted the mix and why,
  and it passes with the waiver printed in the detail. A waiver with nobody's name on it
  is refused at construction — that would be a suppressed warning, not an accepted risk.

The fourth case is the one this library will not do: work out which edition *your*
jurisdiction adopts. Adoption is a legal question that varies by state, county and city,
changes on schedules nobody publishes centrally, and being confidently wrong about it is
the worst failure available here. You say what you have adopted; the library checks that
the bundle is consistent with what you said.

Run it directly (``python examples/retrofit_two_code_editions.py``);
:func:`screen_retrofit_bundle` is exercised in the test suite.
"""

from __future__ import annotations

from datetime import date

from anvilate.scorecard import Scorecard
from anvilate.standards import DesignBasis, MixedEditionWaiver, design_basis_scorecard

EXISTING_FRAME = ["AISC 360-16 §D2", "AISC 360-16 §H1.1", "ACI 318-19 §22.8.3"]
NEW_MEZZANINE = ["AISC 360-22 §E3", "AISC 360-22 §F2", "ACI 318-19 §22.8.3"]

BASIS = DesignBasis(pins={"AISC 360": "22", "ACI 318": "19"})
WAIVER = MixedEditionWaiver(
    standard="AISC 360",
    editions=("16", "22"),
    accepted_by="A. Engineer, P.E. (engineer of record)",
    rationale=(
        "the existing frame is assessed under the edition it was designed to; new "
        "members follow the currently adopted edition"
    ),
    accepted_on=date(2026, 8, 17),
)


def screen_retrofit_bundle() -> Scorecard:
    """New work alone, the whole bundle unwaived, and the whole bundle waived."""
    whole = [*EXISTING_FRAME, *NEW_MEZZANINE]
    return Scorecard(
        entries=[
            design_basis_scorecard("new mezzanine only", basis=BASIS, references=NEW_MEZZANINE),
            design_basis_scorecard("whole bundle, unwaived", basis=BASIS, references=whole),
            design_basis_scorecard(
                "whole bundle, waived",
                basis=BASIS.model_copy(update={"waivers": (WAIVER,)}),
                references=whole,
            ),
        ]
    )


def main() -> None:
    print("2018 frame designed to AISC 360-16, new mezzanine to -22")
    for entry in screen_retrofit_bundle().entries:
        print(f"  {entry.name:<26} {entry.status.value}")
        print(f"      {entry.detail}")


if __name__ == "__main__":
    main()
