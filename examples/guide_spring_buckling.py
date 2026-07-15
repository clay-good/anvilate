"""Worked example: the longer stroke that folded the spring sideways.

A machine's return spring got a redesign for more travel: same music wire
(d = 4 mm on a 32 mm mean coil, C = 8) but stretched to a 280 mm free length
with twenty soft active coils so it could give a 60 mm working stroke. The
wire-stress screen is happy — at the working load the Wahl-corrected shear is
~338 MPa against a 700 MPa allowable, a comfortable SF 2.0. What the stress
screen cannot see is that the coil is now a slender column between its flat
seats. On parallel plates the spring is only *absolutely* stable up to
L₀ ≈ 2.63·D/α = 168 mm; at 280 mm it is well past that, and the Shigley
critical deflection is y_cr ≈ 45 mm. The 60 mm stroke drives it clean through
that limit, so the spring buckles sideways and the follower binds long before
the wire is anywhere near yield. The fix is a shorter/fatter coil or a guide
rod, not thicker wire: stress never was the problem.

Run it directly (``python examples/guide_spring_buckling.py``);
:func:`screen_guide_spring_buckling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    SPRING_END_PARALLEL_PLATES,
    deflection_scorecard,
    helical_spring_buckling,
    helical_spring_rate,
    spring_shear_stress,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

WIRE = Quantity.parse("4 mm")
COIL = Quantity.parse("32 mm")  # mean coil diameter, C = 8
FREE_LENGTH = Quantity.parse("280 mm")
ACTIVE_COILS = 20
ELASTIC_MODULUS = Quantity.parse("207 GPa")  # steel (Shigley Table 10-5)
SHEAR_MODULUS = Quantity.parse("79.3 GPa")
WORKING_STROKE = Quantity.parse("60 mm")
SHEAR_ALLOWABLE = Quantity.parse("700 MPa")  # wire spec sheet, torsional
REQUIRED_SF = 1.5


def screen_guide_spring_buckling() -> Scorecard:
    """Screen the wire stress at the working stroke, then screen that same
    stroke against the coil's lateral-buckling limit."""
    rate = helical_spring_rate(
        mean_coil_diameter=COIL,
        wire_diameter=WIRE,
        active_coils=ACTIVE_COILS,
        shear_modulus=SHEAR_MODULUS,
    )
    force = Quantity(
        magnitude=rate.to("N/mm").magnitude * WORKING_STROKE.to("mm").magnitude,
        unit="N",
    )
    stress = spring_shear_stress(force=force, mean_coil_diameter=COIL, wire_diameter=WIRE)

    buckling = helical_spring_buckling(
        free_length=FREE_LENGTH,
        mean_coil_diameter=COIL,
        elastic_modulus=ELASTIC_MODULUS,
        shear_modulus=SHEAR_MODULUS,
        end_condition_constant=SPRING_END_PARALLEL_PLATES,
    )

    return Scorecard(
        entries=(
            strength_scorecard(
                "guide spring wire shear",
                stress=stress,
                allowable=SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
            # The working stroke must stay short of the critical buckling
            # deflection; None (absolutely stable) would read as NOT_EVALUATED.
            deflection_scorecard(
                "guide spring buckling",
                deflection=WORKING_STROKE,
                limit=buckling.critical_deflection,
            ),
        )
    )


def main() -> None:
    card = screen_guide_spring_buckling()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
