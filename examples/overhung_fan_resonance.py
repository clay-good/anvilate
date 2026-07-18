"""Capstone: the fan shaft that is far too strong and shakes itself apart.

A 15 kg fan wheel hangs off the end of a 200 mm overhung shaft and spins at 3000 rpm. Look at
the shaft as a loaded beam and it is absurd overkill: the fan's own weight bends the 25 mm
shaft to a mere 19 MPa against a 350 MPa yield, a safety factor of 18. You could hardly make it
stronger if you tried. And it will still tear its bearings out.

The trouble is not stress, it is *speed*. An overhung mass on a shaft has a critical (whirl)
speed where the shaft's bending flexibility and the wheel's mass resonate, and here that speed
is 2957 rpm -- essentially the 3000 rpm the fan runs at. At resonance the smallest unbalance
drives a runaway whirl, and no amount of strength helps because the deflection, not the stress,
is what diverges. The design rule is to keep the running speed clear of the critical, below
about 0.75 of it for subcritical operation, and this shaft reaches only 0.74 of that -- it runs
*at* its critical speed, not below it.

The fix is not a stronger shaft; the shaft is already 18 times too strong. It is a *stiffer*
one, which raises the critical speed out of the way. Growing the shaft from 25 mm to 38 mm --
still trivially strong at 5 MPa -- lifts the critical speed to 6831 rpm, well above the running
speed, with a comfortable margin of 1.71. Stiffness, not strength, moves a critical speed.

The lesson is that a rotating shaft has a speed check that its stress check knows nothing about,
and a shaft can be far too strong and still resonate. Size a rotating shaft for its critical
speed as well as its stress -- and the knob for the critical speed is stiffness (diameter),
which strength alone does not buy.

Run it directly (``python examples/overhung_fan_resonance.py``);
:func:`screen_fan_shaft` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import cantilever_tip_mass_frequency, circular_second_moment
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

FAN_MASS = Quantity.parse("15 kg")
OVERHANG = Quantity.parse("200 mm")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
YIELD_STRENGTH = Quantity.parse("350 MPa")
OPERATING_SPEED = Quantity.parse("3000 rpm")
SUBCRITICAL_MARGIN = 0.75  # keep operating below 75% of the critical speed
GRAVITY = Quantity.parse("9.80665 m/s**2")

AS_DRAWN_DIAMETER = Quantity.parse("25 mm")
STIFFER_DIAMETER = Quantity.parse("38 mm")


def _screen(diameter: Quantity) -> Scorecard:
    second_moment = circular_second_moment(diameter)
    # Self-weight bending stress at the shaft root: sigma = 32*M/(pi*d^3), M = m*g*L.
    moment = (
        FAN_MASS.to("kg").magnitude * GRAVITY.to("m/s**2").magnitude * OVERHANG.to("m").magnitude
    )  # N*m
    d = diameter.to("mm").magnitude
    bending_stress = 32.0 * moment * 1000.0 / (pi * d**3)  # MPa
    # Critical (whirl) speed of the overhung mass on the shaft.
    critical_hz = cantilever_tip_mass_frequency(
        elastic_modulus=ELASTIC_MODULUS,
        second_moment=second_moment,
        length=OVERHANG,
        tip_mass=FAN_MASS,
    )
    critical_rpm = critical_hz.to("Hz").magnitude * 60.0
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "shaft bending vs yield",
                computed=YIELD_STRENGTH.to("MPa").magnitude / bending_stress,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "critical-speed separation",
                computed=(SUBCRITICAL_MARGIN * critical_rpm) / OPERATING_SPEED.to("rpm").magnitude,
                required=1.0,
            ),
        )
    )


def screen_fan_shaft() -> Scorecard:
    """Screen the slender 25 mm shaft: hugely strong, but running at its critical speed."""
    return _screen(AS_DRAWN_DIAMETER)


def screen_stiffer_shaft() -> Scorecard:
    """Screen the 38 mm shaft: stiffer, so the critical speed clears the running speed."""
    return _screen(STIFFER_DIAMETER)


def main() -> None:
    print("as drawn (25 mm shaft):")
    print(screen_fan_shaft())
    print("\nstiffer (38 mm shaft):")
    print(screen_stiffer_shaft())


if __name__ == "__main__":
    main()
