"""T1 analytical rotary-hydraulic (positive-displacement pump/motor) checks (closed-form).

A positive-displacement pump or motor moves a fixed volume of oil per shaft revolution — its
*displacement* D — and that single number ties flow, speed, torque, and pressure together. It is the
rotary complement of :mod:`anvilate.analysis.hydraulic_cylinder` (the linear actuator) and is
distinct from the centrifugal machines in :mod:`anvilate.analysis.pump`: a PD unit's flow is set by
its geometry and speed, not by the head it works against.

Run as a pump, it delivers a flow Q = D·N·η_v: the displacement times the shaft speed N, reduced by
the volumetric efficiency η_v because internal leakage (which grows with pressure) never lets all
the swept volume reach the outlet. Run as a motor, the pressure drop Δp across it produces a torque
T = (D·Δp/2π)·η_m — the swept volume converts pressure into work per revolution, and the 2π turns
that per-revolution work into a torque, cut by the mechanical efficiency η_m for friction. Fed a
supply flow, the motor turns at N = Q·η_v/D — the flow it actually admits over its displacement.

Displacement is entered as the volume swept per revolution (e.g. 50 cm³), speed as an angular rate
(rpm or rad/s), and the efficiencies are the caller's, from the unit's curves.

Sources: Esposito, *Fluid Power with Applications* — the flow a pump delivers at a displacement,
speed and volumetric efficiency, and the torque and speed a motor produces from the same three.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity
from ..units.rotation import revolutions_per_second

__all__ = [
    "hydraulic_motor_speed",
    "hydraulic_motor_torque",
    "hydraulic_pump_flow_rate",
]


def hydraulic_pump_flow_rate(
    *,
    displacement: Quantity,
    rotational_speed: Quantity,
    volumetric_efficiency: float = 1.0,
) -> Quantity:
    """The flow a positive-displacement pump delivers, Q = D·N·η_v.

    The output flow from the ``displacement`` D (the volume swept per revolution) turning at a
    ``rotational_speed`` N: Q = D·N·η_v. The ``volumetric_efficiency`` η_v (0 to 1, ~0.9–0.97 for a
    good unit and falling as pressure rises) accounts for the internal leakage that keeps some swept
    volume from reaching the outlet. Unlike a centrifugal pump, the flow barely depends on the
    pressure it works against — a PD pump is a flow source. Returns the delivered flow in m³/s.
    """
    _check(displacement, "[volume]", "displacement")
    _check(rotational_speed, "1/[time]", "rotational_speed")
    _fraction(volumetric_efficiency, "volumetric_efficiency")
    d = displacement.to("m**3").magnitude
    rev_per_second = revolutions_per_second(rotational_speed, name="rotational_speed")
    if d <= 0:
        raise ValueError("displacement must be positive")
    if rev_per_second < 0:
        raise ValueError("rotational_speed must be non-negative")
    return Quantity(magnitude=d * rev_per_second * volumetric_efficiency, unit="m**3/s")


def hydraulic_motor_torque(
    *,
    displacement: Quantity,
    pressure_drop: Quantity,
    mechanical_efficiency: float = 1.0,
) -> Quantity:
    """The torque a positive-displacement motor produces, T = (D·Δp/2π)·η_m.

    The output torque from the ``pressure_drop`` Δp across a motor of ``displacement`` D (volume per
    revolution): T = (D·Δp/2π)·η_m. The swept volume converts pressure into D·Δp of work per
    revolution, and dividing by the 2π radians of a turn gives the torque; the
    ``mechanical_efficiency`` η_m (0 to 1, ~0.9–0.95) trims it for internal friction. The torque
    scales with the pressure the load demands, independent of speed — the defining trait of a
    hydraulic drive. Returns the torque in N·m.
    """
    _check(displacement, "[volume]", "displacement")
    _check(pressure_drop, "[pressure]", "pressure_drop")
    _fraction(mechanical_efficiency, "mechanical_efficiency")
    d = displacement.to("m**3").magnitude
    dp = pressure_drop.to("Pa").magnitude
    if d <= 0:
        raise ValueError("displacement must be positive")
    if dp < 0:
        raise ValueError("pressure_drop must be non-negative")
    return Quantity(magnitude=d * dp / (2.0 * pi) * mechanical_efficiency, unit="N*m")


def hydraulic_motor_speed(
    *,
    flow_rate: Quantity,
    displacement: Quantity,
    volumetric_efficiency: float = 1.0,
) -> Quantity:
    """The speed a supply flow drives a motor at, N = Q·η_v/D.

    How fast a motor of ``displacement`` D turns when fed a supply ``flow_rate`` Q: N = Q·η_v/D, the
    flow it admits over the volume it sweeps per revolution. The ``volumetric_efficiency`` η_v (0 to
    1) accounts for the leakage flow that slips past without turning the shaft, so the real speed is
    below the ideal Q/D — the inverse relation of :func:`hydraulic_pump_flow_rate`. Returns the
    shaft speed in rpm.
    """
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    _check(displacement, "[volume]", "displacement")
    _fraction(volumetric_efficiency, "volumetric_efficiency")
    q = flow_rate.to("m**3/s").magnitude
    d = displacement.to("m**3").magnitude
    if q < 0:
        raise ValueError("flow_rate must be non-negative")
    if d <= 0:
        raise ValueError("displacement must be positive")
    rev_per_second = q * volumetric_efficiency / d
    return Quantity(magnitude=rev_per_second * 60.0, unit="rpm")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
