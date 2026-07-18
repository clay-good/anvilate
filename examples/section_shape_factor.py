"""Worked example: how much a beam carries past first yield depends on its shape.

Elastic design stops at first yield -- the moment M_y = Z_e*S_y that just yields the
extreme fibre. But a ductile section keeps going: as the load grows the yielded zone
spreads inward until the whole section has yielded and a plastic hinge forms at
M_p = Z_p*S_y. The ratio M_p/M_y = Z_p/Z_e is the *shape factor*, and it is a
property of the cross-section's shape alone -- the reserve a ductile beam holds
between first yield and collapse.

That reserve is very different across shapes. A solid round bar, with its area
spread across the depth, keeps about 70% in hand (shape factor 1.70). A solid
rectangle keeps exactly 50% (1.50). But an I-section piles nearly all its area in
the flanges, already at the extreme fibre, so almost none is left to recruit: its
shape factor is only ~1.17. Each section here is taken right at first yield, and
screened for whether it holds at least a 1.5 reserve before a hinge forms: the round
bar and the rectangle do, the I-beam does not.

The lesson is not that I-beams are bad -- they are the most material-efficient
elastic shape, which is why they are everywhere -- but that a design leaning on
post-yield ductility (seismic, plastic, crash) cannot assume the reserve a compact
section would give. The section moduli come straight from the geometry.

Run it directly (``python examples/section_shape_factor.py``);
:func:`screen_shape_factors` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    circular_plastic_section_modulus,
    circular_second_moment,
    i_section_plastic_section_modulus,
    i_section_second_moment,
    rectangular_plastic_section_modulus,
    rectangular_second_moment,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

REQUIRED_RESERVE = 1.5  # required plastic reserve (shape factor) past first yield


def _shape_factor(elastic_modulus: Quantity, plastic_modulus: Quantity) -> float:
    return plastic_modulus.to("mm**3").magnitude / elastic_modulus.to("mm**3").magnitude


def _sections() -> dict[str, float]:
    # Elastic modulus Z_e = I / c for each section (c = half-depth or radius).
    round_ze = Quantity(
        magnitude=circular_second_moment(Quantity.parse("80 mm")).to("mm**4").magnitude / 40.0,
        unit="mm**3",
    )
    round_zp = circular_plastic_section_modulus(Quantity.parse("80 mm"))

    rect_ze = Quantity(
        magnitude=rectangular_second_moment(Quantity.parse("40 mm"), Quantity.parse("120 mm"))
        .to("mm**4")
        .magnitude
        / 60.0,
        unit="mm**3",
    )
    rect_zp = rectangular_plastic_section_modulus(Quantity.parse("40 mm"), Quantity.parse("120 mm"))

    i_kwargs = {
        "flange_width": Quantity.parse("100 mm"),
        "total_height": Quantity.parse("200 mm"),
        "flange_thickness": Quantity.parse("15 mm"),
        "web_thickness": Quantity.parse("10 mm"),
    }
    i_ze = Quantity(
        magnitude=i_section_second_moment(**i_kwargs).to("mm**4").magnitude / 100.0,
        unit="mm**3",
    )
    i_zp = i_section_plastic_section_modulus(**i_kwargs)

    return {
        "solid round bar (d 80)": _shape_factor(round_ze, round_zp),
        "solid rectangle (40x120)": _shape_factor(rect_ze, rect_zp),
        "I-section (100x200, 15/10)": _shape_factor(i_ze, i_zp),
    }


def screen_shape_factors() -> Scorecard:
    """Screen each section's shape factor (its reserve past first yield) against the
    required 1.5 (safety factor = shape factor / required)."""
    entries = [
        ScorecardEntry.from_safety_factor(name, computed=factor, required=REQUIRED_RESERVE)
        for name, factor in _sections().items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, factor in _sections().items():
        print(f"{name}: shape factor {factor:.3f}")
    print(screen_shape_factors())


if __name__ == "__main__":
    main()
