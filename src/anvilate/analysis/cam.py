"""T1 analytical cam-follower motion profiles (closed-form kinematics).

A cam turns rotation into a programmed follower motion, and the *profile* — how
the lift is distributed across the cam angle — decides how violently. The lift L
and rise angle β are fixed by the job; the profile is the designer's choice, and
it lives or dies on its acceleration, because acceleration times follower mass is
the force that hammers the contact and shakes the machine.

Two classic rise profiles bracket the trade-off. Simple harmonic motion (SHM)
lays the lift on a cosine,

    y = (L/2)·(1 − cos(π·θ/β)),

which is smooth in velocity but starts and ends with a *finite* acceleration —
an abrupt jerk step that a high-speed cam feels as a knock. Cycloidal motion,

    y = L·(θ/β − sin(2π·θ/β)/(2π)),

instead brings acceleration smoothly to zero at both ends, so it mates to a dwell
without a jump; it pays with a higher peak acceleration in the middle. Between them
sits parabolic (constant-acceleration) motion, which accelerates at a constant
+4L/β² for the first half of the rise and −4L/β² for the second — the *lowest*
possible peak acceleration for a given lift and rise, but with abrupt jerk steps
where the acceleration jumps. Velocity and acceleration follow by differentiating
with respect to time, which brings down one and two factors of the cam speed ω
(v = ẏ = (dy/dθ)·ω, a = (d²y/dθ²)·ω²).

The cam angle θ and rise angle β are plain-float degrees (the units layer carries
no angle); the lift is a length and the cam speed a rotational frequency —
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import cos, pi, radians, sin

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "CamMotion",
    "cam_follower_motion",
]

_PROFILES = ("shm", "cycloidal", "parabolic", "poly345")


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


class CamMotion(BaseModel):
    """A cam follower's kinematic state at one cam angle.

    ``displacement`` y is the lift from the base circle, ``velocity`` ẏ and
    ``acceleration`` ÿ its time derivatives at the given cam speed. All three are
    zero-referenced to the start of the rise; acceleration is what sizes the
    contact force and the return spring.
    """

    model_config = ConfigDict(frozen=True)

    displacement: Quantity
    velocity: Quantity
    acceleration: Quantity


def cam_follower_motion(
    *,
    profile: str,
    rise: Quantity,
    cam_angle: float,
    rise_angle: float,
    cam_speed: Quantity,
) -> CamMotion:
    """The follower displacement, velocity, and acceleration on a rise segment.

    ``profile`` selects the motion law — ``"shm"`` (simple harmonic, smooth
    velocity but finite end acceleration), ``"cycloidal"`` (acceleration zero at
    both ends, smoother but higher peak), ``"parabolic"`` (constant acceleration
    each half — the lowest peak, but with jerk steps), or ``"poly345"`` (the
    3-4-5 polynomial, zero velocity and acceleration at both ends with bounded
    jerk — the workhorse high-speed profile). ``rise`` L is the total lift,
    ``cam_angle``
    θ the current angle measured from the start of the rise, and ``rise_angle`` β the
    angle over which the full lift happens (both in **degrees**, 0 ≤ θ ≤ β).
    ``cam_speed`` ω is the cam's rotational speed (rpm or rad/s). The velocity and
    acceleration carry ω and ω² respectively, so a faster cam raises acceleration
    with the *square* of speed — which is why cam design is an acceleration problem.
    Returns a :class:`CamMotion` (displacement in mm, velocity in m/s, acceleration
    in m/s²).
    """
    if profile not in _PROFILES:
        raise ValueError(f"profile must be one of {list(_PROFILES)}; got {profile!r}")
    _require(rise, "[length]", "rise")
    if not cam_speed.has_dimension("[frequency]"):
        raise ValueError(
            f"cam_speed must be a rotational-speed ([frequency]) quantity; got "
            f"{cam_speed.dimensionality} ({cam_speed})"
        )
    if rise_angle <= 0:
        raise ValueError(f"rise_angle (degrees) must be positive; got {rise_angle}")
    if not 0 <= cam_angle <= rise_angle:
        raise ValueError(
            f"cam_angle (degrees) must lie in [0, rise_angle={rise_angle}]; got {cam_angle}"
        )
    ell = rise.to("m").magnitude
    beta = radians(rise_angle)
    theta = radians(cam_angle)
    omega = cam_speed.to("rad/s").magnitude
    frac = theta / beta  # 0 .. 1 across the rise
    if profile == "shm":
        y = (ell / 2.0) * (1.0 - cos(pi * frac))
        dy_dtheta = (ell / 2.0) * (pi / beta) * sin(pi * frac)
        d2y_dtheta2 = (ell / 2.0) * (pi / beta) ** 2 * cos(pi * frac)
    elif profile == "cycloidal":
        y = ell * (frac - sin(2.0 * pi * frac) / (2.0 * pi))
        dy_dtheta = (ell / beta) * (1.0 - cos(2.0 * pi * frac))
        d2y_dtheta2 = (ell / beta**2) * (2.0 * pi * sin(2.0 * pi * frac))
    elif profile == "parabolic":  # constant acceleration each half
        if frac <= 0.5:
            y = 2.0 * ell * frac**2
            dy_dtheta = 4.0 * ell * frac / beta
            d2y_dtheta2 = 4.0 * ell / beta**2
        else:
            y = ell * (1.0 - 2.0 * (1.0 - frac) ** 2)
            dy_dtheta = 4.0 * ell * (1.0 - frac) / beta
            d2y_dtheta2 = -4.0 * ell / beta**2
    else:  # poly345 (3-4-5 polynomial)
        y = ell * (10.0 * frac**3 - 15.0 * frac**4 + 6.0 * frac**5)
        dy_dtheta = (ell / beta) * (30.0 * frac**2 - 60.0 * frac**3 + 30.0 * frac**4)
        d2y_dtheta2 = (ell / beta**2) * (60.0 * frac - 180.0 * frac**2 + 120.0 * frac**3)
    return CamMotion(
        displacement=Quantity(magnitude=y * 1000.0, unit="mm"),
        velocity=Quantity(magnitude=dy_dtheta * omega, unit="m/s"),
        acceleration=Quantity(magnitude=d2y_dtheta2 * omega**2, unit="m/s**2"),
    )
