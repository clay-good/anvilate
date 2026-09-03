"""Worked example: the scotch-yoke pump whose speed-up costs nine times the shake.

A scotch-yoke dosing pump strokes 60 mm (a 30 mm crank) pushing a 1.2 kg slider and
plunger. The yoke's charm is its motion: the slider moves in *pure* simple harmonic
motion -- displacement a clean cosine, acceleration peaking at omega^2 * r at both dead
centres with none of a slider-crank's second-order harmonics. Its price is that the
whole inertia load lands on one sliding pin, whose bearing the designer has limited to
200 N (a user-supplied allowable from the pin's PV rating).

At the pump's 300 rpm design speed the peak inertia force is m * omega^2 * r = 36 N --
a 5.6 factor on the pin, and nobody thinks about it. Then production asks to triple
the flow by running 900 rpm. Flow scales with speed, but the inertia force scales
with speed *squared*: tripling the speed multiplies the peak acceleration nine-fold to
266 m/s^2, and the pin now sees 320 N -- 1.6 times its allowable. The pump that was
over-engineered at 300 rpm is over-loaded at 900.

The lesson is the omega-squared law of every reciprocating mechanism: throughput
bought with speed is paid for in inertia at the square of the price. The 900 rpm pump
needs a lighter slider, a bigger pin, or -- the usual answer -- a larger bore at the
original speed.

Run it directly (``python examples/scotch_yoke_pump_speed.py``);
:func:`screen_design_speed` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import scotch_yoke_acceleration
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

CRANK_RADIUS = Quantity.parse("30 mm")  # 60 mm stroke
MOVING_MASS = Quantity.parse("1.2 kg")  # slider + plunger
PIN_ALLOWABLE = Quantity.parse("200 N")  # user-supplied, from the pin's PV rating

DESIGN_SPEED = Quantity.parse("300 rpm")
UPRATED_SPEED = Quantity.parse("900 rpm")


def _screen(speed: Quantity) -> Scorecard:
    # Peak acceleration occurs at the dead centres (theta = 0 or 180 degrees).
    peak_acceleration = scotch_yoke_acceleration(
        crank_radius=CRANK_RADIUS,
        crank_angle=0.0,
        crank_speed=speed,
    )
    pin_force = MOVING_MASS.to("kg").magnitude * peak_acceleration.to("m/s^2").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                f"yoke pin inertia load at {speed.to('rpm').magnitude:.0f} rpm",
                computed=PIN_ALLOWABLE.to("N").magnitude / pin_force,
                required=1.0,
            ),
        )
    )


def screen_design_speed() -> Scorecard:
    """Screen the 300 rpm design point: the pin loafs at a 5.6 factor."""
    return _screen(DESIGN_SPEED)


def screen_uprated_speed() -> Scorecard:
    """Screen the 900 rpm uprate: 3x the speed is 9x the shake, and the pin fails."""
    return _screen(UPRATED_SPEED)


def main() -> None:
    print("design speed, 300 rpm:")
    print(screen_design_speed().report())
    print("\nuprated speed, 900 rpm:")
    print(screen_uprated_speed().report())


if __name__ == "__main__":
    main()
