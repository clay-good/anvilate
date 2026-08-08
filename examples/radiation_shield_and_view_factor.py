"""Worked example: how a radiation shield cuts furnace heat, and a view factor from crossed strings.

Radiant heat between surfaces depends on two things a designer controls: the view factor — the
fraction of one surface's radiation that lands on another — and any shields placed between them. The
view factor is pure geometry, and Hottel's crossed-strings trick gets it for any two long surfaces
from four string lengths, no charts needed. A radiation shield is the cheapest way to cut the flux:
each thin shield of the same emissivity slipped between two surfaces divides the net radiation by
one more, the principle behind spacecraft multi-layer insulation and cryostat shielding.

This example first finds the view factor between two 1 m parallel strips, 1 m apart, facing:
the crossed strings (the diagonals, each √2 m) minus the uncrossed strings (the 1 m gaps) over twice
the strip width gives F₁₂ ≈ 0.414 — a strip sees about 41% of its opposite number, the rest escaping
to the surroundings. Reciprocity then gives the view factor the other way for surfaces of different
size. Finally, inserting 3 radiation shields between two hot surfaces cuts the radiant flux to
1/(3+1) = 25% of the unshielded value. The example reports the view factor, a reciprocity value, and
3-shield reduction, so the geometry-and-shielding levers on radiant heat are explicit.

Run it directly (``python examples/radiation_shield_and_view_factor.py``);
:func:`radiation_geometry` is also exercised in the test suite.
"""

from __future__ import annotations

from math import sqrt

from anvilate.analysis import (
    crossed_strings_view_factor,
    radiation_shield_reduction_factor,
    view_factor_reciprocity,
)
from anvilate.units import Quantity

STRIP_WIDTH = Quantity.parse("1 m")
GAP = Quantity.parse("1 m")
NUMBER_OF_SHIELDS = 3


def radiation_geometry() -> dict[str, float]:
    """Return the crossed-strings view factor, a reciprocity conversion, and the 3-shield factor."""
    diagonal = Quantity(magnitude=sqrt(2.0), unit="m")  # √(w² + h²) for w = h = 1 m
    f12 = crossed_strings_view_factor(
        crossed_string_1=diagonal,
        crossed_string_2=diagonal,
        uncrossed_string_1=GAP,
        uncrossed_string_2=GAP,
        surface_1_width=STRIP_WIDTH,
    )
    # A small (1 m²) surface facing a larger (2 m²) one: reciprocity gives the reverse factor.
    f21 = view_factor_reciprocity(
        area_1=Quantity.parse("1 m**2"), view_factor_1_to_2=f12, area_2=Quantity.parse("2 m**2")
    )
    shield = radiation_shield_reduction_factor(number_of_shields=NUMBER_OF_SHIELDS)
    return {
        "view_factor_1_to_2": f12,
        "reciprocity_view_factor_2_to_1": f21,
        "shield_reduction_factor": shield,
    }


def main() -> None:
    d = radiation_geometry()
    print(f"crossed-strings view factor F12: {d['view_factor_1_to_2']:.3f}")
    print(f"reciprocity F21 (1 m^2 -> 2 m^2): {d['reciprocity_view_factor_2_to_1']:.3f}")
    print(
        f"3 radiation shields cut flux to: {d['shield_reduction_factor']:.0%} "
        f"of the unshielded value"
    )


if __name__ == "__main__":
    main()
