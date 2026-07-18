"""Worked example: the weld stress the throat-shear estimate misses.

A bracket is welded to a column with two vertical fillet welds, each 200 mm long on a
80 mm spacing, and it hangs a 30 kN load out on a 150 mm arm. Sizing the welds the
easy way -- spread the load over all 400 mm of weld throat -- gives a comfortable
17.7 MPa, a safety factor over 3 against a 60 MPa allowable. The welds look generously
sized.

They are not, because the load does not act over the weld group's centroid. Its 150 mm
offset twists the weld line with a 4.5 kN*m moment, and the weld resists it with a
torsional shear flow that adds vectorially to the direct flow -- largest at the ends of
the welds, farthest from the centroid. Worked by the AISC elastic (instantaneous-centre)
method the peak throat stress is 66.5 MPa, nearly four times the direct-shear estimate,
and it fails the 60 MPa allowable at a safety factor of 0.90. The connection the simple
check called safe is overstressed at the weld ends.

The lesson is the same one that governs an eccentric bolt group: an off-centre load on a
weld line is a torsion problem, the moment can dwarf the direct shear, and it loads the
weld ends hardest. Spreading the welds farther apart (a larger polar moment) is the lever
that brings the peak back down. The weld layout and load are declared inline.

Run it directly (``python examples/bracket_weld_group_eccentric.py``);
:func:`screen_bracket_welds` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import eccentric_weld_group_peak_stress, fillet_weld_throat_stress
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("30 kN")
ECCENTRICITY = Quantity.parse("150 mm")
LEG_SIZE = Quantity.parse("6 mm")
TOTAL_WELD_LENGTH = Quantity.parse("400 mm")
ALLOWABLE_STRESS = Quantity.parse("60 MPa")


def _weld_segments() -> list[tuple[tuple[Quantity, Quantity], tuple[Quantity, Quantity]]]:
    """Two 200 mm vertical welds on an 80 mm spacing, centred on the group centroid."""
    return [
        (
            (Quantity.parse("40 mm"), Quantity.parse("100 mm")),
            (Quantity.parse("40 mm"), Quantity.parse("-100 mm")),
        ),
        (
            (Quantity.parse("-40 mm"), Quantity.parse("100 mm")),
            (Quantity.parse("-40 mm"), Quantity.parse("-100 mm")),
        ),
    ]


def screen_bracket_welds() -> Scorecard:
    """Screen the allowable weld stress against the naive direct-shear estimate and the
    true eccentric peak (safety factor = allowable / stress)."""
    allowable = ALLOWABLE_STRESS.to("MPa").magnitude
    direct = (
        fillet_weld_throat_stress(force=LOAD, leg_size=LEG_SIZE, length=TOTAL_WELD_LENGTH)
        .to("MPa")
        .magnitude
    )
    peak = (
        eccentric_weld_group_peak_stress(
            segments=_weld_segments(), load=LOAD, eccentricity=ECCENTRICITY, leg_size=LEG_SIZE
        )
        .to("MPa")
        .magnitude
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "direct-shear estimate", computed=allowable / direct, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "true peak (eccentric)", computed=allowable / peak, required=1.0
            ),
        )
    )


def main() -> None:
    direct = fillet_weld_throat_stress(force=LOAD, leg_size=LEG_SIZE, length=TOTAL_WELD_LENGTH)
    peak = eccentric_weld_group_peak_stress(
        segments=_weld_segments(), load=LOAD, eccentricity=ECCENTRICITY, leg_size=LEG_SIZE
    )
    print(f"direct-shear estimate: {direct.to('MPa').magnitude:.1f} MPa")
    print(f"true peak (eccentric): {peak.to('MPa').magnitude:.1f} MPa")
    print(screen_bracket_welds())


if __name__ == "__main__":
    main()
