"""Worked example: the cam profile that could not outrun its own speed.

A cam lifts a 0.30 kg follower 15 mm over an 80 degree rise. The follower is held
on the cam by a return spring and its seating, which together can supply at most
150 N -- so the follower's acceleration must stay under 150 N / 0.30 kg = 500 m/s²
or it floats off the cam and slams back (valve float, the classic high-speed cam
failure).

At 600 rpm the simple-harmonic profile is comfortable: its peak follower
acceleration is 150 m/s², a 3.3x margin. The temptation is to run the same cam
faster. It does not survive: acceleration scales with the *square* of cam speed,
so doubling to 1200 rpm quadruples the peak to 600 m/s² and the follower floats
(0.83 margin, fail). Reaching for the cycloidal profile -- smoother, zero jerk at
the dwell -- makes it worse here, not better: cycloidal trades its gentle ends for
a higher mid-rise peak (764 m/s²), so at 1200 rpm it fails harder (0.65).

The lesson is that a cam's acceleration is a speed-squared problem, and no motion
profile buys its way out of it. Below the float speed you choose the profile for
smoothness; above it you slow the cam or lighten the follower. The 150 N seating
limit is manufacturer's data, declared inline like any allowable.

Run it directly (``python examples/highspeed_cam_follower.py``);
:func:`screen_cam_follower` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import cam_follower_motion
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

RISE = Quantity.parse("15 mm")
RISE_ANGLE = 80.0
FOLLOWER_MASS = Quantity.parse("0.30 kg")
MAX_SEATING_FORCE = Quantity.parse("150 N")

# The acceleration the seating force can hold against the follower inertia.
ACCEL_LIMIT = MAX_SEATING_FORCE.to("N").magnitude / FOLLOWER_MASS.to("kg").magnitude

CASES = {
    "SHM at 600 rpm": ("shm", Quantity.parse("600 rpm")),
    "SHM at 1200 rpm": ("shm", Quantity.parse("1200 rpm")),
    "cycloidal at 1200 rpm": ("cycloidal", Quantity.parse("1200 rpm")),
}


def peak_acceleration(profile: str, cam_speed: Quantity) -> float:
    """The largest follower acceleration magnitude across the rise (m/s²),
    sampled from the cam module at one-degree steps."""
    peak = 0.0
    step = 0
    while step <= int(RISE_ANGLE):
        motion = cam_follower_motion(
            profile=profile,
            rise=RISE,
            cam_angle=float(step),
            rise_angle=RISE_ANGLE,
            cam_speed=cam_speed,
        )
        peak = max(peak, abs(motion.acceleration.to("m/s**2").magnitude))
        step += 1
    return peak


def screen_cam_follower() -> Scorecard:
    """Screen each profile/speed case: the peak follower acceleration must stay
    under the seating limit (safety factor = limit / peak)."""
    entries = [
        ScorecardEntry.from_safety_factor(
            name,
            computed=ACCEL_LIMIT / peak_acceleration(profile, speed),
            required=1.0,
        )
        for name, (profile, speed) in CASES.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, (profile, speed) in CASES.items():
        print(
            f"{name}: peak {peak_acceleration(profile, speed):.0f} m/s² (limit {ACCEL_LIMIT:.0f})"
        )
    print(screen_cam_follower())


if __name__ == "__main__":
    main()
