"""Worked example: a flat-bar strut buckles about its weak axis, not the strong one.

Declares a 20 x 60 mm A36 flat bar bracing a machine frame — 900 mm pin-ended,
carrying 60 kN of compression — and screens it about both centroidal axes.
Screened the way the section was drawn (bending stiffness through the 60 mm
depth, r = 17.3 mm, λ = 52) the strut sits in the Johnson regime and clears the
2.0 requirement at SF 4.6. But a pin-ended column is free to bow whichever way
is easiest, and about the 20 mm direction r is only 5.8 mm: λ = 156 puts it deep
in the Euler regime, where the critical stress collapses to 81 MPa and the same
load FAILs at SF 1.6. ``CrossSection.least_radius_of_gyration`` (5.8 < 17.3)
is the built-in tell that the as-drawn orientation is not the governing one.

Run it directly (``python examples/flat_bar_strut_weak_axis.py``);
:func:`screen_flat_bar_strut` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import ColumnMember, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

AXIAL_LOAD = Quantity.parse("60 kN")
LENGTH = Quantity.parse("900 mm")


def screen_flat_bar_strut() -> Scorecard:
    """Screen the strut about both axes, returning one scorecard."""
    as_drawn = CrossSection.rectangular(
        width=Quantity.parse("20 mm"), height=Quantity.parse("60 mm")
    )
    # The same bar with the bending axis through its 20 mm thickness — the
    # orientation a pin-ended column actually buckles in, which
    # as_drawn.least_radius_of_gyration already points at.
    weak_axis = CrossSection.rectangular(
        width=Quantity.parse("60 mm"), height=Quantity.parse("20 mm")
    )
    common = {"length": LENGTH, "axial_load": AXIAL_LOAD, "material": "ASTM-A36"}
    return screen_structure(
        [
            ColumnMember(name="as-drawn strong axis", section=as_drawn, **common),
            ColumnMember(name="governing weak axis", section=weak_axis, **common),
        ],
        required_safety_factor=2.0,
    )


def main() -> None:
    as_drawn = CrossSection.rectangular(
        width=Quantity.parse("20 mm"), height=Quantity.parse("60 mm")
    )
    print(
        f"r as drawn: {as_drawn.radius_of_gyration}, least r: {as_drawn.least_radius_of_gyration}"
    )
    card = screen_flat_bar_strut()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
