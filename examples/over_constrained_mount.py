"""Worked example: the same mount over-constrained, then exactly constrained.

A sensor plate is clamped to a machined face and located by two round dowels. It is the
textbook fixture, and it is over-constrained: the face takes the normal translation and the
two tilts, dowel A takes both in-plane translations, and dowel B — a round pin on the same
line — takes the rotation about the normal and, a second time, the translation along the
line. Two pins now fight over one freedom. Which of them carries the load along that line
is decided by how far apart the holes were actually drilled, not by the drawing, so a
dowel-shear check on this plate is a number resting on a load division nobody determined.

Swap dowel B for a pin in a slot running along the dowel line and the count comes out at
exactly six: every freedom removed once, and the same shear check reads as the plain result
it is.

Run it directly (``python examples/over_constrained_mount.py``);
:func:`mount_reports` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.scorecard import ScorecardEntry
from anvilate.topology import Constraint, ConstraintKind, ConstraintTally, Frame, Freedom, tally

FRAME = Frame(
    name="plate frame",
    x="along the dowel line",
    y="across the dowel line",
    z="the plate normal",
)
FACE = Constraint(
    feature="machined face",
    kind=ConstraintKind.PLANAR_FACE,
    removes=(Freedom.TZ, Freedom.RX, Freedom.RY),
)
DOWEL_A = Constraint(
    feature="dowel A", kind=ConstraintKind.PIN_IN_HOLE, removes=(Freedom.TX, Freedom.TY)
)
# A round pin 80 mm along x: in the plate frame it stops translation along x again, and
# rotation about z.
DOWEL_B = Constraint(
    feature="dowel B", kind=ConstraintKind.PIN_IN_HOLE, removes=(Freedom.TX, Freedom.RZ)
)
# The same pin in a slot running along x: it stops rotation about z and nothing else.
SLOT_B = Constraint(feature="slot B", kind=ConstraintKind.SLOT, removes=(Freedom.RZ,))

# The dowel-shear check both versions of the plate are screened with.
DOWEL_SHEAR = ScorecardEntry.from_safety_factor("dowel shear", computed=3.4, required=2.0)


def mount_reports() -> tuple[ConstraintTally, ConstraintTally]:
    """The plate as drawn, and the plate with dowel B in a slot."""
    as_drawn = tally("sensor plate", FRAME, (FACE, DOWEL_A, DOWEL_B))
    slotted = tally("sensor plate", FRAME, (FACE, DOWEL_A, SLOT_B))
    return as_drawn, slotted


def main() -> None:
    as_drawn, slotted = mount_reports()
    for label, counted in (("two round dowels", as_drawn), ("dowel and slot", slotted)):
        print(f"== {label}")
        print(counted)
        print(counted.entry())
        print(counted.qualify(DOWEL_SHEAR))
        print()


if __name__ == "__main__":
    main()
