"""T1 analytical momentum-impulse (classical mechanics) checks (closed-form).

Momentum methods are the force-over-time companion to the energy methods of
:mod:`anvilate.analysis.work_energy`: a moving mass carries momentum, a force applied over a time
delivers an impulse that changes it, and rearranging that relation gives the average force a
collision develops. This is the reasoning behind crumple zones, airbags, and cushioned packaging —
stretch the stopping time and the force drops.

A mass m moving at velocity v carries linear momentum p = m·v. A force F acting for a time Δt
delivers an impulse J = F·Δt, and by the impulse-momentum theorem that impulse equals the change in
momentum, J = Δp. Turning it around, bringing a mass to rest (or changing its velocity by Δv) in a
time Δt takes an average force F = m·Δv/Δt — small when the stop is gradual, huge when it is abrupt,
which is why a longer collision time is the whole point of safety cushioning. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "average_impact_force",
    "impulse",
    "linear_momentum",
]


def linear_momentum(*, mass: Quantity, velocity: Quantity) -> Quantity:
    """The linear momentum, p = m·v.

    The momentum a mass ``mass`` m carries at ``velocity`` v: p = m·v — the "quantity of motion"
    conserved in collisions. Returns the momentum in kg*m/s.
    """
    _check(mass, "[mass]", "mass")
    _check(velocity, "[velocity]", "velocity")
    m = mass.to("kg").magnitude
    v = velocity.to("m/s").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    return Quantity(magnitude=m * v, unit="kg*m/s")


def impulse(*, force: Quantity, time_interval: Quantity) -> Quantity:
    """The impulse, J = F·Δt.

    The impulse a constant ``force`` F delivers while acting for a ``time_interval`` Δt: J = F·Δt.
    By the impulse-momentum theorem it equals the change in momentum it produces. Returns the
    impulse in N*s (equivalently kg*m/s).
    """
    _check(force, "[force]", "force")
    _check(time_interval, "[time]", "time_interval")
    f = force.to("N").magnitude
    dt = time_interval.to("s").magnitude
    if dt <= 0:
        raise ValueError("time_interval must be positive")
    return Quantity(magnitude=f * dt, unit="N*s")


def average_impact_force(
    *, mass: Quantity, velocity_change: Quantity, time_interval: Quantity
) -> Quantity:
    """The average force of a collision, F = m·Δv/Δt.

    The average force needed to change a mass ``mass`` m's velocity by ``velocity_change`` Δv over a
    ``time_interval`` Δt, from the impulse-momentum theorem: F = m·Δv/Δt. Stretching the stopping
    time cuts the force proportionally — the principle behind crumple zones, airbags, and padded
    packaging. Returns the average force in N.
    """
    _check(mass, "[mass]", "mass")
    _check(velocity_change, "[velocity]", "velocity_change")
    _check(time_interval, "[time]", "time_interval")
    m = mass.to("kg").magnitude
    dv = velocity_change.to("m/s").magnitude
    dt = time_interval.to("s").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    if dt <= 0:
        raise ValueError("time_interval must be positive")
    return Quantity(magnitude=abs(m * dv / dt), unit="N")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
