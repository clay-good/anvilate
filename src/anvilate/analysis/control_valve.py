"""T1 analytical control-valve sizing checks (turbulent liquid, closed-form).

A control valve throttles flow by presenting a variable restriction, and one number rates that
restriction: the flow coefficient Cv, the flow of water (in US gpm) the wide-open valve passes at a
1 psi drop. For turbulent liquid flow the valve equation ties flow, pressure drop, and Cv together,
Q = Cv·√(ΔP/SG), from the specific gravity SG of the fluid — the sizing companion to the pipe
friction of :mod:`anvilate.analysis.pipe_flow` (that module drops pressure along the run, this one
across the trim).

Rearranged, the same equation answers the three sizing questions: the flow a valve of a given Cv
passes at a drop, the Cv a duty *requires* (Cv = Q/√(ΔP/SG), the number you select a valve against),
and the drop a valve imposes at a flow. A separate, equally important number is the valve authority
N = ΔP_valve/(ΔP_valve + ΔP_system): the share of the loop's pressure drop the valve takes open.
Below about 0.25 the valve barely moves the flow over most of its travel and control is sloppy, so a
well-controlled loop keeps N above ~0.5. Flows, pressures, and Cv follow the industry's US units
(gpm, psi) through dimension-checked :class:`~anvilate.units.Quantity` values; Cv, SG, and authority
are plain floats.

Sources: Crane TP-410, *Flow of Fluids Through Valves, Fittings and Pipe* — the flow a valve
passes at a flow coefficient and pressure drop, the coefficient a duty requires, and the valve
authority that decides how linear the installed characteristic is.
"""

from __future__ import annotations

from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_VALVE_DATASHEET_SOURCE = "the valve manufacturer's rated flow coefficient"
_PROCESS_SOURCE = "the process datasheet (flow, pressure drop, and fluid specific gravity)"
_SYSTEM_SOURCE = "the piping system's hydraulic calculation of pressure drops"


class _ControlValveInputError(RefusalError, ValueError):
    """A control-valve sizing input that cannot be used without correction."""


def _control_valve_refusal(message: str, *, subject: str, source: str) -> _ControlValveInputError:
    return _ControlValveInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _control_valve_input_source(name: str) -> str:
    if name == "flow_coefficient":
        return _VALVE_DATASHEET_SOURCE
    if name in {"system_pressure_drop", "valve_pressure_drop"}:
        return _SYSTEM_SOURCE
    return _PROCESS_SOURCE


__all__ = [
    "valve_flow_rate",
    "required_flow_coefficient",
    "valve_authority",
]


def valve_flow_rate(
    *, flow_coefficient: float, pressure_drop: Quantity, specific_gravity: float = 1.0
) -> Quantity:
    """The turbulent liquid flow through a valve, Q = Cv·√(ΔP/SG).

    The flow a control valve of coefficient ``flow_coefficient`` Cv passes at a ``pressure_drop`` ΔP
    across it, for a liquid of ``specific_gravity`` SG (relative to water): Q = Cv·√(ΔP/SG). This
    rates an already-selected valve — how much it flows at the available drop. A denser fluid (a
    higher SG) flows less for the same Cv and drop. Cv is positive, SG positive (1.0 for water).
    Returns the flow rate in US gallons per minute.
    """
    require_finite(flow_coefficient, name="flow_coefficient")
    _check(pressure_drop, "[pressure]", "pressure_drop")
    if flow_coefficient <= 0:
        raise _control_valve_refusal(
            "flow_coefficient must be positive",
            subject="flow_coefficient",
            source=_VALVE_DATASHEET_SOURCE,
        )
    require_finite(specific_gravity, name="specific_gravity")
    if specific_gravity <= 0:
        raise _control_valve_refusal(
            "specific_gravity must be positive", subject="specific_gravity", source=_PROCESS_SOURCE
        )
    delta_p_psi = pressure_drop.to("psi").magnitude
    if delta_p_psi <= 0:
        raise _control_valve_refusal(
            "pressure_drop must be positive", subject="pressure_drop", source=_PROCESS_SOURCE
        )
    q_gpm = flow_coefficient * sqrt(delta_p_psi / specific_gravity)
    return Quantity(magnitude=q_gpm, unit="gallon/minute")


