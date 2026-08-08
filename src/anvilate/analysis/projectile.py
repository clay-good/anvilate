"""T1 analytical projectile-trajectory checks (drag-free, closed-form).

Anything launched into the air and left to gravity follows a parabola, and its reach, peak, and
flight time have simple closed forms. Engineers need them more often than the "physics-class" label
suggests: where bulk material thrown off the end of a conveyor lands (to place the receiving chute),
how far a water jet or spray carries, and the safe throw distance of a fragment or an ejected part.
These forms neglect air drag — good for dense, fast, compact bodies over short flights, optimistic
for light or slow ones — so they are a first-cut screen, not a ballistics solution.

For a launch over level ground at speed v and angle θ above horizontal, the horizontal range is
R = v²·sin(2θ)/g, largest at 45°; the peak height is H = v²·sin²θ/(2·g); and the time aloft is
t = 2·v·sin θ/g. Range peaks at 45° because sin(2θ) does, while height and flight time keep rising
toward a vertical launch — the trade a designer balances when aiming a discharge or a jet.
"""

from __future__ import annotations

from math import radians, sin

from ..units import Quantity

STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "projectile_max_height",
    "projectile_range",
    "projectile_time_of_flight",
]


def projectile_range(*, launch_speed: Quantity, launch_angle: float) -> Quantity:
    """The horizontal range over level ground, R = v²·sin(2θ)/g.

    How far a body launched at ``launch_speed`` v and ``launch_angle`` θ (degrees above horizontal)
    travels before returning to launch height: R = v²·sin(2θ)/g. It is greatest at 45°, where
    sin(2θ) = 1, and equal for any pair of angles that sum to 90° (a flat, fast shot and a high,
    lobbed one reach the same distance). Returns the range in m.
    """
    _check(launch_speed, "[length]/[time]", "launch_speed")
    v = launch_speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("launch_speed must be positive")
    if not 0.0 < launch_angle < 90.0:
        raise ValueError("launch_angle must be in (0, 90) degrees")
    theta = radians(launch_angle)
    return Quantity(magnitude=v * v * sin(2.0 * theta) / STANDARD_GRAVITY_M_PER_S2, unit="m")


def projectile_max_height(*, launch_speed: Quantity, launch_angle: float) -> Quantity:
    """The peak height of the trajectory, H = v²·sin²θ/(2·g).

    The highest point a body reaches, where its vertical velocity falls to zero: from the
    ``launch_speed`` v and the ``launch_angle`` θ (degrees above horizontal), H = v²·sin²θ/(2·g). It
    depends only on the vertical launch component, so it keeps rising toward a vertical launch,
    unlike the range which peaks at 45°. Returns the maximum height in m.
    """
    _check(launch_speed, "[length]/[time]", "launch_speed")
    v = launch_speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("launch_speed must be positive")
    if not 0.0 < launch_angle <= 90.0:
        raise ValueError("launch_angle must be in (0, 90] degrees")
    vy = v * sin(radians(launch_angle))
    return Quantity(magnitude=vy * vy / (2.0 * STANDARD_GRAVITY_M_PER_S2), unit="m")


def projectile_time_of_flight(*, launch_speed: Quantity, launch_angle: float) -> Quantity:
    """The time aloft over level ground, t = 2·v·sin θ/g.

    How long a body stays in the air before returning to launch height: from the ``launch_speed`` v
    and the ``launch_angle`` θ (degrees above horizontal), t = 2·v·sin θ/g. Like the peak height it
    grows with the vertical launch component, reaching its maximum for a vertical launch. Returns
    time of flight in s.
    """
    _check(launch_speed, "[length]/[time]", "launch_speed")
    v = launch_speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("launch_speed must be positive")
    if not 0.0 < launch_angle <= 90.0:
        raise ValueError("launch_angle must be in (0, 90] degrees")
    return Quantity(
        magnitude=2.0 * v * sin(radians(launch_angle)) / STANDARD_GRAVITY_M_PER_S2, unit="s"
    )


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
