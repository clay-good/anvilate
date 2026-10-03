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

Sources: Hibbeler, *Engineering Mechanics: Dynamics* (curvilinear motion, projectile) — the
drag-free range, peak height and time of flight of a launch over level ground, and the launch
angle that reaches a required range.
"""

from __future__ import annotations

from math import asin, cos, degrees, radians, sin, sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_LAUNCH_SOURCE = "the launcher specification (launch speed, angle, and height)"
_TARGET_SOURCE = "the target's surveyed range"


class _ProjectileInputError(RefusalError, ValueError):
    """A projectile-trajectory input that cannot be used without correction."""


def _projectile_refusal(message: str, *, subject: str, source: str) -> _ProjectileInputError:
    return _ProjectileInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _projectile_input_source(name: str) -> str:
    if name == "target_range":
        return _TARGET_SOURCE
    return _LAUNCH_SOURCE


STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "projectile_launch_angle_for_range",
    "projectile_max_height",
    "projectile_range",
    "projectile_range_from_height",
    "projectile_time_of_flight",
]


def projectile_range(*, launch_speed: Quantity, launch_angle: float) -> Quantity:
    """The horizontal range over level ground, R = v²·sin(2θ)/g.

    How far a body launched at ``launch_speed`` v and ``launch_angle`` θ (degrees above horizontal)
    travels before returning to launch height: R = v²·sin(2θ)/g. It is greatest at 45°, where
    sin(2θ) = 1, and equal for any pair of angles that sum to 90° (a flat, fast shot and a high,
    lobbed one reach the same distance). Returns the range in m.
    """
    require_finite(launch_angle, name="launch_angle")
    _check(launch_speed, "[length]/[time]", "launch_speed")
    v = launch_speed.to("m/s").magnitude
    if v <= 0:
        raise _projectile_refusal(
            "launch_speed must be positive", subject="launch_speed", source=_LAUNCH_SOURCE
        )
    if not 0.0 < launch_angle < 90.0:
        raise _projectile_refusal(
            "launch_angle must be in (0, 90) degrees", subject="launch_angle", source=_LAUNCH_SOURCE
        )
    theta = radians(launch_angle)
    return Quantity(magnitude=v * v * sin(2.0 * theta) / STANDARD_GRAVITY_M_PER_S2, unit="m")


def projectile_max_height(*, launch_speed: Quantity, launch_angle: float) -> Quantity:
    """The peak height of the trajectory, H = v²·sin²θ/(2·g).

    The highest point a body reaches, where its vertical velocity falls to zero: from the
    ``launch_speed`` v and the ``launch_angle`` θ (degrees above horizontal), H = v²·sin²θ/(2·g). It
    depends only on the vertical launch component, so it keeps rising toward a vertical launch,
    unlike the range which peaks at 45°. Returns the maximum height in m.
    """
    require_finite(launch_angle, name="launch_angle")
    _check(launch_speed, "[length]/[time]", "launch_speed")
    v = launch_speed.to("m/s").magnitude
    if v <= 0:
        raise _projectile_refusal(
            "launch_speed must be positive", subject="launch_speed", source=_LAUNCH_SOURCE
        )
    if not 0.0 < launch_angle <= 90.0:
        raise _projectile_refusal(
            "launch_angle must be in (0, 90] degrees", subject="launch_angle", source=_LAUNCH_SOURCE
        )
    vy = v * sin(radians(launch_angle))
    return Quantity(magnitude=vy * vy / (2.0 * STANDARD_GRAVITY_M_PER_S2), unit="m")


def projectile_time_of_flight(*, launch_speed: Quantity, launch_angle: float) -> Quantity:
    """The time aloft over level ground, t = 2·v·sin θ/g.

    How long a body stays in the air before returning to launch height: from the ``launch_speed`` v
    and the ``launch_angle`` θ (degrees above horizontal), t = 2·v·sin θ/g. Like the peak height it
    grows with the vertical launch component, reaching its maximum for a vertical launch. Returns
    time of flight in s.
    """
    require_finite(launch_angle, name="launch_angle")
    _check(launch_speed, "[length]/[time]", "launch_speed")
    v = launch_speed.to("m/s").magnitude
    if v <= 0:
        raise _projectile_refusal(
            "launch_speed must be positive", subject="launch_speed", source=_LAUNCH_SOURCE
        )
    if not 0.0 < launch_angle <= 90.0:
        raise _projectile_refusal(
            "launch_angle must be in (0, 90] degrees", subject="launch_angle", source=_LAUNCH_SOURCE
        )
    return Quantity(
        magnitude=2.0 * v * sin(radians(launch_angle)) / STANDARD_GRAVITY_M_PER_S2, unit="s"
    )


def projectile_launch_angle_for_range(
    *, launch_speed: Quantity, target_range: Quantity, high_trajectory: bool = False
) -> float:
    """The launch angle to reach a target range, θ = ½·arcsin(g·R/v²).

    The aiming inverse of :func:`projectile_range`: to land a projectile at a horizontal
    ``target_range`` R over level ground with ``launch_speed`` v, fire at θ = ½·arcsin(g·R/v²).
    Every reachable range has *two* solutions summing to 90° — a flat, fast ``low`` shot (default)
    and a high, lobbed one (``high_trajectory=True``) — merging at 45° for the maximum range
    v²/g. A target beyond that maximum cannot be reached at this speed and is rejected. Returns the
    launch angle in degrees.
    """
    _check(launch_speed, "[length]/[time]", "launch_speed")
    _check(target_range, "[length]", "target_range")
    v = launch_speed.to("m/s").magnitude
    r = target_range.to("m").magnitude
    if v <= 0:
        raise _projectile_refusal(
            "launch_speed must be positive", subject="launch_speed", source=_LAUNCH_SOURCE
        )
    if r <= 0:
        raise _projectile_refusal(
            "target_range must be positive", subject="target_range", source=_TARGET_SOURCE
        )
    ratio = STANDARD_GRAVITY_M_PER_S2 * r / (v * v)
    if ratio > 1.0:
        raise _projectile_refusal(
            "target_range exceeds the maximum range v²/g at this speed (unreachable); "
            "increase the launch speed",
            subject="target_range and launch_speed",
            source=_TARGET_SOURCE,
        )
    low_angle = 0.5 * degrees(asin(ratio))
    return 90.0 - low_angle if high_trajectory else low_angle


def projectile_range_from_height(
    *, launch_speed: Quantity, launch_angle: float, launch_height: Quantity
) -> Quantity:
    """The range of a projectile launched from a height, R = (v·cosθ/g)·(v·sinθ + √((v·sinθ)²+2gh)).

    When the launch point sits a ``launch_height`` h above the landing plane — a ball thrown off a
    cliff, a shell from a hilltop — the projectile flies farther than the level-ground
    :func:`projectile_range`, because it spends extra time falling the last h. Solving the vertical
    quadratic for the flight time and multiplying by the horizontal speed gives
    R = (v·cosθ/g)·(v·sinθ + √((v·sinθ)² + 2·g·h)), from the ``launch_speed`` v and ``launch_angle``
    θ (degrees). At h = 0 it reduces to the level-ground v²·sin(2θ)/g, and the optimal angle for the
    maximum range drops below 45° as the height grows. Returns the range in metres.
    """
    require_finite(launch_angle, name="launch_angle")
    _check(launch_speed, "[length]/[time]", "launch_speed")
    _check(launch_height, "[length]", "launch_height")
    v = launch_speed.to("m/s").magnitude
    h = launch_height.to("m").magnitude
    if v <= 0:
        raise _projectile_refusal(
            "launch_speed must be positive", subject="launch_speed", source=_LAUNCH_SOURCE
        )
    if h < 0:
        raise _projectile_refusal(
            "launch_height must be non-negative", subject="launch_height", source=_LAUNCH_SOURCE
        )
    if not 0.0 <= launch_angle < 90.0:
        raise _projectile_refusal(
            "launch_angle must be in [0, 90) degrees", subject="launch_angle", source=_LAUNCH_SOURCE
        )
    theta = radians(launch_angle)
    vy = v * sin(theta)
    vx = v * cos(theta)
    g = STANDARD_GRAVITY_M_PER_S2
    r = (vx / g) * (vy + sqrt(vy * vy + 2.0 * g * h))
    return Quantity(magnitude=r, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _projectile_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_projectile_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _projectile_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_projectile_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
