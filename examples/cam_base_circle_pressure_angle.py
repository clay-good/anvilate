"""Worked example: the cam base circle that jams its follower.

A cam lifts a translating roller follower 20 mm over 60 degrees of rotation on a
simple-harmonic profile. The kinematics are fine -- the acceleration is bounded, the
follower does what it should. What decides whether the mechanism *works* is a
quantity the lift profile alone does not reveal: the pressure angle, the tilt of the
cam-to-follower contact normal away from the follower's line of travel. The more the
contact force tilts, the more of it shoves the follower sideways against its guide
instead of along its stroke, and past about 30 degrees the side thrust jams the
follower in its bore.

The pressure angle peaks near mid-rise, where the follower is moving fastest, and it
depends on the base circle. A tight 40 mm base circle makes the tooth-to-follower
geometry steep: the pressure angle reaches 31 degrees, over the limit -- the follower
binds. The fix is not a different lift profile but a bigger base circle: opening it to
60 mm flattens the contact geometry and drops the pressure angle to 23 degrees, well
clear. The lift is the same; the machine simply has more room to deliver it.

The lesson is that a cam's base circle is not free to be as small as packaging would
like. It is set by the pressure angle, and a follower that jams is cured by growing
the base circle (or adding an offset), not by reprofiling the rise. The lift, rise
angle, and base circles are declared inline.

Run it directly (``python examples/cam_base_circle_pressure_angle.py``);
:func:`screen_cam_pressure_angle` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import cam_follower_motion, cam_pressure_angle
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

RISE = Quantity.parse("20 mm")
RISE_ANGLE = 60.0  # degrees
CAM_SPEED = Quantity.parse("600 rpm")
MID_RISE_ANGLE = 30.0  # degrees, where the SHM velocity (and pressure angle) peaks
MAX_PRESSURE_ANGLE = 30.0  # degrees, the translating-follower jamming limit
BASE_CIRCLE_RADII = (Quantity.parse("40 mm"), Quantity.parse("60 mm"))

_TWO_PI = 6.283185307179586


def _mid_rise_state() -> tuple[Quantity, Quantity]:
    """Return the follower displacement and lift gradient ds/dtheta at mid-rise."""
    motion = cam_follower_motion(
        profile="shm",
        rise=RISE,
        cam_angle=MID_RISE_ANGLE,
        rise_angle=RISE_ANGLE,
        cam_speed=CAM_SPEED,
    )
    omega = CAM_SPEED.to("rad/s").magnitude
    lift_gradient = Quantity(
        magnitude=motion.velocity.to("m/s").magnitude / omega * 1000.0, unit="mm"
    )
    return motion.displacement, lift_gradient


def screen_cam_pressure_angle() -> Scorecard:
    """Screen the mid-rise pressure angle against the 30-degree jamming limit for each
    base circle (safety factor = limit / pressure angle)."""
    displacement, lift_gradient = _mid_rise_state()
    entries = []
    for base_circle in BASE_CIRCLE_RADII:
        phi = (
            cam_pressure_angle(
                lift_gradient=lift_gradient,
                follower_displacement=displacement,
                base_circle_radius=base_circle,
            )
            .to("degree")
            .magnitude
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{base_circle.to('mm').magnitude:.0f} mm base circle",
                computed=MAX_PRESSURE_ANGLE / phi,
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    displacement, lift_gradient = _mid_rise_state()
    for base_circle in BASE_CIRCLE_RADII:
        phi = cam_pressure_angle(
            lift_gradient=lift_gradient,
            follower_displacement=displacement,
            base_circle_radius=base_circle,
        )
        print(
            f"{base_circle.to('mm').magnitude:.0f} mm base circle: "
            f"pressure angle {phi.to('degree').magnitude:.1f} deg"
        )
    print(screen_cam_pressure_angle())


if __name__ == "__main__":
    main()
