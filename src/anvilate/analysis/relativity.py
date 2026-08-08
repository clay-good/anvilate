"""T1 analytical special-relativity checks (closed-form).

At speeds approaching that of light, time, length, and energy stop behaving classically. Special
relativity captures this through a single factor, the Lorentz factor, that grows without bound as
the speed nears c. The effects are not just theoretical: a GPS satellite's clock must be corrected
for time dilation, a particle accelerator's beam energy is almost all relativistic, and a cosmic-ray
muon reaches the ground only because its clock runs slow. These are distinct from the low-speed
matter waves of :mod:`anvilate.analysis.quantum` (whose de Broglie relation is non-relativistic).

The Lorentz factor is gamma = 1/sqrt(1 - (v/c)^2), the multiplier on every relativistic effect: it
is 1 at rest and diverges as v -> c. A moving clock's ticks stretch by it, so a proper time interval
t0 is observed as gamma * t0 (time dilation). The kinetic energy is not (1/2)m v^2 but the full
(gamma - 1) m c^2, which climbs toward infinity as the speed approaches c — the reason no massive
object can be pushed to light speed.

Speeds must be below c; the factor is undefined at or above it.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "lorentz_factor",
    "relativistic_kinetic_energy",
    "time_dilation",
]


def lorentz_factor(*, velocity: Quantity) -> float:
    """The Lorentz factor, gamma = 1/sqrt(1 - (v/c)^2).

    The dimensionless multiplier behind every special-relativistic effect, from the ``velocity`` v:
    gamma = 1/sqrt(1 - (v/c)^2). It is 1 at rest, about 1.005 at a tenth of light speed, and grows
    without bound as v approaches c. The speed must be below c. Returns the factor as a float.
    """
    _check(velocity, "[length]/[time]", "velocity")
    v = velocity.to("m/s").magnitude
    if v < 0:
        raise ValueError("velocity must be non-negative")
    if v >= _SPEED_OF_LIGHT:
        raise ValueError("velocity must be below the speed of light")
    beta = v / _SPEED_OF_LIGHT
    return 1.0 / sqrt(1.0 - beta * beta)


def time_dilation(*, proper_time: Quantity, velocity: Quantity) -> Quantity:
    """The dilated time interval, t = gamma * t0.

    The time a moving clock's interval takes as seen by a stationary observer: the ``proper_time``
    t0 measured in the clock's own frame, stretched by the Lorentz factor of the ``velocity`` v,
    t = gamma * t0. It is why a fast-moving clock (a GPS satellite, a cosmic-ray muon) runs slow
    relative to the ground. The speed must be below c. Returns the dilated time in s.
    """
    _check(proper_time, "[time]", "proper_time")
    t0 = proper_time.to("s").magnitude
    if t0 < 0:
        raise ValueError("proper_time must be non-negative")
    gamma = lorentz_factor(velocity=velocity)
    return Quantity(magnitude=gamma * t0, unit="s")


def relativistic_kinetic_energy(*, mass: Quantity, velocity: Quantity) -> Quantity:
    """The relativistic kinetic energy, KE = (gamma - 1) * m * c^2.

    The kinetic energy of a mass moving at relativistic speed: the ``mass`` m and ``velocity`` v
    give KE = (gamma - 1) * m * c^2, which reduces to (1/2)m v^2 at low speed but climbs toward
    infinity as v approaches c. It is the energy an accelerator must supply, far above the classical
    estimate for a fast beam. The speed must be below c. Returns the kinetic energy in J.
    """
    _check(mass, "[mass]", "mass")
    m = mass.to("kg").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    gamma = lorentz_factor(velocity=velocity)
    return Quantity(magnitude=(gamma - 1.0) * m * _SPEED_OF_LIGHT * _SPEED_OF_LIGHT, unit="J")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
