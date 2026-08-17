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

Performance splits cleanly into two factors. The characteristic velocity c* = p_c·A_t/ṁ measures the
combustion chamber alone — how much chamber pressure the propellant makes for a given throat flow —
while the thrust coefficient C_F = F/(p_c·A_t) measures the nozzle's conversion of that pressure
into thrust. Their product is the effective exhaust velocity (c* · C_F = I_sp · g₀), so a test
firing that measures thrust, chamber pressure, and flow can attribute a shortfall to the chamber or
the nozzle.
"""

from __future__ import annotations

from math import exp, log, sqrt

from ..units import Quantity

STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "characteristic_velocity",
    "nozzle_expansion_ratio",
    "rocket_delta_v",
    "rocket_exhaust_velocity",
    "rocket_propellant_mass_fraction",
    "rocket_specific_impulse",
    "rocket_thrust",
    "thrust_coefficient",
    "thrust_from_coefficient",
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


def nozzle_expansion_ratio(
    *,
    chamber_pressure: Quantity,
    exit_pressure: Quantity,
    heat_capacity_ratio: float,
) -> float:
    """The nozzle area ratio ε = A_e/A_t for a given pressure expansion.

    :func:`rocket_thrust` consumes an ``exit_area`` and nothing in the module produced one, so the
    bell's geometry — the single most visible number about an engine — had to be guessed or found
    by hand-inverting the isentropic Mach relation. This closes that:

        ε = 1 / [ ((γ+1)/2)^(1/(γ−1)) · (p_e/p_c)^(1/γ) · √( ((γ+1)/(γ−1))·(1 − (p_e/p_c)^((γ−1)/γ)) ) ]

    from the ``chamber_pressure`` p_c, the ``exit_pressure`` p_e the bell expands to, and the
    ``heat_capacity_ratio`` γ. Multiply a chosen throat area by ε to get the exit area, or divide a
    chosen exit area by it to get the throat.

    The ratio is what makes vacuum engines look the way they do: expanding from 7 MPa to 0.1 MPa
    (roughly sea level) at γ = 1.20 needs ε = 9.06, while expanding the same chamber to near
    vacuum runs the bell out to ε in the hundreds. This is the same physics as
    :func:`anvilate.analysis.compressible_flow.isentropic_area_ratio` reached from pressure rather
    than Mach number, and agrees with it exactly at the implied exit Mach of 3.2095. Returns the
    area ratio as a plain float.
    """  # noqa: E501
    _check(chamber_pressure, "[pressure]", "chamber_pressure")
    _check(exit_pressure, "[pressure]", "exit_pressure")
    p_c = chamber_pressure.to("Pa").magnitude
    p_e = exit_pressure.to("Pa").magnitude
    g = heat_capacity_ratio
    if g <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {g}")
    if p_c <= 0 or p_e <= 0:
        raise ValueError("chamber_pressure and exit_pressure must be positive")
    if p_e >= p_c:
        raise ValueError(
            f"exit_pressure must be below chamber_pressure for the nozzle to expand; "
            f"got {exit_pressure} against {chamber_pressure}"
        )
    ratio = p_e / p_c
    # Below the critical pressure ratio the flow chokes and the bell runs supersonic, which is the
    # branch this expression describes. ABOVE it the same algebra keeps returning finite, plausible
    # numbers -- eps has a minimum of exactly 1 at the critical ratio and climbs again toward
    # infinity as p_e approaches p_c -- but they describe a subsonic diffuser, not a nozzle. An
    # eps of 4.6 from a mistyped exit pressure is indistinguishable from a real bell, so the
    # subsonic branch is refused rather than returned.
    critical_ratio = (2.0 / (g + 1.0)) ** (g / (g - 1.0))
    if ratio >= critical_ratio:
        raise ValueError(
            f"exit_pressure must be below the critical ratio {critical_ratio:.5f} of the chamber "
            f"pressure ({critical_ratio * p_c / 1e6:.4f} MPa here) for the nozzle to run "
            f"supersonic; got {exit_pressure}, a pressure ratio of {ratio:.5f}, which puts the "
            f"flow on the subsonic branch where the area ratio describes a diffuser."
        )
    denominator = (
        ((g + 1.0) / 2.0) ** (1.0 / (g - 1.0))
        * ratio ** (1.0 / g)
        * sqrt(((g + 1.0) / (g - 1.0)) * (1.0 - ratio ** ((g - 1.0) / g)))
    )
    return 1.0 / denominator


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


def rocket_delta_v(
    *, specific_impulse: Quantity, initial_mass: Quantity, final_mass: Quantity
) -> Quantity:
    """The Tsiolkovsky rocket equation, Δv = I_sp·g₀·ln(m₀/m_f).

    The velocity change a stage can achieve, the single most important number in mission design:
    from the ``specific_impulse`` I_sp, standard gravity g₀, and the mass ratio of the
    ``initial_mass`` m₀ (fuelled) to the ``final_mass`` m_f (burnt out), Δv = I_sp·g₀·ln(m₀/m_f).
    The logarithm is unforgiving — because m_f includes the structure and payload that cannot be
    shed, doubling the Δv needs the mass ratio *squared*, which is why big Δv budgets force staging.
    Returns the velocity change in m/s.
    """
    _check(specific_impulse, "[time]", "specific_impulse")
    _check(initial_mass, "[mass]", "initial_mass")
    _check(final_mass, "[mass]", "final_mass")
    isp = specific_impulse.to("s").magnitude
    m0 = initial_mass.to("kg").magnitude
    mf = final_mass.to("kg").magnitude
    if isp <= 0:
        raise ValueError("specific_impulse must be positive")
    if m0 <= 0:
        raise ValueError("initial_mass must be positive")
    if mf <= 0:
        raise ValueError("final_mass must be positive")
    if mf >= m0:
        raise ValueError("final_mass must be less than initial_mass (propellant is burnt)")
    return Quantity(magnitude=isp * STANDARD_GRAVITY_M_PER_S2 * log(m0 / mf), unit="m/s")


def rocket_propellant_mass_fraction(*, delta_v: Quantity, specific_impulse: Quantity) -> float:
    """The propellant mass fraction a Δv needs, ζ = 1 − exp(−Δv/(I_sp·g₀)).

    Inverting the rocket equation (:func:`rocket_delta_v`) for the mass budget: the fraction of the
    stage's initial mass that must be propellant to reach a required ``delta_v`` at a
    ``specific_impulse`` I_sp, ζ = m_prop/m₀ = 1 − exp(−Δv/(I_sp·g₀)). It rises steeply toward 1 as
    the demanded Δv grows — a Δv equal to the exhaust velocity already needs 63% propellant —
    leaving ever less mass for structure and payload, the fundamental squeeze of rocketry. Returns
    the propellant mass fraction (0 to 1).
    """
    _check(delta_v, "[length]/[time]", "delta_v")
    _check(specific_impulse, "[time]", "specific_impulse")
    dv = delta_v.to("m/s").magnitude
    isp = specific_impulse.to("s").magnitude
    if dv <= 0:
        raise ValueError("delta_v must be positive")
    if isp <= 0:
        raise ValueError("specific_impulse must be positive")
    return 1.0 - exp(-dv / (isp * STANDARD_GRAVITY_M_PER_S2))


def characteristic_velocity(
    *, chamber_pressure: Quantity, throat_area: Quantity, mass_flow_rate: Quantity
) -> Quantity:
    """The characteristic velocity, c* = p_c·A_t/ṁ.

    A measure of the combustion chamber's performance alone, independent of the nozzle: from the
    ``chamber_pressure`` p_c, the ``throat_area`` A_t, and the ``mass_flow_rate`` ṁ, c* = p_c·A_t/ṁ.
    A higher c* means the propellant makes more chamber pressure per unit of throat flow — better
    combustion. Returns the characteristic velocity in m/s.
    """
    _check(chamber_pressure, "[pressure]", "chamber_pressure")
    _check(throat_area, "[area]", "throat_area")
    _check(mass_flow_rate, "[mass]/[time]", "mass_flow_rate")
    p_c = chamber_pressure.to("Pa").magnitude
    a_t = throat_area.to("m**2").magnitude
    mdot = mass_flow_rate.to("kg/s").magnitude
    if p_c <= 0:
        raise ValueError("chamber_pressure must be positive")
    if a_t <= 0:
        raise ValueError("throat_area must be positive")
    if mdot <= 0:
        raise ValueError("mass_flow_rate must be positive")
    return Quantity(magnitude=p_c * a_t / mdot, unit="m/s")


def thrust_coefficient(
    *, thrust: Quantity, chamber_pressure: Quantity, throat_area: Quantity
) -> float:
    """The nozzle thrust coefficient, C_F = F/(p_c·A_t).

    A measure of how well the nozzle turns chamber pressure into thrust: from the ``thrust`` F, the
    ``chamber_pressure`` p_c, and the ``throat_area`` A_t, C_F = F/(p_c·A_t). It runs from about 1.2
    (poorly expanded) to near 1.9 (a large vacuum bell), and multiplied by c* gives the effective
    exhaust velocity. Returns the thrust coefficient as a plain float.
    """
    _check(thrust, "[force]", "thrust")
    _check(chamber_pressure, "[pressure]", "chamber_pressure")
    _check(throat_area, "[area]", "throat_area")
    f = thrust.to("N").magnitude
    p_c = chamber_pressure.to("Pa").magnitude
    a_t = throat_area.to("m**2").magnitude
    if f <= 0:
        raise ValueError("thrust must be positive")
    if p_c <= 0:
        raise ValueError("chamber_pressure must be positive")
    if a_t <= 0:
        raise ValueError("throat_area must be positive")
    return f / (p_c * a_t)


def thrust_from_coefficient(
    *, thrust_coefficient: float, chamber_pressure: Quantity, throat_area: Quantity
) -> Quantity:
    """The thrust from the coefficient, F = C_F·p_c·A_t.

    The thrust a nozzle produces, from the ``thrust_coefficient`` C_F, the ``chamber_pressure`` p_c,
    and the ``throat_area`` A_t: F = C_F·p_c·A_t. This is how a design sizes the throat for a target
    thrust once the chamber pressure and expected C_F are set. Returns the thrust in N.
    """
    _check(chamber_pressure, "[pressure]", "chamber_pressure")
    _check(throat_area, "[area]", "throat_area")
    p_c = chamber_pressure.to("Pa").magnitude
    a_t = throat_area.to("m**2").magnitude
    if thrust_coefficient <= 0:
        raise ValueError("thrust_coefficient must be positive")
    if p_c <= 0:
        raise ValueError("chamber_pressure must be positive")
    if a_t <= 0:
        raise ValueError("throat_area must be positive")
    return Quantity(magnitude=thrust_coefficient * p_c * a_t, unit="N")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
