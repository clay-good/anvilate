"""T1 analytical uniform-circular-motion checks (closed-form).

A body moving in a circle is always accelerating — its velocity keeps changing direction — so a net
inward force must supply that acceleration. Sizing that force, and the speed a real curve can hold
before it slides, is the basis of cornering, banked tracks, and rotating machinery. This is the
linear-speed view of circular motion, complementing the angular-rate relations of
:mod:`anvilate.analysis.coriolis` and :mod:`anvilate.analysis.centrifuge` (which work in ω) and the
gravitational orbits of :mod:`anvilate.analysis.orbital_mechanics`.

A body of speed v on a circle of radius r has a centripetal acceleration a = v²/r directed at the
centre, and holding it there takes a centripetal force F = m·v²/r on a mass m — the tension in a
string, the friction on a tire, the pull of a bearing. On a flat curve that force comes from tire
friction, so the fastest a vehicle can round it without sliding is v_max = √(µ·g·r), from the
friction coefficient µ and gravity g — which is why sharp bends carry low speed limits. Inputs and
outputs are dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Hibbeler, *Engineering Mechanics: Dynamics* (curvilinear motion) — the centripetal
acceleration v²/r, the force it demands of a mass, and the cornering speed a friction
coefficient allows.
"""

from __future__ import annotations

from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_STANDARD_GRAVITY = 9.80665  # m/s**2
_CIRCULAR_MOTION_SOURCE = "the governing motion case or calibrated speed record"
_CIRCULAR_GEOMETRY_SOURCE = "the curve or rotating-system drawing"
_CIRCULAR_MASS_SOURCE = "the approved mass-properties record"
_TRACTION_SOURCE = "the tire-road test data or approved friction specification"
_GRAVITY_SOURCE = "the site gravity model or calibrated acceleration record"


class _CircularMotionInputError(RefusalError, ValueError):
    """A circular-motion input that cannot be used without correction."""


def _circular_motion_refusal(
    message: str, *, subject: str, source: str
) -> _CircularMotionInputError:
    return _CircularMotionInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _circular_motion_input_source(name: str) -> str:
    if name == "radius":
        return _CIRCULAR_GEOMETRY_SOURCE
    if name == "mass":
        return _CIRCULAR_MASS_SOURCE
    if name == "gravity":
        return _GRAVITY_SOURCE
    return _CIRCULAR_MOTION_SOURCE


__all__ = [
    "centripetal_acceleration",
    "centripetal_force",
    "maximum_cornering_speed",
]


def centripetal_acceleration(*, velocity: Quantity, radius: Quantity) -> Quantity:
    """The centripetal acceleration, a = v²/r.

    The inward acceleration of a body moving at ``velocity`` v on a circle of ``radius`` r: v²/r,
    directed toward the centre. It climbs with the square of speed and falls with a wider radius —
    the "g-force" a rider feels on a curve. Returns the acceleration in m/s**2.
    """
    _check(velocity, "[velocity]", "velocity")
    _check(radius, "[length]", "radius")
    v = velocity.to("m/s").magnitude
    r = radius.to("m").magnitude
    if r <= 0:
        raise _circular_motion_refusal(
            "radius must be positive", subject="radius", source=_CIRCULAR_GEOMETRY_SOURCE
        )
    return Quantity(magnitude=v * v / r, unit="m/s**2")


def centripetal_force(*, mass: Quantity, velocity: Quantity, radius: Quantity) -> Quantity:
    """The centripetal force, F = m·v²/r.

    The net inward force needed to keep a mass ``mass`` m moving at ``velocity`` v on a circle of
    ``radius`` r: F = m·v²/r. It is what a string, a bearing, or tire friction must supply; exceed
    what the constraint can provide and the body flies off tangentially. Returns the force in N.
    """
    _check(mass, "[mass]", "mass")
    _check(velocity, "[velocity]", "velocity")
    _check(radius, "[length]", "radius")
    m = mass.to("kg").magnitude
    v = velocity.to("m/s").magnitude
    r = radius.to("m").magnitude
    if m <= 0:
        raise _circular_motion_refusal(
            "mass must be positive", subject="mass", source=_CIRCULAR_MASS_SOURCE
        )
    if r <= 0:
        raise _circular_motion_refusal(
            "radius must be positive", subject="radius", source=_CIRCULAR_GEOMETRY_SOURCE
        )
    return Quantity(magnitude=m * v * v / r, unit="N")


def maximum_cornering_speed(
    *, friction_coefficient: float, radius: Quantity, gravity: Quantity | None = None
) -> Quantity:
    """The maximum cornering speed on a flat curve, v_max = √(µ·g·r).

    The fastest a vehicle can round a flat (unbanked) curve of ``radius`` r without sliding, when
    the centripetal force comes entirely from tire friction of ``friction_coefficient`` µ against
    gravity ``gravity`` g (defaulting to 9.80665 m/s²): v_max = √(µ·g·r). A tighter curve or a
    slicker road lowers it. Returns the maximum speed in m/s.
    """
    _check(radius, "[length]", "radius")
    r = radius.to("m").magnitude
    if friction_coefficient <= 0:
        raise _circular_motion_refusal(
            "friction_coefficient must be positive",
            subject="friction_coefficient",
            source=_TRACTION_SOURCE,
        )
    if r <= 0:
        raise _circular_motion_refusal(
            "radius must be positive", subject="radius", source=_CIRCULAR_GEOMETRY_SOURCE
        )
    if gravity is None:
        g = _STANDARD_GRAVITY
    else:
        _check(gravity, "[acceleration]", "gravity")
        g = gravity.to("m/s**2").magnitude
        if g <= 0:
            raise _circular_motion_refusal(
                "gravity must be positive", subject="gravity", source=_GRAVITY_SOURCE
            )
    return Quantity(magnitude=sqrt(friction_coefficient * g * r), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _circular_motion_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_circular_motion_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _circular_motion_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_circular_motion_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
