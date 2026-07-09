"""Worked example: the same steel area as a square bar and as an I-beam.

Declares a 10 kN point load at mid-span of a 3 m simply-supported A36 beam and
screens two sections holding the same ~3,080 mm² of steel: a 55.5 mm square bar,
and a 200 mm deep I-shape (100 x 10 mm flanges, 6 mm web). The shape is the whole
story: pushing the flange material far from the neutral axis multiplies the
section modulus 7.4x (28,500 -> 209,800 mm³), so the square bar fails outright at
SF 0.95 while the I-beam passes at 6.99 — same weight per meter, same material,
same load. This is why rolled beams are I-shaped.

Run it directly (``python examples/i_beam_same_steel.py``);
:func:`screen_same_steel` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

LOAD = Quantity.parse("10 kN")
SPAN = Quantity.parse("3 m")


def screen_same_steel() -> Scorecard:
    """Screen both equal-area sections under the same load, returning one card."""
    square_bar = CrossSection.rectangular(
        width=Quantity.parse("55.5 mm"), height=Quantity.parse("55.5 mm")
    )
    i_beam = CrossSection.i_section(
        depth=Quantity.parse("200 mm"),
        flange_width=Quantity.parse("100 mm"),
        flange_thickness=Quantity.parse("10 mm"),
        web_thickness=Quantity.parse("6 mm"),
    )
    common = {
        "length": SPAN,
        "support": Support.SIMPLY_SUPPORTED,
        "load": LOAD,
        "load_type": LoadType.POINT,
        "material": "ASTM-A36",
    }
    members = [
        BeamMember(name="square bar", section=square_bar, **common),
        BeamMember(name="I-beam", section=i_beam, **common),
    ]
    return screen_structure(members, required_safety_factor=1.5)


def main() -> None:
    card = screen_same_steel()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
