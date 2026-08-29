"""T1 analytical dry (Coulomb) friction checks (closed-form).

Dry sliding friction resists motion in proportion to how hard two surfaces press together, and that
simple law — independent of contact area and (to first order) of speed — sizes the grip of a clamp,
the drag of a skidding load, and the steepest slope a pile of material will stand at. This is the
general Coulomb-friction law behind the domain-specific friction of the belt/capstan
(:mod:`anvilate.analysis.belt`) and band brake (:mod:`anvilate.analysis.brake`).

The friction force a surface can develop is F = µ·N, from the ``friction_coefficient`` µ and the
``normal_force`` N pressing the surfaces together. On an incline this sets the angle of repose
θ = arctan(µ) — the steepest slope on which an object (or a heap of granular material) just rests
without sliding, equal to the friction angle. To instead drag a load of weight W up a ramp inclined
at θ against both gravity and friction takes a force F = W·(sin θ + µ·cos θ) along the slope. Inputs
and outputs are dimension-checked :class:`~anvilate.units.Quantity` values; the incline angle is a
plain float in degrees.
"""

from __future__ import annotations

from math import atan, cos, degrees, radians, sin

from ..units import Quantity

__all__ = [
    "angle_of_repose",
    "force_to_slide_up_incline",
    "friction_force",
]


def friction_force(*, normal_force: Quantity, friction_coefficient: float) -> Quantity:
    """The dry friction force, F = µ·N.

    The maximum friction force two surfaces develop, from the ``normal_force`` N pressing them
    together and the ``friction_coefficient`` µ: F = µ·N. Use the static µ for the force to start
    motion, the kinetic µ for the drag once sliding. It is independent of the apparent contact area.
    Returns the friction force in N.
    """
    _check(normal_force, "[force]", "normal_force")
    n = normal_force.to("N").magnitude
    if n < 0:
        raise ValueError("normal_force must be non-negative")
    if friction_coefficient < 0:
        raise ValueError("friction_coefficient must be non-negative")
    return Quantity(magnitude=friction_coefficient * n, unit="N")


def angle_of_repose(*, friction_coefficient: float) -> Quantity:
    """The angle of repose (friction angle), θ = arctan(µ).

    The steepest incline on which an object — or a heap of granular material — rests without slip,
    from the ``friction_coefficient`` µ: θ = arctan(µ). Below it the object stays put; above it, it
    slides. It is the same as the friction angle and the natural slope of a stockpile. Returns the
    angle in degrees.
    """
    if friction_coefficient < 0:
        raise ValueError("friction_coefficient must be non-negative")
    return Quantity(magnitude=degrees(atan(friction_coefficient)), unit="degree")


def force_to_slide_up_incline(
    *, weight: Quantity, incline_angle: float, friction_coefficient: float
) -> Quantity:
    """The force to drag a load up an incline, F = W·(sin θ + µ·cos θ).

    The force along the slope needed to move a load of ``weight`` W up an incline of the
    ``incline_angle`` θ (plain float, degrees) against gravity and friction ``friction_coefficient``
    µ: F = W·(sin θ + µ·cos θ). The gravity term sin θ dominates on a steep ramp, the friction term
    µ·cos θ on a shallow one. Returns the required force in N.
    """
    _check(weight, "[force]", "weight")
    w = weight.to("N").magnitude
    if w < 0:
        raise ValueError("weight must be non-negative")
    if not 0.0 <= incline_angle < 90.0:
        raise ValueError(f"incline_angle must be in [0, 90) degrees; got {incline_angle}")
    if friction_coefficient < 0:
        raise ValueError("friction_coefficient must be non-negative")
    theta = radians(incline_angle)
    return Quantity(magnitude=w * (sin(theta) + friction_coefficient * cos(theta)), unit="N")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
