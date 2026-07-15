"""Worked example: the section modulus sets the size.

A platform beam carries an 8 kN·m service moment in steel with a 165 MPa
allowable bending stress and a required 1.5 safety factor. Before picking a
section you can name the floor it must clear: Z_min = n·M/σ_allow = 1.5 · 8e6 /
165 ≈ 72,700 mm³. An 80 x 120 x 5 box tube looks generous but its section
modulus is only 62,600 mm³ — below the floor — so at the service moment it
works to 128 MPa and misses the 1.5 margin. Step up to a 100 x 140 x 6 box
(Z ≈ 107,000 mm³, above the floor) and the same moment is a comfortable 75 MPa.
The section modulus, not the overall size or the wall thickness alone, is what
the moment is asking for.

Run it directly (``python examples/beam_section_sizing.py``);
:func:`screen_beam_sections` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection, required_section_modulus, strength_scorecard
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

MOMENT = Quantity.parse("8 kN*m")
ALLOWABLE = Quantity.parse("165 MPa")  # steel allowable bending stress
REQUIRED_SF = 1.5

CANDIDATES = {
    "80x120x5 box": CrossSection.hollow_rectangular(
        width=Quantity.parse("80 mm"),
        height=Quantity.parse("120 mm"),
        wall_thickness=Quantity.parse("5 mm"),
    ),
    "100x140x6 box": CrossSection.hollow_rectangular(
        width=Quantity.parse("100 mm"),
        height=Quantity.parse("140 mm"),
        wall_thickness=Quantity.parse("6 mm"),
    ),
}


def floor_section_modulus() -> Quantity:
    """The minimum section modulus the moment requires at the design margin."""
    return required_section_modulus(
        bending_moment=MOMENT, allowable_stress=ALLOWABLE, required_safety_factor=REQUIRED_SF
    )


def screen_beam_sections() -> Scorecard:
    """Screen each candidate box tube's bending stress (M/Z) against the allowable
    — equivalent to asking whether its section modulus clears the required floor."""
    entries = []
    for name, section in CANDIDATES.items():
        z = section.section_modulus.to("mm**3").magnitude
        bending_stress = Quantity(magnitude=MOMENT.to("N*mm").magnitude / z, unit="MPa")
        entries.append(
            strength_scorecard(
                f"{name} bending",
                stress=bending_stress,
                allowable=ALLOWABLE,
                required=REQUIRED_SF,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    print(f"required section modulus: {floor_section_modulus().to('mm**3')}")
    card = screen_beam_sections()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
