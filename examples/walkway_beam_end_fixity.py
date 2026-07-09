"""Worked example: end fixity rescues a walkway beam's deflection check.

Declares a 4 m A36 walkway beam (60 x 120 mm rectangle) carrying 6 kN/m,
moment-connected into a concrete wall embed at one end and resting on a post at
the other, and screens it twice: once idealized the usual conservative way — a
pin at both ends — and once as the propped cantilever it actually is. Bending is
identical either way (the governing moment is w·L²/8 in both cases, sagging at
mid-span for pin-pin, hogging at the wall for the propped beam) and passes at
SF 3.0. Deflection is not: pin-pin gives 5·w·L⁴/(384·E·I) = 11.6 mm, just over
the L/360 = 11.1 mm limit, while the propped beam's w·L⁴/(185·E·I) = 4.8 mm
clears it easily. Declaring the fixity the connection already provides turns a
FAIL into a PASS without touching the section.

Run it directly (``python examples/walkway_beam_end_fixity.py``);
:func:`screen_walkway_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

FLOOR_LOAD = Quantity.parse("6 N/mm")  # 6 kN/m of grating, live load, and services
SPAN = Quantity.parse("4 m")
DEFLECTION_LIMIT = Quantity(magnitude=4000 / 360, unit="mm")  # L/360


def screen_walkway_beam() -> Scorecard:
    """Screen the beam under both end-fixity idealizations, returning one card."""
    section = CrossSection.rectangular(
        width=Quantity.parse("60 mm"), height=Quantity.parse("120 mm")
    )
    common = {
        "section": section,
        "length": SPAN,
        "load": FLOOR_LOAD,
        "load_type": LoadType.DISTRIBUTED,
        "material": "ASTM-A36",
        "deflection_limit": DEFLECTION_LIMIT,
    }
    assumed_pin_pin = BeamMember(name="assumed pin-pin", support=Support.SIMPLY_SUPPORTED, **common)
    wall_end_fixed = BeamMember(name="wall end fixed", support=Support.FIXED_PINNED, **common)
    return screen_structure([assumed_pin_pin, wall_end_fixed], required_safety_factor=1.5)


def main() -> None:
    card = screen_walkway_beam()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
