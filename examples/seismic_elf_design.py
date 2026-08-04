"""Capstone: the equivalent lateral force method end to end, from height to drift.

Designing a building for earthquake by the equivalent lateral force method is a chain of code steps,
each feeding the next, and this capstone runs the whole chain for a six-story steel moment frame
(24 m tall, 30,000 kN, on a site with SDS = 1.0 g, SD1 = 0.55 g, R = 8). It pulls eight functions
from the loads module in the order a designer works them:

1. **Period** — the approximate fundamental period Ta = Ct·hn^x from the height.
2. **Coefficient** — the seismic response coefficient, the SDS/R plateau capped by the SD1/T
   long-period limit; here the cap governs and pulls Cs down to 0.075 from the 0.125 plateau.
3. **Base shear** — V = Cs·W, the total lateral force.
4. **Serviceability** — the Cd-amplified story drift against the L/50 (0.020·h) limit, and the
   P-delta stability coefficient against its ceiling.

The takeaway is which step governs. The strength side is generous — the long-period cap already
handed the frame a seismic coefficient 40% below the plateau — and P-delta is a non-issue at a
stability coefficient of 0.04 against a 0.09 ceiling (safety factor 2.2). What governs is the drift:
the amplified story sway reaches 72 mm against an 80 mm limit, a safety factor of just 1.12. The
frame is not close to failing in strength; it is close to swaying too far. The lesson is that a
modern seismic design is usually governed by drift, not by the base-shear strength everyone starts
with — and the period cap that eases the force is the same flexibility that tightens the drift.

Run it directly (``python examples/seismic_elf_design.py``);
:func:`screen_seismic_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    allowable_story_drift,
    approximate_fundamental_period,
    seismic_base_shear,
    seismic_design_story_drift,
    seismic_response_coefficient,
    seismic_response_coefficient_upper_limit,
    seismic_stability_coefficient,
    seismic_stability_coefficient_limit,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

BUILDING_HEIGHT = Quantity.parse("24 m")
PERIOD_COEFFICIENT = 0.0724  # Ct, steel moment frame
HEIGHT_EXPONENT = 0.8  # x
SDS = 1.0
SD1 = 0.55
RESPONSE_MODIFICATION = 8.0  # R
DEFLECTION_AMPLIFICATION = 5.5  # Cd
SEISMIC_WEIGHT = Quantity.parse("30000 kN")

STORY_HEIGHT = Quantity.parse("4 m")
ELASTIC_STORY_DRIFT = Quantity.parse("13 mm")  # from the reduced-force analysis
DRIFT_LIMIT_RATIO = 0.020
STORY_GRAVITY_LOAD = Quantity.parse("25000 kN")
STORY_SHEAR = Quantity.parse("2000 kN")


def _governing_cs() -> float:
    period = approximate_fundamental_period(
        building_height=BUILDING_HEIGHT,
        period_coefficient=PERIOD_COEFFICIENT,
        height_exponent=HEIGHT_EXPONENT,
    )
    plateau = seismic_response_coefficient(
        design_spectral_acceleration=SDS, response_modification_factor=RESPONSE_MODIFICATION
    )
    cap = seismic_response_coefficient_upper_limit(
        design_spectral_acceleration_1s=SD1,
        fundamental_period=period,
        response_modification_factor=RESPONSE_MODIFICATION,
    )
    return min(plateau, cap)


def screen_seismic_design() -> Scorecard:
    """Screen the frame's seismic serviceability (drift and P-delta) off the ELF base shear."""
    cs = _governing_cs()
    # The base shear V = Cs*W is the demand the frame is proportioned for (context for the checks).
    seismic_base_shear(seismic_weight=SEISMIC_WEIGHT, response_coefficient=cs)

    design_drift = seismic_design_story_drift(
        elastic_story_drift=ELASTIC_STORY_DRIFT,
        deflection_amplification_factor=DEFLECTION_AMPLIFICATION,
    )
    allowable = allowable_story_drift(
        story_height=STORY_HEIGHT, drift_limit_ratio=DRIFT_LIMIT_RATIO
    )

    theta = seismic_stability_coefficient(
        story_gravity_load=STORY_GRAVITY_LOAD,
        design_story_drift=design_drift,
        story_shear=STORY_SHEAR,
        story_height=STORY_HEIGHT,
        deflection_amplification_factor=DEFLECTION_AMPLIFICATION,
    )
    theta_max = seismic_stability_coefficient_limit(
        deflection_amplification_factor=DEFLECTION_AMPLIFICATION
    )

    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "story drift vs 0.020h limit",
                computed=allowable.to("mm").magnitude / design_drift.to("mm").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "P-delta stability vs ceiling",
                computed=theta_max / theta,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(f"governing seismic coefficient Cs : {_governing_cs():.3f} (long-period cap governs)")
    print(screen_seismic_design())
    print(
        "  -> strength is generous and P-delta is a non-issue; the story drift governs the design"
    )


if __name__ == "__main__":
    main()
