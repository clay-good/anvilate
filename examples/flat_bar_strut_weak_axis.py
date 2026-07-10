"""Worked example: the column screen buckles the bar the way it wants to bow.

Declares a 20 x 60 mm A36 flat bar bracing a machine frame — 900 mm pin-ended,
carrying 60 kN of compression — drawn with its bending stiffness through the
60 mm depth (r = 17.3 mm, λ = 52, a stocky Johnson column at SF 4.6). But a
pin-ended column is free to bow whichever way is easiest, and about the 20 mm
direction r is only 5.8 mm: λ = 156 is deep in the Euler regime, where the
critical stress collapses to 81 MPa and the same load FAILs at SF 1.6. The
pack guards this automatically: every builder section carries both second
moments, and the buckling screen takes ``least_radius_of_gyration``, so the
as-drawn declaration screens at the honest 1.6 — a strong-axis declaration
cannot inflate capacity. The false 4.6 can only be produced by a hand-built
raw :class:`CrossSection`, which records no transverse second moment and so
leaves the weak-axis choice with the caller.

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
    """Screen the as-drawn declaration and the raw-section escape hatch."""
    as_drawn = CrossSection.rectangular(
        width=Quantity.parse("20 mm"), height=Quantity.parse("60 mm")
    )
    # A hand-built section records only the declared axis — no transverse
    # second moment — so the screen cannot see the weak axis and takes the
    # caller's word for it. This is the screen the guard exists to prevent.
    strong_axis_only = CrossSection(
        area=as_drawn.area,
        second_moment=as_drawn.second_moment,
        extreme_fibre=as_drawn.extreme_fibre,
    )
    common = {"length": LENGTH, "axial_load": AXIAL_LOAD, "material": "ASTM-A36"}
    return screen_structure(
        [
            ColumnMember(name="as-drawn (guarded)", section=as_drawn, **common),
            ColumnMember(name="raw strong-axis section", section=strong_axis_only, **common),
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
