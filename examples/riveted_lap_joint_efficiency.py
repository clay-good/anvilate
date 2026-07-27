"""Worked example: the riveted seam that balances its three failure modes.

A riveted lap seam -- 20 mm rivets at a 50 mm pitch in 12 mm plate, with the classic
boiler-practice allowables of 80 MPa plate tension, 60 MPa rivet shear, and 120 MPa
bearing (user-supplied, as all allowables are) -- can fail three ways over each pitch:
the plate tears across the hole, the rivets shear, or the rivet crushes against the
hole. The weakest mode is the joint's strength, and the strength as a fraction of the
unpierced plate is its *efficiency* -- the number a seam is bought and inspected by.

Single-riveted, this seam is lopsided: one rivet's shear area (18.8 kN) gives out far
below the plate's tearing strength (28.8 kN), so the joint keeps only 39% of the solid
plate -- short of the 50% a decent lap seam should reach -- and the plate section
around it is mostly wasted. The instinct to widen the pitch makes it *worse*: pitch
adds tearing strength and solid-plate strength alike, while the shear ceiling stays
fixed, so efficiency falls.

The fix is a second row. Two rivets per pitch double the shear ceiling to 37.7 kN,
the governing mode flips from shearing to tearing at 28.8 kN, and the efficiency
climbs to 60% -- a balanced seam, with no single mode throwing capacity away. That is
the whole craft of riveted (and bolted-lap) design in one move: a joint is efficient
when its failure modes are matched, and the governing-mode label says which lever to
pull next.

Run it directly (``python examples/riveted_lap_joint_efficiency.py``);
:func:`screen_single_riveted_seam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import riveted_joint_efficiency
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

PITCH = Quantity.parse("50 mm")
RIVET_DIAMETER = Quantity.parse("20 mm")
PLATE_THICKNESS = Quantity.parse("12 mm")
ALLOWABLE_TENSION = Quantity.parse("80 MPa")  # user-supplied boiler-practice allowables
ALLOWABLE_SHEAR = Quantity.parse("60 MPa")
ALLOWABLE_BEARING = Quantity.parse("120 MPa")

REQUIRED_EFFICIENCY = 0.50  # the floor a decent lap seam should clear


def _screen(rivets_per_pitch: int, name: str) -> Scorecard:
    joint = riveted_joint_efficiency(
        pitch=PITCH,
        rivet_diameter=RIVET_DIAMETER,
        plate_thickness=PLATE_THICKNESS,
        allowable_tension=ALLOWABLE_TENSION,
        allowable_shear=ALLOWABLE_SHEAR,
        allowable_bearing=ALLOWABLE_BEARING,
        rivets_per_pitch=rivets_per_pitch,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                f"{name} (governs by {joint.governing_mode})",
                computed=joint.efficiency / REQUIRED_EFFICIENCY,
                required=1.0,
            ),
        )
    )


def screen_single_riveted_seam() -> Scorecard:
    """Screen the single-riveted seam: shear governs and efficiency is a poor 39%."""
    return _screen(1, "joint efficiency, single-riveted")


def screen_double_riveted_seam() -> Scorecard:
    """Screen the double-riveted seam: tearing governs and efficiency reaches 60%."""
    return _screen(2, "joint efficiency, double-riveted")


def main() -> None:
    print("single-riveted:")
    print(screen_single_riveted_seam())
    print("\ndouble-riveted:")
    print(screen_double_riveted_seam())


if __name__ == "__main__":
    main()
