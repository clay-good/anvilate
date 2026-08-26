"""T1 analytical gyroscopic-effect checks (rigid rotor, closed-form).

A fast-spinning rotor — a turbine wheel, a flywheel, a propeller, a reaction wheel — stores angular
momentum along its axis, and that stored momentum makes the axis stubborn: it resists being tilted,
and when a moment does tilt it, the axis moves at right angles to the push rather than yielding to
it. This is the gyroscopic effect, and it is a real load case in rotating machinery, distinct from
the vibration and balancing of :mod:`anvilate.analysis.dynamics`: a ship's turbine feels it every
time the hull turns, an aircraft engine every time it pitches, and the bearings carry the couple
it produces.

Three relations describe it. The spin angular momentum L = I·ω, from the rotor's polar moment of
inertia I and its spin rate ω, is the reservoir everything else scales with. A moment M applied
across the spin axis does not tilt it but precesses it at Ω = M/(I·ω) — inversely with the stored
momentum, which is why a fast, heavy rotor barely drifts. Run the other way, forcing the axis to
precess at a rate Ω (as a turning vehicle forces its rotor to turn with it) demands a reaction
moment M = I·ω·Ω on the bearings, at right angles to both the spin and the turn — the gyroscopic
couple a
rotating machine's mounts are sized for.

Sources: Hibbeler, *Engineering Mechanics: Dynamics* (gyroscopic motion) — the spin angular
momentum of a rotor, the precession rate an applied moment produces, and the reaction moment a
forced precession develops.
"""

from __future__ import annotations

from ..units import Quantity
from ..units.rotation import angular_speed_rad_per_s

__all__ = [
    "gyroscopic_precession_rate",
    "gyroscopic_reaction_moment",
    "gyroscopic_spin_angular_momentum",
]


def gyroscopic_spin_angular_momentum(
    *, polar_moment_of_inertia: Quantity, spin_speed: Quantity
) -> Quantity:
    """The spin angular momentum, L = I·ω.

    The angular momentum a rotor stores along its spin axis: the ``polar_moment_of_inertia`` I about
    that axis times the ``spin_speed`` ω, L = I·ω. It is the reservoir that gives a gyroscope its
    stiffness in space — the larger it is, the more moment-impulse is needed to reorient the axis,
    the slower any applied moment precesses it (:func:`gyroscopic_precession_rate`). Returns the
    angular momentum in N*m*s.
    """
    _check(polar_moment_of_inertia, "[mass]*[length]**2", "polar_moment_of_inertia")
    _check(spin_speed, "1/[time]", "spin_speed")
    inertia = polar_moment_of_inertia.to("kg*m**2").magnitude
    omega = angular_speed_rad_per_s(spin_speed, name="spin_speed")
    if inertia <= 0:
        raise ValueError("polar_moment_of_inertia must be positive")
    if omega <= 0:
        raise ValueError("spin_speed must be positive")
    return Quantity(magnitude=inertia * omega, unit="N*m*s")


def gyroscopic_precession_rate(
    *, applied_moment: Quantity, polar_moment_of_inertia: Quantity, spin_speed: Quantity
) -> Quantity:
    """The precession rate, Ω = M/(I·ω).

    The rate at which a spinning rotor's axis sweeps around when a moment is applied across it:
    instead of tilting toward the moment, the axis precesses at Ω = M/(I·ω), from the
    ``applied_moment`` M and the spin angular momentum I·ω (``polar_moment_of_inertia`` I and the
    ``spin_speed`` ω). It is inversely proportional to the stored momentum, so a fast, heavy rotor
    precesses slowly — the stability that keeps a spinning top upright and a bullet on course.
    Returns the precession rate in rad/s.
    """
    _check(applied_moment, "[force]*[length]", "applied_moment")
    _check(polar_moment_of_inertia, "[mass]*[length]**2", "polar_moment_of_inertia")
    _check(spin_speed, "1/[time]", "spin_speed")
    moment = applied_moment.to("N*m").magnitude
    inertia = polar_moment_of_inertia.to("kg*m**2").magnitude
    omega = angular_speed_rad_per_s(spin_speed, name="spin_speed")
    if moment <= 0:
        raise ValueError("applied_moment must be positive")
    if inertia <= 0:
        raise ValueError("polar_moment_of_inertia must be positive")
    if omega <= 0:
        raise ValueError("spin_speed must be positive")
    return Quantity(magnitude=moment / (inertia * omega), unit="rad/s")


def gyroscopic_reaction_moment(
    *, polar_moment_of_inertia: Quantity, spin_speed: Quantity, precession_rate: Quantity
) -> Quantity:
    """The gyroscopic reaction moment, M = I·ω·Ω.

    The couple a spinning rotor forces onto its bearings when something makes its axis precess: from
    the spin angular momentum I·ω (``polar_moment_of_inertia`` I and ``spin_speed`` ω) and the
    imposed ``precession_rate`` Ω, M = I·ω·Ω, acting at right angles to both the spin and the
    precession. It is the load a ship's turbine puts on its mounts as the hull turns, or an aircraft
    engine as it pitches, and it grows with both rotor speed and how sharply the axis is swung — the
    gyroscopic couple that sizes the bearings. Returns the reaction moment in N*m.
    """
    _check(polar_moment_of_inertia, "[mass]*[length]**2", "polar_moment_of_inertia")
    _check(spin_speed, "1/[time]", "spin_speed")
    _check(precession_rate, "1/[time]", "precession_rate")
    inertia = polar_moment_of_inertia.to("kg*m**2").magnitude
    omega = angular_speed_rad_per_s(spin_speed, name="spin_speed")
    precession = angular_speed_rad_per_s(precession_rate, name="precession_rate")
    if inertia <= 0:
        raise ValueError("polar_moment_of_inertia must be positive")
    if omega <= 0:
        raise ValueError("spin_speed must be positive")
    if precession <= 0:
        raise ValueError("precession_rate must be positive")
    return Quantity(magnitude=inertia * omega * precession, unit="N*m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
