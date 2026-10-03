"""T1 analytical DC (permanent-magnet) motor constants (closed-form).

A brushed or brushless-DC motor is governed by two constants and a winding resistance. Spinning, it
acts as a generator and pushes back a voltage proportional to speed — the back-EMF — and it produces
a torque proportional to the current it draws. In SI units the two constants are numerically equal,
which is why one datasheet number often serves for both. This module gives those constitutive
relations, the electrical companion to the servo *motion* sizing of
:mod:`anvilate.analysis.servo` and to the induction-machine feeder checks of
:mod:`anvilate.analysis.electrical`.

The back-EMF is E = K_e·ω, from the ``back_emf_constant`` K_e (V·s/rad) and the mechanical
``angular_speed`` ω. The torque is T = K_t·I, from the ``torque_constant`` K_t (N·m/A) and the
armature ``current`` I — and K_e and K_t share a dimension ([energy]/[current]) and, in SI, a value.
The terminal voltage a driver must supply is V = E + I·R_a: the back-EMF plus the ohmic drop across
the ``armature_resistance``, so at stall (ω = 0) all of it drives current through R_a, while at
speed the back-EMF takes most of it. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Fitzgerald, Kingsley & Umans, *Electric Machinery* — the back EMF of a DC machine at
speed, the torque its armature current develops, and the terminal voltage those and the winding
resistance require.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.rotation import angular_speed_rad_per_s

_MOTOR_DATASHEET_SOURCE = "the motor datasheet (torque and back-EMF constants, armature resistance)"
_OPERATING_POINT_SOURCE = "the duty cycle or measured motor current and speed"


class _DcMotorInputError(RefusalError, ValueError):
    """A DC-motor input that cannot be used without correction."""


def _dc_motor_refusal(message: str, *, subject: str, source: str) -> _DcMotorInputError:
    return _DcMotorInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _dc_motor_input_source(name: str) -> str:
    if name in {"armature_resistance", "back_emf_constant", "torque_constant"}:
        return _MOTOR_DATASHEET_SOURCE
    return _OPERATING_POINT_SOURCE


__all__ = [
    "dc_motor_back_emf",
    "dc_motor_torque",
    "dc_motor_terminal_voltage",
]


def dc_motor_back_emf(*, back_emf_constant: Quantity, angular_speed: Quantity) -> Quantity:
    """A DC motor's back-EMF, E = K_e·ω.

    The voltage a spinning DC motor generates against its supply, from the ``back_emf_constant`` K_e
    (V·s/rad, the motor's voltage constant) and the mechanical ``angular_speed`` ω: E = K_e·ω. It
    rises with speed, and at the no-load speed it nearly equals the supply voltage (only a trickle
    of current flows). Pass ω as a genuine angular rate (rad/s). Returns the back-EMF in volts.
    """
    _check(back_emf_constant, "[energy]/[current]", "back_emf_constant")
    _check(angular_speed, "1/[time]", "angular_speed")
    ke = back_emf_constant.to("V*s/rad").magnitude
    omega = angular_speed_rad_per_s(angular_speed, name="angular_speed")
    if ke < 0:
        raise _dc_motor_refusal(
            "back_emf_constant must be non-negative",
            subject="back_emf_constant",
            source=_MOTOR_DATASHEET_SOURCE,
        )
    if omega < 0:
        raise _dc_motor_refusal(
            "angular_speed must be non-negative",
            subject="angular_speed",
            source=_OPERATING_POINT_SOURCE,
        )
    return Quantity(magnitude=ke * omega, unit="V")


def dc_motor_torque(*, torque_constant: Quantity, armature_current: Quantity) -> Quantity:
    """A DC motor's torque, T = K_t·I.

    The shaft torque a DC motor develops, from the ``torque_constant`` K_t (N·m/A, the motor's
    torque constant) and the ``armature_current`` I it draws: T = K_t·I. Torque is set by current
    alone (not speed), which is why a DC motor's torque is limited by winding heating and why
    stall — where current is highest — gives the greatest torque. In SI K_t equals the back-EMF
    constant K_e. Returns the torque in N·m.
    """
    _check(torque_constant, "[energy]/[current]", "torque_constant")
    _check(armature_current, "[current]", "armature_current")
    kt = torque_constant.to("N*m/A").magnitude
    i = armature_current.to("A").magnitude
    if kt < 0:
        raise _dc_motor_refusal(
            "torque_constant must be non-negative",
            subject="torque_constant",
            source=_MOTOR_DATASHEET_SOURCE,
        )
    if i < 0:
        raise _dc_motor_refusal(
            "armature_current must be non-negative",
            subject="armature_current",
            source=_OPERATING_POINT_SOURCE,
        )
    return Quantity(magnitude=kt * i, unit="N*m")


def dc_motor_terminal_voltage(
    *,
    back_emf: Quantity,
    armature_current: Quantity,
    armature_resistance: Quantity,
) -> Quantity:
    """A DC motor's terminal voltage, V = E + I·R_a.

    The supply voltage a DC motor needs at its terminals: the ``back_emf`` E plus the ohmic drop the
    ``armature_current`` I makes across the ``armature_resistance`` R_a, V = E + I·R_a. At stall
    (E = 0) the whole terminal voltage drives current through R_a — the reason stall current is high
    and must be limited — while at speed the back-EMF carries most of it and the current falls.
    Returns the terminal voltage in volts.
    """
    _check(back_emf, "[electric_potential]", "back_emf")
    _check(armature_current, "[current]", "armature_current")
    _check(armature_resistance, "[electric_potential]/[current]", "armature_resistance")
    e = back_emf.to("V").magnitude
    i = armature_current.to("A").magnitude
    r = armature_resistance.to("ohm").magnitude
    if e < 0:
        raise _dc_motor_refusal(
            "back_emf must be non-negative", subject="back_emf", source=_OPERATING_POINT_SOURCE
        )
    if i < 0:
        raise _dc_motor_refusal(
            "armature_current must be non-negative",
            subject="armature_current",
            source=_OPERATING_POINT_SOURCE,
        )
    if r < 0:
        raise _dc_motor_refusal(
            "armature_resistance must be non-negative",
            subject="armature_resistance",
            source=_MOTOR_DATASHEET_SOURCE,
        )
    return Quantity(magnitude=e + i * r, unit="V")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _dc_motor_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_dc_motor_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _dc_motor_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_dc_motor_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
