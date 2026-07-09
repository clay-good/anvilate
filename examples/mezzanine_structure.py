"""Worked example: screening a whole mezzanine structure with the structural pack.

Declares a small steel mezzanine — a 3 m floor beam under a distributed load,
carried on two 2.5 m posts — as structural members, then screens the whole thing
in one call. The pack dispatches the beam to the simply-supported UDL check (with
an L/360 deflection limit) and each post to a buckling check, rolling every result
into one No-silent-green scorecard.

Run it directly (``python examples/mezzanine_structure.py``);
:func:`screen_mezzanine` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import (
    BeamMember,
    ColumnMember,
    LoadType,
    Support,
    screen_structure,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SPAN = Quantity.parse("3 m")
FLOOR_LOAD = Quantity.parse("5 N/mm")  # 5 kN/m distributed over the beam


def screen_mezzanine() -> Scorecard:
    """Declare and screen the mezzanine, returning the whole-structure scorecard."""
    floor_beam = BeamMember(
        name="floor_beam",
        section=CrossSection.rectangular(
            width=Quantity.parse("50 mm"), height=Quantity.parse("100 mm")
        ),
        length=SPAN,
        support=Support.SIMPLY_SUPPORTED,
        load=FLOOR_LOAD,
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        deflection_limit=Quantity.parse("8.33 mm"),  # ~ span / 360
    )
    # Each post carries half the beam's total load, w*L/2.
    post_load = Quantity(
        magnitude=FLOOR_LOAD.to("N/mm").magnitude * SPAN.to("mm").magnitude / 2, unit="N"
    )
    posts = [
        ColumnMember(
            name=f"post_{side}",
            section=CrossSection.rectangular(
                width=Quantity.parse("50 mm"), height=Quantity.parse("50 mm")
            ),
            length=Quantity.parse("2.5 m"),
            axial_load=post_load,
            material="ASTM-A36",
        )
        for side in ("left", "right")
    ]
    return screen_structure([floor_beam, *posts], required_safety_factor=1.67)


def main() -> None:
    card = screen_mezzanine()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
