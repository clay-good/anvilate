"""T1 analytical rocket-propulsion checks (ideal nozzle, closed-form).

A rocket engine is a converging-diverging nozzle (the geometry of
:mod:`anvilate.analysis.compressible_flow`) with combustion behind it: hot gas at high chamber
pressure expands through the throat and out the bell, turning thermal energy into a high-speed jet
whose reaction is thrust. The ideal (isentropic, one-dimensional) relations give the exhaust
velocity, the thrust, and the specific impulse in closed form — the first-cut numbers of a
propulsion sizing.

The exhaust velocity is the energy the expansion releases, v_e = √(2γ/(γ−1)·R·T_c·(1 − (p_e/p_c)^
((γ−1)/γ))): from the chamber temperature T_c and pressure p_c, the exit pressure p_e the nozzle
expands to, the gas constant R, and the ratio γ. The thrust adds a small pressure term to the
momentum, F = ṁ·v_e + (p_e − p_a)·A_e — the jet momentum ṁ·v_e plus the pressure thrust when the
exit pressure differs from the ambient p_a, which is why an engine makes more thrust in vacuum than
at sea level. Dividing thrust by the propellant weight flow gives the specific impulse
I_sp = F/(ṁ·g₀), the seconds of thrust per unit weight of propellant — the headline efficiency.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "rocket_exhaust_velocity",
    "rocket_specific_impulse",
    "rocket_thrust",
]


def rocket_exhaust_velocity(
    *,
    chamber_temperature: Quantity,
    chamber_pressure: Quantity,
    exit_pressure: Quantity,
    specific_gas_constant: Quantity,
    heat_capacity_ratio: float,
) -> Quantity:
    """The ideal exhaust velocity, v_e = √(2γ/(γ−1)·R·T_c·(1 − (p_e/p_c)^((γ−1)/γ))).

    The jet speed an ideal nozzle produces expanding combustion gas from the chamber to the exit:
    from the ``chamber_temperature`` T_c, ``chamber_pressure`` p_c, the ``exit_pressure`` p_e the
    bell expands to, the exhaust ``specific_gas_constant`` R, and the ``heat_capacity_ratio`` γ. A
    hotter, lighter gas (higher R·T_c) and a larger expansion ratio p_c/p_e both raise it, so rocket
    nozzles are long and chambers run hot. Returns the exhaust velocity in m/s.
    """
    _check(chamber_temperature, "[temperature]", "chamber_temperature")
    _check(chamber_pressure, "[pressure]", "chamber_pressure")
    _check(exit_pressure, "[pressure]", "exit_pressure")
    _check(specific_gas_constant, "[length]**2/[time]**2/[temperature]", "specific_gas_constant")
    t_c = chamber_temperature.to("K").magnitude
    p_c = chamber_pressure.to("Pa").magnitude
    p_e = exit_pressure.to("Pa").magnitude
    r = specific_gas_constant.to("J/(kg*K)").magnitude
    if t_c <= 0:
        raise ValueError("chamber_temperature must be positive")
    if p_c <= 0:
        raise ValueError("chamber_pressure must be positive")
    if p_e <= 0:
        raise ValueError("exit_pressure must be positive")
    if p_e >= p_c:
        raise ValueError("exit_pressure must be less than chamber_pressure (the nozzle expands)")
    if r <= 0:
        raise ValueError("specific_gas_constant must be positive")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    g = heat_capacity_ratio
    v_e = sqrt(2.0 * g / (g - 1.0) * r * t_c * (1.0 - (p_e / p_c) ** ((g - 1.0) / g)))
    return Quantity(magnitude=v_e, unit="m/s")


def rocket_thrust(
    *,
    mass_flow_rate: Quantity,
    exhaust_velocity: Quantity,
    exit_pressure: Quantity,
    ambient_pressure: Quantity,
    exit_area: Quantity,
) -> Quantity:
    """The rocket thrust, F = ṁ·v_e + (p_e − p_a)·A_e.

    The reaction force the engine develops: the jet momentum — the ``mass_flow_rate`` ṁ times the
    ``exhaust_velocity`` v_e (from :func:`rocket_exhaust_velocity`) — plus the pressure thrust when
    the ``exit_pressure`` p_e differs from ``ambient_pressure`` p_a over the ``exit_area`` A_e, so
    F = ṁ·v_e + (p_e − p_a)·A_e. Because p_a falls to zero in space, the same engine makes more push
    in vacuum than at sea level. Returns the thrust in kN.
    """
    _check(mass_flow_rate, "[mass]/[time]", "mass_flow_rate")
    _check(exhaust_velocity, "[length]/[time]", "exhaust_velocity")
    _check(exit_pressure, "[pressure]", "exit_pressure")
    _check(ambient_pressure, "[pressure]", "ambient_pressure")
    _check(exit_area, "[area]", "exit_area")
    m_dot = mass_flow_rate.to("kg/s").magnitude
    v_e = exhaust_velocity.to("m/s").magnitude
    p_e = exit_pressure.to("Pa").magnitude
    p_a = ambient_pressure.to("Pa").magnitude
    a_e = exit_area.to("m**2").magnitude
    if m_dot <= 0:
        raise ValueError("mass_flow_rate must be positive")
    if v_e <= 0:
        raise ValueError("exhaust_velocity must be positive")
    if p_e <= 0:
        raise ValueError("exit_pressure must be positive")
    if p_a < 0:
        raise ValueError("ambient_pressure must be non-negative")
    if a_e <= 0:
        raise ValueError("exit_area must be positive")
    f = m_dot * v_e + (p_e - p_a) * a_e
    return Quantity(magnitude=f / 1000.0, unit="kN")


def rocket_specific_impulse(*, thrust: Quantity, mass_flow_rate: Quantity) -> Quantity:
    """The specific impulse, I_sp = F/(ṁ·g₀).

    The seconds of thrust an engine delivers per unit weight of propellant burned: the ``thrust`` F
    over the propellant weight flow — the ``mass_flow_rate`` ṁ times standard gravity g₀ — so
    I_sp = F/(ṁ·g₀). It is the headline efficiency of a rocket stage, independent of scale: a higher
    I_sp means more velocity change per unit propellant. Chemical rockets reach a few-hundred
    seconds; electric thrusters, thousands. Returns the specific impulse in s.
    """
    _check(thrust, "[force]", "thrust")
    _check(mass_flow_rate, "[mass]/[time]", "mass_flow_rate")
    f = thrust.to("N").magnitude
    m_dot = mass_flow_rate.to("kg/s").magnitude
    if f <= 0:
        raise ValueError("thrust must be positive")
    if m_dot <= 0:
        raise ValueError("mass_flow_rate must be positive")
    return Quantity(magnitude=f / (m_dot * STANDARD_GRAVITY_M_PER_S2), unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
