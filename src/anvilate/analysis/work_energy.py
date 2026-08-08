"""T1 analytical work-energy (classical mechanics) checks (closed-form).

Energy methods are the shortcut of classical mechanics: rather than track forces through time, you
count the energy a body carries and the work done on it. A moving mass carries kinetic energy, a
raised mass carries gravitational potential energy, and a force over a distance does work that
converts between them. These are the low-speed basics behind the relativistic kinetic energy of
:mod:`anvilate.analysis.relativity` and the impact energy of :mod:`anvilate.analysis.impact`.

A mass m moving at speed v carries kinetic energy KE = ½·m·v², which climbs with the square of speed
(the reason stopping distance grows so fast). Lifting it to a height h against gravity stores
gravitational potential energy PE = m·g·h, released as it falls. A constant force F pushing through
a distance d along its line does work W = F·d, the energy it transfers — positive when it drives the
motion, and by the work-energy theorem equal to the change in kinetic energy. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

_STANDARD_GRAVITY = 9.80665  # m/s**2

__all__ = [
    "gravitational_potential_energy",
    "kinetic_energy",
    "work_done",
]


def kinetic_energy(*, mass: Quantity, velocity: Quantity) -> Quantity:
    """The kinetic energy, KE = ½·m·v².

    The energy a mass ``mass`` m carries by virtue of moving at ``velocity`` v: KE = ½·m·v². It
    grows with the square of speed, so a body at twice the speed carries four times the energy — the
    physics behind braking distance and impact severity. Returns the kinetic energy in J.
    """
    _check(mass, "[mass]", "mass")
    _check(velocity, "[velocity]", "velocity")
    m = mass.to("kg").magnitude
    v = velocity.to("m/s").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    return Quantity(magnitude=0.5 * m * v * v, unit="J")


def gravitational_potential_energy(
    *, mass: Quantity, height: Quantity, gravity: Quantity | None = None
) -> Quantity:
    """The gravitational potential energy, PE = m·g·h.

    The energy stored by raising a mass ``mass`` m to a ``height`` h against gravity ``gravity`` g
    (defaulting to 9.80665 m/s²): PE = m·g·h. It is released as kinetic energy when the mass falls,
    the basis of pumped-hydro storage and pile drivers. Returns the potential energy in J.
    """
    _check(mass, "[mass]", "mass")
    _check(height, "[length]", "height")
    m = mass.to("kg").magnitude
    h = height.to("m").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    if gravity is None:
        g = _STANDARD_GRAVITY
    else:
        _check(gravity, "[acceleration]", "gravity")
        g = gravity.to("m/s**2").magnitude
        if g <= 0:
            raise ValueError("gravity must be positive")
    return Quantity(magnitude=m * g * h, unit="J")


def work_done(*, force: Quantity, distance: Quantity) -> Quantity:
    """The work done by a constant force, W = F·d.

    The energy a constant ``force`` F transfers while acting through a ``distance`` d along its own
    line of action: W = F·d. By the work-energy theorem it equals the change in the body's kinetic
    energy. Returns the work in J.
    """
    _check(force, "[force]", "force")
    _check(distance, "[length]", "distance")
    f = force.to("N").magnitude
    d = distance.to("m").magnitude
    return Quantity(magnitude=f * d, unit="J")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
