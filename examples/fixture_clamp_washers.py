"""Worked example: the clamp that stayed clamped.

A machining fixture clamps a casting through a stack of disc washers. Gasket
creep, chip settling, and thermal cycling cost the joint 0.4 mm of grip over a
shift, and the process spec says the clamp force may vary at most 10% -- a
loose casting chatters, an over-clamped one distorts.

Two washers with the same 40/20 mm footprint audition for the job. The stiff,
shallow disc (cone height half its 1.5 mm thickness) behaves like any linear
spring: losing 0.4 mm of its barely-0.7 mm working deflection dumps 52% of the
clamp force -- five times the allowance. The disc coned to h/t = sqrt(2), the
Almen-Laszlo plateau ratio, rides the flat top of its load-deflection curve:
the same 0.4 mm of settling costs 2.3% of the force. Same footprint, same
steel -- the *shape* of the curve, set by one geometry ratio, is the whole
design. That is what Belleville washers are for: not storing energy, but
holding force while position drifts.

The 10% allowance is the process engineer's input, declared inline.

Run it directly (``python examples/fixture_clamp_washers.py``);
:func:`screen_clamp_washers` is also exercised in the test suite.
"""

from __future__ import annotations

from math import sqrt

from anvilate.analysis import belleville_washer_force
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

OUTER_DIAMETER = Quantity.parse("40 mm")
INNER_DIAMETER = Quantity.parse("20 mm")
THICKNESS = Quantity.parse("1.5 mm")
MODULUS = Quantity.parse("206 GPa")
SETTLEMENT = 0.4  # mm of grip lost over a shift
ALLOWED_VARIATION = 0.10  # process spec: clamp force within 10%

# (label, cone height h in mm, working deflection y0 in mm)
CANDIDATES = (
    ("shallow disc (h/t = 0.5)", 0.75, 0.70),
    ("plateau disc (h/t = sqrt(2))", sqrt(2.0) * 1.5, 0.9 * sqrt(2.0) * 1.5),
)


def _force_at(cone_height: float, deflection: float) -> float:
    """The washer load in newtons at a given deflection, both in mm."""
    return (
        belleville_washer_force(
            deflection=Quantity(magnitude=deflection, unit="mm"),
            thickness=THICKNESS,
            cone_height=Quantity(magnitude=cone_height, unit="mm"),
            outer_diameter=OUTER_DIAMETER,
            inner_diameter=INNER_DIAMETER,
            elastic_modulus=MODULUS,
        )
        .to("N")
        .magnitude
    )


def force_variation(cone_height: float, working_deflection: float) -> float:
    """The fractional clamp-force loss when the joint settles by SETTLEMENT."""
    clamped = _force_at(cone_height, working_deflection)
    settled = _force_at(cone_height, working_deflection - SETTLEMENT)
    return (clamped - settled) / clamped


def screen_clamp_washers() -> Scorecard:
    """Screen each candidate washer's force constancy over the shift's
    settlement against the 10% process allowance."""
    entries = []
    for label, cone_height, working_deflection in CANDIDATES:
        variation = force_variation(cone_height, working_deflection)
        entries.append(
            ScorecardEntry.from_safety_factor(
                label, computed=ALLOWED_VARIATION / variation, required=1.0
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for label, cone_height, working_deflection in CANDIDATES:
        variation = force_variation(cone_height, working_deflection)
        print(f"{label}: {variation:.1%} force loss over {SETTLEMENT} mm settling")
    print(screen_clamp_washers())


if __name__ == "__main__":
    main()