def required_flow_coefficient(
    *, flow_rate: Quantity, pressure_drop: Quantity, specific_gravity: float = 1.0
) -> float:
    """The flow coefficient a duty requires, Cv = Q/√(ΔP/SG).

    The sizing inverse of :func:`valve_flow_rate`, and the number a valve is selected against: to
    pass a ``flow_rate`` Q at an allotted ``pressure_drop`` ΔP with a liquid of ``specific_gravity``
    SG, the valve must have at least Cv = Q/√(ΔP/SG). Pick a valve whose rated Cv exceeds this (with
    margin, so it does not run near wide-open); a valve short of it cannot pass the flow at the
    available drop. Allotting more pressure drop to the valve lowers the required Cv. Returns the
    required flow coefficient as a plain float (US gpm/psi^0.5 basis).
    """
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    _check(pressure_drop, "[pressure]", "pressure_drop")
    require_finite(specific_gravity, name="specific_gravity")
    if specific_gravity <= 0:
        raise _control_valve_refusal(
            "specific_gravity must be positive", subject="specific_gravity", source=_PROCESS_SOURCE
        )
    q_gpm = flow_rate.to("gallon/minute").magnitude
    delta_p_psi = pressure_drop.to("psi").magnitude
    if q_gpm <= 0:
        raise _control_valve_refusal(
            "flow_rate must be positive", subject="flow_rate", source=_PROCESS_SOURCE
        )
    if delta_p_psi <= 0:
        raise _control_valve_refusal(
            "pressure_drop must be positive", subject="pressure_drop", source=_PROCESS_SOURCE
        )
    return q_gpm / sqrt(delta_p_psi / specific_gravity)


def valve_authority(*, valve_pressure_drop: Quantity, system_pressure_drop: Quantity) -> float:
    """The control-valve authority, N = ΔP_valve/(ΔP_valve + ΔP_system).

    How much of the loop's pressure drop the valve commands when fully open: N =
    ΔP_valve/(ΔP_valve + ΔP_system), from the wide-open ``valve_pressure_drop`` ΔP_valve and the
    rest-of-loop ``system_pressure_drop`` ΔP_system (pipe, fittings, exchangers) at that flow. It
    sets how linear and responsive the installed characteristic is: a low authority (N ≲ 0.25) means
    the system, not the valve, governs the flow over most of the travel, so the valve barely acts
    until nearly shut. Good control wants N above ~0.5, bought by allotting the valve a larger share
    of the drop (a smaller valve). Both drops must be non-negative with a positive total. Returns
    the dimensionless authority (0 to 1).
    """
    _check(valve_pressure_drop, "[pressure]", "valve_pressure_drop")
    _check(system_pressure_drop, "[pressure]", "system_pressure_drop")
    dp_valve = valve_pressure_drop.to("psi").magnitude
    dp_system = system_pressure_drop.to("psi").magnitude
    if dp_valve < 0:
        raise _control_valve_refusal(
            "valve_pressure_drop must be non-negative",
            subject="valve_pressure_drop",
            source=_SYSTEM_SOURCE,
        )
    if dp_system < 0:
        raise _control_valve_refusal(
            "system_pressure_drop must be non-negative",
            subject="system_pressure_drop",
            source=_SYSTEM_SOURCE,
        )
    total = dp_valve + dp_system
    if total <= 0:
        raise _control_valve_refusal(
            "the total pressure drop must be positive",
            subject="valve_pressure_drop and system_pressure_drop",
            source=_SYSTEM_SOURCE,
        )
    return dp_valve / total


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _control_valve_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_control_valve_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _control_valve_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_control_valve_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
