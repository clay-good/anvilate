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
object can be pushed to light speed. Length contracts by the same factor (L = L0/gamma), momentum
grows past the classical m*v to gamma*m*v, and light itself shifts frequency by the relativistic
Doppler factor sqrt((1 +/- beta)/(1 -/+ beta)) — a redshift for a receding source, a blueshift for
an approaching one.

Speeds must be below c; the factor is undefined at or above it.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.rotation import count_rate_per_second

_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "length_contraction",
    "lorentz_factor",
    "relativistic_doppler_frequency",
    "relativistic_kinetic_energy",
    "relativistic_momentum",
    "relativistic_velocity_addition",
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


def length_contraction(*, proper_length: Quantity, velocity: Quantity) -> Quantity:
    """The contracted length, L = L0/gamma.

    The length of a moving object along its direction of motion as seen by a stationary observer:
    the ``proper_length`` L0 in the object's own frame, shrunk by the Lorentz factor of the
    ``velocity`` v, L = L0/gamma. It is the spatial mirror of time dilation. The speed must be below
    c. Returns the contracted length in m.
    """
    _check(proper_length, "[length]", "proper_length")
    ell0 = proper_length.to("m").magnitude
    if ell0 < 0:
        raise ValueError("proper_length must be non-negative")
    gamma = lorentz_factor(velocity=velocity)
    return Quantity(magnitude=ell0 / gamma, unit="m")


def relativistic_momentum(*, mass: Quantity, velocity: Quantity) -> Quantity:
    """The relativistic momentum, p = gamma * m * v.

    The momentum of a mass moving at relativistic speed: the ``mass`` m and ``velocity`` v give
    p = gamma * m * v, exceeding the classical m*v and diverging as v approaches c. It is why a fast
    particle grows ever harder to deflect. The speed must be below c. Returns the momentum in
    kg*m/s.
    """
    _check(mass, "[mass]", "mass")
    _check(velocity, "[length]/[time]", "velocity")
    m = mass.to("kg").magnitude
    v = velocity.to("m/s").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    gamma = lorentz_factor(velocity=velocity)
    return Quantity(magnitude=gamma * m * v, unit="kg*m/s")


def relativistic_doppler_frequency(
    *, source_frequency: Quantity, velocity: Quantity, approaching: bool = False
) -> Quantity:
    """The relativistic Doppler frequency, f = f0*sqrt((1 +/- beta)/(1 -/+ beta)).

    The frequency a moving light source appears to have, from the ``source_frequency`` f0 and the
    relative ``velocity`` v: for a source ``approaching`` the observer f = f0*sqrt((1+β)/(1−β))
    (blueshift), and for a receding one f = f0*sqrt((1−β)/(1+β)) (redshift), with
    beta = v/c. Unlike the classical Doppler effect it applies to light and folds in time dilation.
    The speed must be below c. Returns the observed frequency in Hz.
    """
    _check(source_frequency, "1/[time]", "source_frequency")
    _check(velocity, "[length]/[time]", "velocity")
    f0 = count_rate_per_second(source_frequency, name="source_frequency")
    v = velocity.to("m/s").magnitude
    if f0 <= 0:
        raise ValueError("source_frequency must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    if v >= _SPEED_OF_LIGHT:
        raise ValueError("velocity must be below the speed of light")
    beta = v / _SPEED_OF_LIGHT
    ratio = sqrt((1.0 + beta) / (1.0 - beta)) if approaching else sqrt((1.0 - beta) / (1.0 + beta))
    return Quantity(magnitude=f0 * ratio, unit="Hz")


def relativistic_velocity_addition(
    *, first_velocity: Quantity, second_velocity: Quantity
) -> Quantity:
    """The relativistic velocity addition, u = (u1 + u2)/(1 + u1*u2/c^2).

    How two velocities combine when neither is small next to light speed: a body moving at
    ``first_velocity`` u1 in one frame, itself carrying something at ``second_velocity`` u2, gives a
    net speed u = (u1 + u2)/(1 + u1*u2/c^2) — not the classical u1 + u2. The denominator holds the
    result below c no matter how close the parts are: 0.5c added to 0.5c is 0.8c, and light stays at
    c in every frame. Speeds are along a common line (positive same-direction, negative opposing),
    each below c. Returns the combined velocity in m/s.
    """
    _check(first_velocity, "[length]/[time]", "first_velocity")
    _check(second_velocity, "[length]/[time]", "second_velocity")
    u1 = first_velocity.to("m/s").magnitude
    u2 = second_velocity.to("m/s").magnitude
    if abs(u1) >= _SPEED_OF_LIGHT or abs(u2) >= _SPEED_OF_LIGHT:
        raise ValueError("each speed must be below the speed of light")
    c2 = _SPEED_OF_LIGHT * _SPEED_OF_LIGHT
    u = (u1 + u2) / (1.0 + u1 * u2 / c2)
    return Quantity(magnitude=u, unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
