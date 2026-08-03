"""Worked example: a revision that moves which check governs.

When a design changes, the numbers all move — but the question a reviewer asks is
narrower: *is the same check still the one holding the design back?* A scorecard
answers it directly. `Scorecard.governing()` names the tightest check, and
`governing_shift(previous)` reports when a revision hands governance from one
check to another.

A 200 kN column lands on a 300 x 300 mm base plate. Two limit states are
screened: the concrete bearing under the plate (AISC J8) and the cantilevered
plate's own bending (Design Guide 1). The concrete is comfortable — the bearing
pressure is a ninth of what the footing allows — so bearing never moves; it is
fixed by the plate footprint, not its thickness.

The first design uses a thin 8 mm plate. Its bending stress 3·f_p·l²/t² runs to
585 MPa against a 250 MPa yield, a safety factor of 0.43: the plate bending fails,
and it governs by a wide margin. The obvious revision is a thicker plate. Because
the bending stress runs inversely with the square of the thickness, a 40 mm plate
drops it to 23 MPa — the bending safety factor climbs past 10, and now the
comfortable concrete bearing (still 9.6) is the tightest check in the set.

The revision didn't just relax a number; it moved the governing check from the
plate's bending to the concrete bearing. That is what `governing_shift` reports —
so the reviewer knows the reference point moved, and that any further thickening
of the plate is wasted: it no longer touches what governs.

Run it directly (``python examples/base_plate_revision_governing_shift.py``);
:func:`thin_plate`, :func:`thick_plate`, and :func:`governing_shift` are exercised
in the test suite.
"""

from __future__ import annotations

from anvilate.packs.structural import BasePlate, screen_base_plate
from anvilate.scorecard import GoverningChange, Scorecard
from anvilate.units import Quantity

REQUIRED_SF = 2.0


def _plate(thickness: str) -> BasePlate:
    return BasePlate(
        name="col_base",
        width=Quantity.parse("300 mm"),
        depth=Quantity.parse("300 mm"),
        axial_load=Quantity.parse("200 kN"),
        concrete_strength=Quantity.parse("25 MPa"),
        plate_thickness=Quantity.parse(thickness),
        cantilever=Quantity.parse("75 mm"),
        plate_material="ASTM-A36",
    )


def thin_plate() -> Scorecard:
    """The first design: an 8 mm plate whose bending governs (and fails)."""
    return screen_base_plate(_plate("8 mm"), required_safety_factor=REQUIRED_SF)


def thick_plate() -> Scorecard:
    """The revision: a 40 mm plate — now the concrete bearing governs."""
    return screen_base_plate(_plate("40 mm"), required_safety_factor=REQUIRED_SF)


def governing_shift() -> GoverningChange | None:
    """How the governing check moved from the thin plate to the thick one."""
    return thick_plate().governing_shift(thin_plate())


def main() -> None:
    before = thin_plate()
    print("Thin 8 mm plate:")
    print(before)
    for entry in before.entries:
        print(f"  {entry}")
    print(f"  governing: {before.governing().name}")

    after = thick_plate()
    print("\nRevised 40 mm plate:")
    print(after)
    for entry in after.entries:
        print(f"  {entry}")
    print(f"  governing: {after.governing().name}")

    shift = after.governing_shift(before)
    print(f"\n{shift}")


if __name__ == "__main__":
    main()
