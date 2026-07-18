"""Worked example: the bolt load the direct-shear estimate misses.

A bracket bolts to a column face with four bolts in a 80 x 120 mm rectangle and hangs
a 40 kN load out on an arm, 150 mm from the bolt group's centre. The tempting way to
size the bolts is to share the load equally: 40 kN over four bolts is 10 kN each, and
against a 25 kN bolt shear capacity that is a safety factor of 2.5 -- plenty.

That estimate is wrong, because the load does not act at the bolt group's centre. Its
150 mm offset applies a 6 kN*m twisting moment to the group, and the bolts resist it
with a torsional shear that adds vectorially to the direct 10 kN -- largest at the
corner bolts farthest from the centre. Worked properly with the elastic (instantaneous
-centre) method, the top corner bolt carries 27.6 kN, nearly three times the naive
estimate, and it fails the 25 kN capacity at a safety factor of 0.90. The connection
the direct-shear check called safe is overloaded.

The lesson is that an eccentric load on a bolt group is a torsion problem, not just a
sharing problem: the moment can dwarf the direct shear, and it always loads the corner
bolts hardest. Spreading the bolts wider (a larger polar moment) is the lever that
brings the peak back down. The bolt layout and load are declared inline.

Run it directly (``python examples/bracket_bolt_group_eccentric.py``);
:func:`screen_bracket_bolts` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import eccentric_shear_group_peak_force
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("40 kN")
ECCENTRICITY = Quantity.parse("150 mm")
BOLT_SHEAR_CAPACITY = Quantity.parse("25 kN")


def _bolt_positions() -> list[tuple[Quantity, Quantity]]:
    """A 80 x 120 mm rectangular pattern, centred on the group centroid."""
    xs = (Quantity.parse("40 mm"), Quantity.parse("-40 mm"))
    ys = (Quantity.parse("60 mm"), Quantity.parse("-60 mm"))
    return [(x, y) for x in xs for y in ys]


def screen_bracket_bolts() -> Scorecard:
    """Screen the bolt shear capacity against the naive direct-shear estimate and the
    true peak (elastic-method) bolt force (safety factor = capacity / bolt force)."""
    capacity = BOLT_SHEAR_CAPACITY.to("kN").magnitude
    positions = _bolt_positions()
    direct_shear = LOAD.to("kN").magnitude / len(positions)
    peak = (
        eccentric_shear_group_peak_force(positions=positions, load=LOAD, eccentricity=ECCENTRICITY)
        .to("kN")
        .magnitude
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "direct-shear estimate (P/n)", computed=capacity / direct_shear, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "true peak (eccentric)", computed=capacity / peak, required=1.0
            ),
        )
    )


def main() -> None:
    positions = _bolt_positions()
    direct_shear = LOAD.to("kN").magnitude / len(positions)
    peak = eccentric_shear_group_peak_force(
        positions=positions, load=LOAD, eccentricity=ECCENTRICITY
    )
    print(f"direct-shear estimate P/n: {direct_shear:.1f} kN")
    print(f"true peak corner bolt:     {peak.to('kN').magnitude:.1f} kN")
    print(screen_bracket_bolts())


if __name__ == "__main__":
    main()
