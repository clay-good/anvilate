"""T1 analytical pump sizing checks (hydraulic power and specific speed, closed-form).

Once a pipe run's total head is known (see :mod:`~anvilate.analysis.pipe_flow`), sizing the
pump that drives it is direct. The useful power added to the fluid is the hydraulic power
P = ρ·g·Q·H — the weight of fluid lifted per second times the head — and the motor must supply
more than that, P/η, because no pump is perfectly efficient. Divide the two and you have the
shaft (brake) power the driver has to deliver.

Which *kind* of pump suits the duty is set by the specific speed, a dimensionless group that
collapses speed, flow and head into one number: N_s = ω·√Q / (g·H)^(3/4). Low values (well
below 1) point to high-head, low-flow radial (centrifugal) impellers; high values to low-head,
high-flow axial ones.

Run the *same* pump at a different speed and the affinity laws predict the new operating point:
flow scales with the speed ratio, head with its square, and power with its cube. That cube is
why trimming speed with a variable-frequency drive saves so much energy — a 20% speed cut nearly
halves the power. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "affinity_head",
    "affinity_flow_rate",
    "affinity_power",
    "pump_hydraulic_power",
    "pump_shaft_power",
    "pump_specific_speed",
]

_GRAVITY = 9.80665  # m/s^2, standard gravity


def pump_hydraulic_power(
    *,
    flow_rate: Quantity,
    head: Quantity,
    density: Quantity,
) -> Quantity:
    """The hydraulic (fluid) power a pump adds, P = ρ·g·Q·H.

    The rate of useful work delivered to the fluid: lifting a volumetric ``flow_rate`` Q of a
    fluid of ``density`` ρ through a total ``head`` H costs P = ρ·g·Q·H. This is the power that
    actually goes into the flow; the driver must supply more (see :func:`pump_shaft_power`). H is
    the total dynamic head — static lift plus the friction and fitting losses from
    :mod:`~anvilate.analysis.pipe_flow`. Returns the hydraulic power in watts.
    """
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(head, "[length]", "head")
    _check(density, "[mass]/[length]**3", "density")
    q = flow_rate.to("m**3/s").magnitude
    h = head.to("m").magnitude
    rho = density.to("kg/m**3").magnitude
    if q <= 0 or h <= 0 or rho <= 0:
        raise ValueError("flow_rate, head, and density must be positive")
    return Quantity(magnitude=rho * _GRAVITY * q * h, unit="W")


def pump_shaft_power(*, hydraulic_power: Quantity, efficiency: float) -> Quantity:
    """The shaft (brake) power a pump driver must supply, P_shaft = P_hyd / η.

    A pump never converts all of its shaft power into fluid power, so the motor must deliver more
    than the hydraulic power: P_shaft = P_hyd / η. ``hydraulic_power`` P_hyd comes from
    :func:`pump_hydraulic_power` and ``efficiency`` η is the pump's overall efficiency (0 to 1,
    typically 0.6–0.85 for a centrifugal pump at its best point). Returns the shaft power in watts
    — size the motor above this.
    """
    _check(hydraulic_power, "[power]", "hydraulic_power")
    p = hydraulic_power.to("W").magnitude
    if p <= 0:
        raise ValueError("hydraulic_power must be positive")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError(f"efficiency must be in (0, 1]; got {efficiency}")
    return Quantity(magnitude=p / efficiency, unit="W")


def pump_specific_speed(
    *,
    rotational_speed: Quantity,
    flow_rate: Quantity,
    head: Quantity,
) -> float:
    """The dimensionless specific speed N_s = ω·√Q / (g·H)^(3/4) of a pump duty.

    The similarity group that classifies what impeller shape a duty wants, independent of size:
    N_s = ω·√Q / (g·H)^(3/4) from the ``rotational_speed`` ω, the ``flow_rate`` Q, and the
    ``head`` H. Small N_s (well under 1) means high head at low flow — a radial centrifugal
    impeller; large N_s means high flow at low head — a mixed-flow or axial one. Rotational speed
    is taken as an angular rate (e.g. rpm or rad/s, converted internally to rad/s). Returns the
    dimensionless specific speed.
    """
    _check(rotational_speed, "1/[time]", "rotational_speed")
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(head, "[length]", "head")
    omega = rotational_speed.to("rad/s").magnitude
    q = flow_rate.to("m**3/s").magnitude
    h = head.to("m").magnitude
    if omega <= 0 or q <= 0 or h <= 0:
        raise ValueError("rotational_speed, flow_rate, and head must be positive")
    return omega * sqrt(q) / (_GRAVITY * h) ** 0.75


def affinity_flow_rate(*, flow_rate: Quantity, speed_ratio: float) -> Quantity:
    """The flow of the same pump at a new speed, Q₂ = Q₁·(N₂/N₁) (first affinity law).

    Flow scales in direct proportion to shaft speed: ``flow_rate`` Q₁ at the reference speed
    becomes Q₁·``speed_ratio`` at the new one, where ``speed_ratio`` = N₂/N₁. Returns the scaled
    flow rate in m³/s.
    """
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    q = flow_rate.to("m**3/s").magnitude
    if speed_ratio <= 0:
        raise ValueError(f"speed_ratio must be positive; got {speed_ratio}")
    if q <= 0:
        raise ValueError("flow_rate must be positive")
    return Quantity(magnitude=q * speed_ratio, unit="m**3/s")


def affinity_head(*, head: Quantity, speed_ratio: float) -> Quantity:
    """The head of the same pump at a new speed, H₂ = H₁·(N₂/N₁)² (second affinity law).

    Head scales with the *square* of the speed ratio: ``head`` H₁ becomes H₁·``speed_ratio``²,
    where ``speed_ratio`` = N₂/N₁. Returns the scaled head in meters.
    """
    _check(head, "[length]", "head")
    h = head.to("m").magnitude
    if speed_ratio <= 0:
        raise ValueError(f"speed_ratio must be positive; got {speed_ratio}")
    if h <= 0:
        raise ValueError("head must be positive")
    return Quantity(magnitude=h * speed_ratio**2, unit="m")


def affinity_power(*, power: Quantity, speed_ratio: float) -> Quantity:
    """The power of the same pump at a new speed, P₂ = P₁·(N₂/N₁)³ (third affinity law).

    Power scales with the *cube* of the speed ratio: ``power`` P₁ becomes P₁·``speed_ratio``³,
    where ``speed_ratio`` = N₂/N₁. This cube is the whole case for variable-speed drives — a
    modest speed cut is a large power saving. Returns the scaled power in watts.
    """
    _check(power, "[power]", "power")
    p = power.to("W").magnitude
    if speed_ratio <= 0:
        raise ValueError(f"speed_ratio must be positive; got {speed_ratio}")
    if p <= 0:
        raise ValueError("power must be positive")
    return Quantity(magnitude=p * speed_ratio**3, unit="W")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
