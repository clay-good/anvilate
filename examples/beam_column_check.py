"""Worked example: a pipe beam-column under combined axial load and bending.

A column rarely carries pure compression — wind, an eccentric beam reaction, or
frame action adds a bending moment, and the two effects interact: axial load eats
into the moment the section can carry, and vice versa. This screen takes a round
HSS pipe column (Ø200 × 10 mm wall, 4 m, pinned) carrying 400 kN of gravity load
plus a 40 kN·m moment and runs the AISC §H1.1 interaction check that beams (bending
only) and columns (axial only) can't express on their own.

The pack computes the available axial strength from the buckling curve and the
available flexural strength from first yield, combines them per §H1.1, and reports
the reciprocal of the unity ratio as a safety factor — here a comfortable pass.

Run it directly (``python examples/beam_column_check.py``); :func:`screen_beam_column_post`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import ColumnEnd, CrossSection
from anvilate.packs.structural import BeamColumnMember, screen_beam_column
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity


def screen_beam_column_post() -> Scorecard:
    """Declare and screen the pipe beam-column, returning its scorecard."""
    pipe = CrossSection.hollow_circular(
        outer_diameter=Quantity.parse("200 mm"),
        inner_diameter=Quantity.parse("180 mm"),
    )
    post = BeamColumnMember(
        name="frame_post",
        section=pipe,
        length=Quantity.parse("4 m"),
        axial_load=Quantity.parse("400 kN"),
        moment=Quantity.parse("40 kN*m"),
        material="ASTM-A992",
        end_condition=ColumnEnd.PINNED_PINNED,
    )
    return screen_beam_column(post, required_safety_factor=1.5)


def main() -> None:
    card = screen_beam_column_post()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
