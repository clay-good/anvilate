"""T1 analytical rotor hover (actuator-disk momentum theory) checks (closed-form).

A helicopter rotor or a drone propeller holds itself up by accelerating air downward through the
disk it sweeps. Actuator-disk momentum theory idealizes the rotor as an infinitely thin disk and,
from conservation of momentum, fixes the downwash it induces and the minimum power hover costs — the
thrust-producing counterpart to the energy-extracting wind turbine of
:mod:`anvilate.analysis.wind_power`, which runs the same momentum balance in reverse.

Balancing the thrust against the momentum flux through the disk gives the induced (downwash)
velocity v_h = √(T/(2·ρ·A)), from the thrust T, the air density ρ, and the disk area A. The ideal
power to hover is the thrust carried through that velocity, P = T·v_h = T^{3/2}/√(2·ρ·A) — which is
why a large, lightly loaded rotor hovers far more efficiently than a small, highly loaded one.
Comparing this ideal against the real shaft power gives the figure of merit FM = P_ideal/P_actual,
the standard measure of hover efficiency (about 0.7-0.8 for a good rotor). Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Leishman, *Principles of Helicopter Aerodynamics* (momentum theory) — the induced
velocity a rotor needs in hover, the ideal power that costs, and the figure of merit an actual
rotor achieves against it.
"""

from __future__ import annotations

from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_WEIGHT_SOURCE = "the vehicle's gross-weight and hover thrust requirement"
_ATMOSPHERE_SOURCE = "the density altitude of the operating case"
_ROTOR_SOURCE = "the rotor drawing (blade radius and disk area)"
_POWER_SOURCE = "the measured or rated shaft power at hover"


class _RotorMomentumInputError(RefusalError, ValueError):
    """A rotor hover input that cannot be used without correction."""


def _rotor_momentum_refusal(message: str, *, subject: str, source: str) -> _RotorMomentumInputError:
    return _RotorMomentumInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _rotor_momentum_input_source(name: str) -> str:
    if name == "air_density":
        return _ATMOSPHERE_SOURCE
    if name == "disk_area":
        return _ROTOR_SOURCE
    if name == "actual_power":
        return _POWER_SOURCE
    return _WEIGHT_SOURCE


__all__ = [
    "figure_of_merit",
    "hover_induced_velocity",
    "ideal_hover_power",
]


def hover_induced_velocity(
    *, thrust: Quantity, air_density: Quantity, disk_area: Quantity
) -> Quantity:
    """The hover induced (downwash) velocity, v_h = √(T/(2*ρ*A)).

    The velocity the rotor imparts to the air at the disk in hover, from the ``thrust`` T, the
    ``air_density`` ρ, and the ``disk_area`` A: v_h = √(T/(2*ρ*A)). A larger disk or lighter loading
    gives a gentler downwash. Returns the induced velocity in m/s.
    """
    _check(thrust, "[force]", "thrust")
    _check(air_density, "[mass]/[volume]", "air_density")
    _check(disk_area, "[area]", "disk_area")
    t = thrust.to("N").magnitude
    rho = air_density.to("kg/m**3").magnitude
    a = disk_area.to("m**2").magnitude
    if t <= 0:
        raise _rotor_momentum_refusal(
            "thrust must be positive", subject="thrust", source=_WEIGHT_SOURCE
        )
    if rho <= 0:
        raise _rotor_momentum_refusal(
            "air_density must be positive", subject="air_density", source=_ATMOSPHERE_SOURCE
        )
    if a <= 0:
        raise _rotor_momentum_refusal(
            "disk_area must be positive", subject="disk_area", source=_ROTOR_SOURCE
        )
    return Quantity(magnitude=sqrt(t / (2.0 * rho * a)), unit="m/s")


def ideal_hover_power(*, thrust: Quantity, air_density: Quantity, disk_area: Quantity) -> Quantity:
    """The ideal hover power, P = T^{3/2}/√(2*ρ*A).

    The minimum (induced) power an actuator disk needs to hover, the thrust carried through the
    induced velocity, from the ``thrust`` T, the ``air_density`` ρ, and the ``disk_area`` A:
    P = T*v_h = T^{3/2}/√(2*ρ*A). Because it grows as thrust to the 3/2 power and falls with disk
    area, a big lightly-loaded rotor hovers far more cheaply than a small one. Returns power in W.
    """
    _check(thrust, "[force]", "thrust")
    _check(air_density, "[mass]/[volume]", "air_density")
    _check(disk_area, "[area]", "disk_area")
    t = thrust.to("N").magnitude
    rho = air_density.to("kg/m**3").magnitude
    a = disk_area.to("m**2").magnitude
    if t <= 0:
        raise _rotor_momentum_refusal(
            "thrust must be positive", subject="thrust", source=_WEIGHT_SOURCE
        )
    if rho <= 0:
        raise _rotor_momentum_refusal(
            "air_density must be positive", subject="air_density", source=_ATMOSPHERE_SOURCE
        )
    if a <= 0:
        raise _rotor_momentum_refusal(
            "disk_area must be positive", subject="disk_area", source=_ROTOR_SOURCE
        )
    return Quantity(magnitude=t**1.5 / sqrt(2.0 * rho * a), unit="W")


def figure_of_merit(
    *, thrust: Quantity, air_density: Quantity, disk_area: Quantity, actual_power: Quantity
) -> float:
    """The rotor figure of merit, FM = P_ideal/P_actual.

    The hover efficiency of a real rotor: the ideal actuator-disk power over the ``actual_power`` P
    the rotor draws, from the ``thrust`` T, the ``air_density`` ρ, and the ``disk_area`` A:
    FM = (T^{3/2}/√(2*ρ*A))/P. It lies between 0 and 1 (about 0.7-0.8 for a good rotor); higher
    means less power wasted on profile drag and swirl. Returns the figure of merit as a plain float.
    """
    _check(actual_power, "[power]", "actual_power")
    p_actual = actual_power.to("W").magnitude
    if p_actual <= 0:
        raise _rotor_momentum_refusal(
            "actual_power must be positive", subject="actual_power", source=_POWER_SOURCE
        )
    p_ideal = (
        ideal_hover_power(thrust=thrust, air_density=air_density, disk_area=disk_area)
        .to("W")
        .magnitude
    )
    return p_ideal / p_actual


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _rotor_momentum_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_rotor_momentum_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _rotor_momentum_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_rotor_momentum_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
