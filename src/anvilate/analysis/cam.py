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

from math import atan2, cos, degrees, pi, radians, sin, sqrt, tan

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "CamMotion",
    "cam_follower_motion",
    "cam_pressure_angle",
    "cam_base_circle_for_pressure_angle",
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


def cam_pressure_angle(
    *,
    lift_gradient: Quantity,
    follower_displacement: Quantity,
    base_circle_radius: Quantity,
    offset: Quantity | None = None,
) -> Quantity:
    """The pressure angle of a radial translating roller-follower cam.

    The pressure angle φ is the angle between the cam-to-follower contact normal and
    the follower's line of travel; it sets how much of the contact force pushes the
    follower *sideways* against its guide rather than along its stroke. For a radial
    translating roller follower,

        tan(φ) = (ds/dθ − e) / (√(r_b² − e²) + s),

    where ``lift_gradient`` ds/dθ is the follower's lift per unit *cam angle* (a
    length per radian — divide a :attr:`CamMotion.velocity` by the cam's angular
    speed ω to get it), ``follower_displacement`` s the current lift,
    ``base_circle_radius`` r_b the cam's base circle, and ``offset`` e the follower
    axis's offset from the cam centre (default 0 for an on-centre follower; a positive
    offset in the direction of ds/dθ reduces φ on the rise). Keep the peak φ below
    about 30° for a translating follower or it jams in its guide — enlarging the base
    circle is the usual fix. ``offset`` must be below r_b. Returns φ in degrees.
    """
    _require(lift_gradient, "[length]", "lift_gradient")
    _require(follower_displacement, "[length]", "follower_displacement")
    _require(base_circle_radius, "[length]", "base_circle_radius")
    dsdtheta = lift_gradient.to("mm").magnitude
    s = follower_displacement.to("mm").magnitude
    r_b = base_circle_radius.to("mm").magnitude
    if r_b <= 0:
        raise ValueError(f"base_circle_radius must be positive; got {base_circle_radius}")
    if s < 0:
        raise ValueError(f"follower_displacement must be non-negative; got {follower_displacement}")
    e = 0.0
    if offset is not None:
        _require(offset, "[length]", "offset")
        e = offset.to("mm").magnitude
    if abs(e) >= r_b:
        raise ValueError(
            f"offset ({offset}) must be smaller than the base_circle_radius ({base_circle_radius})"
        )
    angle = atan2(dsdtheta - e, sqrt(r_b**2 - e**2) + s)
    return Quantity(magnitude=degrees(angle), unit="degree")


def cam_base_circle_for_pressure_angle(
    *,
    lift_gradient: Quantity,
    follower_displacement: Quantity,
    max_pressure_angle: float,
) -> Quantity:
    """The minimum base-circle radius r_b that holds a cam's pressure angle in check.

    The design inverse of :func:`cam_pressure_angle` for an on-centre translating roller
    follower: setting tan(φ) = (ds/dθ)/(r_b + s) equal to the ``max_pressure_angle`` φ_max
    and solving gives r_b = (ds/dθ)/tan(φ_max) − s. Evaluate the ``lift_gradient`` ds/dθ
    (lift per unit cam angle) and ``follower_displacement`` s at the point of *steepest*
    rise, where φ peaks, and this returns the smallest base circle that keeps the whole
    rise under φ_max — the standard "enlarge the base circle to tame the pressure angle"
    sizing step (keep φ_max ≤ ~30° for a translating follower). φ_max must be in (0, 90);
    the base circle comes out negative if the demanded rise is too steep for *any*
    positive base circle at that displacement, which is itself the signal to slow the
    motion. Returns the base-circle radius in mm.
    """
    _require(lift_gradient, "[length]", "lift_gradient")
    _require(follower_displacement, "[length]", "follower_displacement")
    if not 0 < max_pressure_angle < 90:
        raise ValueError(
            f"max_pressure_angle (degrees) must lie in (0, 90); got {max_pressure_angle}"
        )
    dsdtheta = lift_gradient.to("mm").magnitude
    s = follower_displacement.to("mm").magnitude
    if s < 0:
        raise ValueError(f"follower_displacement must be non-negative; got {follower_displacement}")
    r_b = dsdtheta / tan(radians(max_pressure_angle)) - s
    return Quantity(magnitude=r_b, unit="mm")
