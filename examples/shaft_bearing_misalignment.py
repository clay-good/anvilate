"""Worked example: the shaft check that is neither strength nor deflection.

A precision gear shaft, 50 mm across and spanning 1 m between two bearings, carries a
1.5 kN gear load at its centre. Checked the usual two ways it is comfortable: the
bending stress is a trivial 31 MPa against a 350 MPa yield (a safety factor over 11),
and the 0.51 mm midspan deflection is inside a 0.6 mm limit. By strength and stiffness
the shaft is fine.

There is a third check that neither of those catches. Where the shaft passes over its
bearings it is not flat -- it tilts, by the end slope F*L^2/(16*E*I) -- and a rolling
bearing tolerates only a tiny misalignment before its rollers edge-load and its life
collapses. Here the shaft slopes 0.00153 rad at each bearing, and the tight cylindrical
roller bearings allow only 0.0012 rad: the misalignment fails at a safety factor of
0.79. The shaft that is plenty strong and plenty stiff still mistreats its own bearings.

The lesson is that a shaft has three serviceability checks, not two: stress, deflection,
and the *slope* at its bearings -- and for a slender shaft on precision (roller or
angular-contact) bearings the slope is often the one that governs. A shaft that fails it
is stiffened (larger diameter, shorter span, or the load moved toward a bearing), or the
bearings changed to self-aligning ones that tolerate the tilt. The shaft, load, and
bearing tolerance are declared inline.

Run it directly (``python examples/shaft_bearing_misalignment.py``);
:func:`screen_shaft` is also exercised in the test suite.
"""

from __future__ import annotations

from math import radians

from anvilate.analysis import (
    circular_second_moment,
    simply_supported_center_load,
    simply_supported_center_load_support_slope,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("1.5 kN")
SPAN = Quantity.parse("1 m")
DIAMETER = Quantity.parse("50 mm")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
YIELD = Quantity.parse("350 MPa")
DEFLECTION_LIMIT = Quantity.parse("0.6 mm")
BEARING_MISALIGNMENT_TOLERANCE_RAD = 0.0012  # tight cylindrical roller bearing
REQUIRED_STRESS_SAFETY_FACTOR = 1.5


def screen_shaft() -> Scorecard:
    """Screen the shaft on bending stress, midspan deflection, and bearing
    misalignment slope."""
    second_moment = circular_second_moment(DIAMETER)
    bending = simply_supported_center_load(
        force=LOAD,
        length=SPAN,
        second_moment=second_moment,
        extreme_fibre=Quantity(magnitude=DIAMETER.to("mm").magnitude / 2, unit="mm"),
        elastic_modulus=ELASTIC_MODULUS,
    )
    slope_rad = radians(
        simply_supported_center_load_support_slope(
            force=LOAD, length=SPAN, second_moment=second_moment, elastic_modulus=ELASTIC_MODULUS
        )
        .to("degree")
        .magnitude
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "bending stress",
                computed=YIELD.to("MPa").magnitude / bending.max_bending_stress.to("MPa").magnitude,
                required=REQUIRED_STRESS_SAFETY_FACTOR,
            ),
            ScorecardEntry.from_safety_factor(
                "midspan deflection",
                computed=DEFLECTION_LIMIT.to("mm").magnitude
                / bending.max_deflection.to("mm").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "bearing misalignment slope",
                computed=BEARING_MISALIGNMENT_TOLERANCE_RAD / slope_rad,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(screen_shaft())


if __name__ == "__main__":
    main()
