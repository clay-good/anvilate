"""T1 analytical vortex-shedding / flow-induced vibration checks (closed-form).

A fluid flowing past a bluff body — a chimney in the wind, a heat-exchanger tube in crossflow, a
subsea pipeline in a current — sheds vortices alternately from each side, and the alternating side
force can shake the body. Three relations screen the risk.

The shedding frequency is set by the Strouhal relation, f_s = St·V/D, from the dimensionless
Strouhal number St (≈ 0.2 for a circular cylinder over a wide range), the flow ``velocity`` V, and
the body's ``characteristic_length`` D (the diameter across the flow).

The danger is resonance: when the shedding frequency approaches the body's natural frequency, the
vibration locks in and grows. The flow speed where that happens is the lock-in velocity
V = f_n·D/St, the wind or current speed a design must keep clear of.

The reduced velocity V_r = V/(f_n·D) is the dimensionless flow speed that collects the risk into
one number — lock-in centres on V_r ≈ 1/St (about 5 for a cylinder), and a design is screened by
whether its operating V_r lands in that band. The Strouhal number is the caller's from a table; the
relations are here.

Reduced velocity says *whether* the flow speed lands in the lock-in band; it does not say whether
landing there matters. That is the Scruton number Sc = 4π·m·ζ/(ρ·D²), the mass-damping parameter —
the structure's mass and damping measured against the fluid's density. A heavy, well-damped body in
air has a large Sc and barely responds even at resonance; a light or lightly damped one in water has
a small Sc and can be shaken apart. The two together are the screen: reduced velocity for the speed,
Scruton for the consequence.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity
from ..units.rotation import count_rate_per_second

__all__ = [
    "lock_in_velocity",
    "reduced_velocity",
    "scruton_number",
    "vortex_shedding_frequency",
]


def vortex_shedding_frequency(
    *,
    strouhal_number: float,
    velocity: Quantity,
    characteristic_length: Quantity,
) -> Quantity:
    """The vortex-shedding frequency past a bluff body, f_s = St·V/D.

    The rate at which vortices peel off alternate sides of the body: f_s = St·V/D, from the
    ``strouhal_number`` St (~0.2 for a circular cylinder), the flow ``velocity`` V, and the
    ``characteristic_length`` D across the flow. Compare it to the structure's natural frequency —
    if they coincide, the shedding force resonates. Returns the shedding frequency in hertz.
    """
    _check(velocity, "[length]/[time]", "velocity")
    _check(characteristic_length, "[length]", "characteristic_length")
    if strouhal_number <= 0:
        raise ValueError("strouhal_number must be positive")
    v = velocity.to("m/s").magnitude
    d = characteristic_length.to("m").magnitude
    if v <= 0 or d <= 0:
        raise ValueError("velocity and characteristic_length must be positive")
    return Quantity(magnitude=strouhal_number * v / d, unit="Hz")


def lock_in_velocity(
    *,
    strouhal_number: float,
    natural_frequency: Quantity,
    characteristic_length: Quantity,
) -> Quantity:
    """The flow velocity that resonates a structure, V = f_n·D/St (the lock-in speed).

    Setting the shedding frequency equal to the structure's ``natural_frequency`` f_n and solving
    for speed gives the velocity at which vortex-induced vibration locks in: V = f_n·D/St, from the
    ``strouhal_number`` St and the ``characteristic_length`` D. It is the critical wind or current
    speed a chimney, cable, or tube must be detuned away from. Returns the lock-in velocity in m/s.
    """
    _check(natural_frequency, "1/[time]", "natural_frequency")
    _check(characteristic_length, "[length]", "characteristic_length")
    if strouhal_number <= 0:
        raise ValueError("strouhal_number must be positive")
    f_n = count_rate_per_second(natural_frequency, name="natural_frequency")
    d = characteristic_length.to("m").magnitude
    if f_n <= 0 or d <= 0:
        raise ValueError("natural_frequency and characteristic_length must be positive")
    return Quantity(magnitude=f_n * d / strouhal_number, unit="m/s")


def reduced_velocity(
    *,
    velocity: Quantity,
    natural_frequency: Quantity,
    characteristic_length: Quantity,
) -> float:
    """The reduced velocity of a bluff body in flow, V_r = V/(f_n·D).

    The dimensionless flow speed that collects the vortex-induced-vibration risk into one number:
    V_r = V/(f_n·D), from the flow ``velocity`` V, the ``natural_frequency`` f_n, and the
    ``characteristic_length`` D. Lock-in centres on V_r ≈ 1/St (about 5 for a circular cylinder), so
    a design whose operating reduced velocity sits near that band is at risk and one well away is
    not. Returns the dimensionless reduced velocity.
    """
    _check(velocity, "[length]/[time]", "velocity")
    _check(natural_frequency, "1/[time]", "natural_frequency")
    _check(characteristic_length, "[length]", "characteristic_length")
    v = velocity.to("m/s").magnitude
    f_n = count_rate_per_second(natural_frequency, name="natural_frequency")
    d = characteristic_length.to("m").magnitude
    if v <= 0 or f_n <= 0 or d <= 0:
        raise ValueError("velocity, natural_frequency, and characteristic_length must be positive")
    return v / (f_n * d)


def scruton_number(
    *,
    mass_per_unit_length: Quantity,
    damping_ratio: float,
    fluid_density: Quantity,
    characteristic_length: Quantity,
) -> float:
    """The Scruton (mass-damping) number, Sc = 4π·m·ζ/(ρ·D²).

    The dimensionless group that decides how hard a body responds when
    :func:`reduced_velocity` says it is in the lock-in band. From the ``mass_per_unit_length`` m of
    the structure, its ``damping_ratio`` ζ (a plain float, from
    :func:`anvilate.analysis.dynamics.damping_ratio_from_log_decrement` if the decay is measured),
    the ``fluid_density`` ρ, and the ``characteristic_length`` D across the flow:
    Sc = 4π·m·ζ/(ρ·D²). The numerator is what resists being shaken, the denominator the fluid doing
    the shaking.

    Lock-in velocity and reduced velocity between them locate the resonance but say nothing about
    its amplitude; this does. Roughly, Sc below about 10 means vortex-induced vibration amplitudes
    of order the diameter and a real fatigue problem, while a few tens make the response
    negligible — which is why a steel chimney in air is usually fine and the same slenderness in
    water, where ρ is 800 times higher, is not. It is also the design lever: mass and damping enter
    only as their product, so a tuned damper and added ballast buy the same thing. Returns the
    dimensionless Scruton number as a plain float.
    """
    _check(mass_per_unit_length, "[mass]/[length]", "mass_per_unit_length")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    _check(characteristic_length, "[length]", "characteristic_length")
    m = mass_per_unit_length.to("kg/m").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    d = characteristic_length.to("m").magnitude
    if m <= 0:
        raise ValueError("mass_per_unit_length must be positive")
    if damping_ratio <= 0:
        raise ValueError("damping_ratio must be positive")
    if rho <= 0:
        raise ValueError("fluid_density must be positive")
    if d <= 0:
        raise ValueError("characteristic_length must be positive")
    return 4.0 * pi * m * damping_ratio / (rho * d * d)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
