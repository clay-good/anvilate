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

from math import sqrt

from ..units import Quantity

__all__ = [
    "average_impact_force",
    "coefficient_of_restitution_from_rebound",
    "impulse",
    "linear_momentum",
    "rebound_height",
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


def coefficient_of_restitution_from_rebound(
    *, drop_height: Quantity, rebound_height: Quantity
) -> float:
    """The coefficient of restitution from a bounce test, e = √(h_rebound/h_drop).

    The standard drop-and-bounce measurement of how elastic a collision is: a ball released from
    ``drop_height`` h returns to ``rebound_height`` h′, and since the speeds at the floor scale as
    √h, the coefficient of restitution is e = √(h′/h). It runs from 0 (a perfectly plastic impact
    that keeps no rebound, like clay) to 1 (a perfectly elastic bounce that returns to the drop
    height); a superball sits near 0.9, a tennis ball near 0.75. The rebound cannot exceed the drop
    (energy is lost, not created), so h′ ≤ h. Returns the dimensionless coefficient of restitution.
    """
    _check(drop_height, "[length]", "drop_height")
    _check(rebound_height, "[length]", "rebound_height")
    h = drop_height.to("m").magnitude
    h_r = rebound_height.to("m").magnitude
    if h <= 0:
        raise ValueError("drop_height must be positive")
    if h_r < 0:
        raise ValueError("rebound_height must be non-negative")
    if h_r > h:
        raise ValueError("rebound_height cannot exceed drop_height (a bounce cannot gain energy)")
    return sqrt(h_r / h)


def rebound_height(*, drop_height: Quantity, coefficient_of_restitution: float) -> Quantity:
    """The bounce height for a given restitution, h′ = e²·h.

    The height a ball dropped from ``drop_height`` h returns to, given the
    ``coefficient_of_restitution`` e: because the rebound speed is e times the impact speed and
    height scales with speed squared, h′ = e²·h. Each successive bounce is a factor e² lower, so the
    ball settles in a geometric series — the reason a lively ball takes many quick bounces to stop.
    ``coefficient_of_restitution`` is in [0, 1]. Returns the rebound height in metres.
    """
    _check(drop_height, "[length]", "drop_height")
    h = drop_height.to("m").magnitude
    if h < 0:
        raise ValueError("drop_height must be non-negative")
    if not 0.0 <= coefficient_of_restitution <= 1.0:
        raise ValueError("coefficient_of_restitution must be in [0, 1]")
    return Quantity(magnitude=coefficient_of_restitution**2 * h, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
