"""Worked example: one gearbox output shaft, three independent failure modes.

A single machine element rarely fails for a single reason, and a design is only as
good as its weakest check. This example carries one gearbox output shaft through
the three screens that actually govern it, each drawing on a different part of the
analysis library, and rolls them into one scorecard.

The shaft carries a spur gear at mid-span: 300 N*m of torque on a 200 mm pitch
circle, which the gear force resolution turns into a 3000 N tangential and 1092 N
radial tooth load, a 3193 N resultant that bends the shaft over its 300 mm bearing
span. Three things must survive it:

* the shaft itself, under combined bending and torsion — the distortion-energy
  (von Mises) stress on a 35 mm shaft is 84 MPa against a 250 MPa allowable (2.98);
* the key that ties the gear to the shaft, in shear — a 10 x 50 mm key runs at
  34 MPa against a 100 MPa allowable (2.92);
* the rolling bearings, in fatigue — a 20 kN dynamic-rating bearing reaches a
  22,600-hour L10 life against a 20,000-hour target (1.13).

All three pass, so the design is sound — but the bearing life is the tight one, and
it is the check a shaft-stress-only analysis would have missed entirely. A complete
design screens every mode; the governing one is rarely the obvious one. The
allowables and bearing rating are material and catalogue data, declared inline.

Run it directly (``python examples/gearbox_output_shaft.py``);
:func:`screen_output_shaft` is also exercised in the test suite.
"""

from __future__ import annotations

from math import hypot

from anvilate.analysis import (
    bearing_life_hours,
    gear_radial_load,
    gear_tangential_load,
    key_shear_stress,
    shaft_von_mises_stress,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TORQUE = Quantity.parse("300 N*m")
PITCH_DIAMETER = Quantity.parse("200 mm")
PRESSURE_ANGLE = 20.0
BEARING_SPAN = Quantity.parse("300 mm")
SHAFT_DIAMETER = Quantity.parse("35 mm")
SHAFT_ALLOWABLE = Quantity.parse("250 MPa")
KEY_WIDTH = Quantity.parse("10 mm")
KEY_LENGTH = Quantity.parse("50 mm")
KEY_ALLOWABLE = Quantity.parse("100 MPa")
BEARING_RATING = Quantity.parse("20 kN")
BEARING_SPEED = Quantity.parse("1450 rpm")
BEARING_LIFE_TARGET = Quantity.parse("20000 hour")


def _gear_resultant_load() -> float:
    """The resultant tooth load (N) bending the shaft, from the gear force split."""
    wt = gear_tangential_load(torque=TORQUE, pitch_diameter=PITCH_DIAMETER)
    wr = gear_radial_load(tangential_load=wt, pressure_angle=PRESSURE_ANGLE)
    return hypot(wt.to("N").magnitude, wr.to("N").magnitude)


def screen_output_shaft() -> Scorecard:
    """Screen the shaft (combined stress), the key (shear), and the bearings
    (fatigue life) -- the three independent failure modes of the output shaft."""
    resultant = _gear_resultant_load()
    # Gear at mid-span of a simply-supported shaft: M = W * L / 4.
    moment = Quantity(magnitude=resultant * BEARING_SPAN.to("m").magnitude / 4.0, unit="N*m")
    shaft_stress = shaft_von_mises_stress(
        bending_moment=moment, torque=TORQUE, diameter=SHAFT_DIAMETER
    )
    key_stress = key_shear_stress(
        torque=TORQUE,
        shaft_diameter=SHAFT_DIAMETER,
        key_width=KEY_WIDTH,
        key_length=KEY_LENGTH,
    )
    bearing_life = bearing_life_hours(
        dynamic_load_rating=BEARING_RATING,
        equivalent_load=Quantity(magnitude=resultant / 2.0, unit="N"),  # load per bearing
        speed=BEARING_SPEED,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "shaft, combined bending + torsion",
                computed=SHAFT_ALLOWABLE.to("MPa").magnitude / shaft_stress.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "key, shear",
                computed=KEY_ALLOWABLE.to("MPa").magnitude / key_stress.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "bearings, L10 fatigue life",
                computed=bearing_life.to("hour").magnitude
                / BEARING_LIFE_TARGET.to("hour").magnitude,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(f"resultant tooth load: {_gear_resultant_load():.0f} N")
    print(screen_output_shaft())


if __name__ == "__main__":
    main()
