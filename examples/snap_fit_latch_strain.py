"""Worked example: the snap-fit that assembles by hand and cracks anyway.

A battery-cover latch is a nylon cantilever snap finger that must flex 1.0 mm to clear
its undercut. As first drawn it is short and stubby -- 8 mm long, 2 mm thick, 4 mm wide
-- and it goes together fine: the mating push over the 30-degree lead-in is about 46 N,
well inside a 65 N one-hand assembly limit. On the bench it clicks shut. It looks done.

It is not, because a snap-fit is designed by *strain*, not by force. Flexing that stubby
finger 1.0 mm strains its root fibre to 4.7 % (ε = 1.5*h*Y/L^2), more than double the
2 % a nylon tolerates on repeated assembly. The finger crazes and then cracks -- on the
first hard push if you are unlucky, after a dozen cycles if you are not -- and the very
assembly force that felt comfortable is what breaks it. The force gate passes and hides
the strain gate that governs.

The fix is not a stronger or thicker finger -- thickening it *raises* the strain. It is a
*longer, more slender* one: stretched to 15 mm at the same 2 mm thickness, the same 1.0 mm
undercut now strains the root to only 1.3 % (a safety factor of 1.5), and the mating force
drops to 7 N as a bonus. A snap finger clears a deeper undercut by getting longer and
thinner, because strain falls with the square of the length.

Run it directly (``python examples/snap_fit_latch_strain.py``);
:func:`screen_latch` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import snapfit as sf
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

UNDERCUT = Quantity.parse("1.0 mm")
THICKNESS = Quantity.parse("2 mm")
WIDTH = Quantity.parse("4 mm")
ELASTIC_MODULUS = Quantity.parse("2800 MPa")  # unfilled nylon
PERMISSIBLE_STRAIN = 0.02  # repeated-assembly allowable
INSERTION_ANGLE = 30.0
FRICTION_COEFFICIENT = 0.3
HAND_ASSEMBLY_LIMIT = Quantity.parse("65 N")

AS_DRAWN_LENGTH = Quantity.parse("8 mm")  # short and stubby
REDESIGNED_LENGTH = Quantity.parse("15 mm")  # long and slender


def _screen(length: Quantity) -> Scorecard:
    strain = sf.snap_fit_strain(deflection=UNDERCUT, length=length, thickness=THICKNESS)
    # The finger's spring force at its actual working deflection sets the mating push.
    deflection_force = sf.snap_fit_deflection_force(
        permissible_strain=strain,
        width=WIDTH,
        thickness=THICKNESS,
        length=length,
        elastic_modulus=ELASTIC_MODULUS,
    )
    mating_force = sf.snap_fit_mating_force(
        deflection_force=deflection_force,
        insertion_angle=INSERTION_ANGLE,
        friction_coefficient=FRICTION_COEFFICIENT,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "root strain vs allowable",
                computed=PERMISSIBLE_STRAIN / strain,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "mating force vs hand limit",
                computed=HAND_ASSEMBLY_LIMIT.to("N").magnitude / mating_force.to("N").magnitude,
                required=1.0,
            ),
        )
    )


def screen_latch() -> Scorecard:
    """Screen the as-drawn stubby finger: it assembles by hand but over-strains."""
    return _screen(AS_DRAWN_LENGTH)


def screen_redesigned_latch() -> Scorecard:
    """Screen the slender redesign: the same undercut, now within the strain allowable."""
    return _screen(REDESIGNED_LENGTH)


def main() -> None:
    print("as drawn (8 mm finger):")
    print(screen_latch())
    print("\nredesigned (15 mm finger):")
    print(screen_redesigned_latch())


if __name__ == "__main__":
    main()
