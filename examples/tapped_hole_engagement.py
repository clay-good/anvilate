"""Worked example: one diameter of thread is enough — into steel.

An M12 x 1.75 class-8.8 steel bolt is torqued to develop its full rated clamp:
the proof load through the ISO 898 tensile stress area is 84.3 mm^2 x 580 MPa =
48.9 kN. The shop rule of thumb is "thread it in one diameter" — 12 mm of
engagement — which is exactly right for a steel nut. But this bolt threads into
a tapped boss in 6061-T6 aluminium, and the threads that carry the load are the
soft internal ones.

Thread stripping is a shear failure over the engaged threads, and which
cylinder shears depends on which member is weaker. The bolt's own (external)
steel threads strip on a cylinder at the internal minor diameter, area
0.75*pi*D1*Le; the aluminium (internal) threads strip on the larger cylinder at
the bolt's major diameter, area 0.875*pi*d*Le. The aluminium area is bigger, but
its material is far weaker, so it governs. At 12 mm of engagement the steel
threads sit at SF 2.16 while the aluminium threads run 123 MPa against a 159 MPa
allowable — SF 1.29, under the 2.0 a soft tapped hole is held to. Doubling the
engagement to 24 mm (the "two diameters into aluminium" rule) halves the
stripping stress and recovers SF 2.58. Same bolt, same load; the fix is deeper
threads, not a bigger bolt.

The proof strength (580 MPa, ISO 898-1 class 8.8) and the aluminium shear
allowable (0.577*Sy for 6061-T6) are declared inline as engineering inputs, not
drawn from a library table.

Run it directly (``python examples/tapped_hole_engagement.py``);
:func:`screen_tapped_hole` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bolt_tensile_stress_area,
    strength_scorecard,
    thread_stripping_stress,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

NOMINAL_DIAMETER = Quantity.parse("12 mm")  # M12
PITCH = Quantity.parse("1.75 mm")  # M12 coarse (from the standards thread table)
PROOF_STRENGTH = Quantity.parse("580 MPa")  # ISO 898-1 property class 8.8
# 6061-T6 tapped-hole threads, shear allowable ~ 0.577*Sy (Sy = 276 MPa).
ALUMINIUM_SHEAR_ALLOWABLE = Quantity.parse("159 MPa")
# Class-8.8 steel bolt threads, shear allowable ~ 0.577*Sy (Sy = 640 MPa).
STEEL_SHEAR_ALLOWABLE = Quantity.parse("369 MPa")
SHORT_ENGAGEMENT = Quantity.parse("12 mm")  # one diameter (the steel-nut rule)
DEEP_ENGAGEMENT = Quantity.parse("24 mm")  # two diameters (the aluminium rule)
REQUIRED_SF = 2.0


def _proof_load() -> Quantity:
    """The bolt's rated proof load = A_t * proof strength — the clamp the joint
    is expected to develop."""
    area = bolt_tensile_stress_area(nominal_diameter=NOMINAL_DIAMETER, pitch=PITCH)
    return Quantity(magnitude=(area.pint * PROOF_STRENGTH.pint).to("N").magnitude, unit="N")


def screen_tapped_hole() -> Scorecard:
    """Screen thread stripping at the bolt's proof load three ways: the steel
    bolt threads and the aluminium hole threads at one diameter of engagement,
    then the aluminium threads at two diameters."""
    load = _proof_load()
    steel_short = thread_stripping_stress(
        load=load,
        nominal_diameter=NOMINAL_DIAMETER,
        pitch=PITCH,
        engagement_length=SHORT_ENGAGEMENT,
        member="external",
    )
    alum_short = thread_stripping_stress(
        load=load,
        nominal_diameter=NOMINAL_DIAMETER,
        pitch=PITCH,
        engagement_length=SHORT_ENGAGEMENT,
        member="internal",
    )
    alum_deep = thread_stripping_stress(
        load=load,
        nominal_diameter=NOMINAL_DIAMETER,
        pitch=PITCH,
        engagement_length=DEEP_ENGAGEMENT,
        member="internal",
    )
    return Scorecard(
        entries=(
            strength_scorecard(
                "steel bolt threads @ 1*d",
                stress=steel_short,
                allowable=STEEL_SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
            strength_scorecard(
                "aluminium hole threads @ 1*d",
                stress=alum_short,
                allowable=ALUMINIUM_SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
            strength_scorecard(
                "aluminium hole threads @ 2*d",
                stress=alum_deep,
                allowable=ALUMINIUM_SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
        )
    )


def main() -> None:
    card = screen_tapped_hole()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
