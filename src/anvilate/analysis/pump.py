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

Sources: Karassik, *Pump Handbook*, and the Hydraulic Institute standards for the
pump-power, efficiency and affinity relations.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.rotation import angular_speed_rad_per_s

__all__ = [
    "affinity_head",
    "affinity_flow_rate",
    "affinity_power",
    "npsh_available",
    "npsh_margin",
    "pump_hydraulic_power",
    "pump_shaft_power",
    "pump_specific_speed",
    "pump_temperature_rise",
    "pump_suction_specific_speed",
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


def pump_temperature_rise(
    *,
    head: Quantity,
    efficiency: float,
    specific_heat: Quantity,
) -> Quantity:
    """The temperature rise a pump imparts to its own liquid, ΔT = g·H·(1 − η)/(c_p·η).

    Everything the pump does not turn into head becomes heat, and that heat has nowhere to go but
    into the liquid passing through: ΔT = g·``head``·(1 − ``efficiency``)/(``specific_heat``·η).
    The mass flow cancels out — more flow carries away more heat but also absorbs more of it — so
    the rise depends only on head and efficiency. That is exactly why it matters at low flow: as a
    centrifugal pump is throttled toward shut-off its efficiency collapses while its head rises, so
    ΔT climbs steeply just as there is less liquid to carry the heat out. This is the API 610
    minimum-continuous-flow screen — heat the liquid enough and it flashes at the impeller eye,
    which shows up as a loss of the NPSH margin :func:`npsh_margin` checks. At a normal duty
    (50 m, 75% efficient, water) the rise is a negligible 0.04 K; at 200 m and 40% it is 0.7 K, and
    at shut-off it runs away. Returns the temperature rise in K.
    """
    _check(head, "[length]", "head")
    _check(specific_heat, "[energy]/([mass]*[temperature])", "specific_heat")
    h = head.to("m").magnitude
    cp = specific_heat.to("J/(kg*K)").magnitude
    if h < 0:
        raise ValueError("head must be non-negative")
    if cp <= 0:
        raise ValueError("specific_heat must be positive")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError(f"efficiency must be in (0, 1]; got {efficiency}")
    return Quantity(magnitude=_GRAVITY * h * (1.0 - efficiency) / (cp * efficiency), unit="K")


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
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    q = flow_rate.to("m**3/s").magnitude
    h = head.to("m").magnitude
    if omega <= 0 or q <= 0 or h <= 0:
        raise ValueError("rotational_speed, flow_rate, and head must be positive")
    return omega * sqrt(q) / (_GRAVITY * h) ** 0.75


def pump_suction_specific_speed(
    *,
    rotational_speed: Quantity,
    flow_rate: Quantity,
    npsh_required: Quantity,
) -> float:
    """The dimensionless suction specific speed N_ss = ω·√Q / (g·NPSHr)^(3/4) of a pump inlet.

    The cousin of :func:`pump_specific_speed` that governs *cavitation*, not impeller shape: it
    replaces the total head with the required NPSH, N_ss = ω·√Q / (g·NPSHr)^(3/4) from the
    ``rotational_speed`` ω, ``flow_rate`` Q, and ``npsh_required`` NPSHr from the pump curve. It
    measures how hard the inlet is worked — a high N_ss means the pump makes head from very little
    suction margin, which buys efficiency but courts suction recirculation and instability at
    part-load; the Hydraulic Institute's reliability guidance caps it (~3.5 in this SI dimensionless
    form, ~9000-11000 in US rpm/gpm/ft units). Rotational speed is an angular rate (rpm or rad/s).
    Returns the dimensionless suction specific speed.
    """
    _check(rotational_speed, "1/[time]", "rotational_speed")
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(npsh_required, "[length]", "npsh_required")
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    q = flow_rate.to("m**3/s").magnitude
    npshr = npsh_required.to("m").magnitude
    if omega <= 0 or q <= 0 or npshr <= 0:
        raise ValueError("rotational_speed, flow_rate, and npsh_required must be positive")
    return omega * sqrt(q) / (_GRAVITY * npshr) ** 0.75


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


def npsh_available(
    *,
    atmospheric_pressure: Quantity,
    vapor_pressure: Quantity,
    density: Quantity,
    static_suction_head: Quantity,
    suction_friction_loss: Quantity,
) -> Quantity:
    """The net positive suction head available at a pump inlet, NPSH_a.

    Whether a pump cavitates depends on how much the pressure at its inlet exceeds the liquid's
    vapor pressure, expressed as a head: NPSH_a = (p_atm − p_v)/(ρ·g) + h_s − h_f.
    ``atmospheric_pressure`` p_atm acts on the source surface, ``vapor_pressure`` p_v is the
    liquid's vapor pressure at the
    pumping temperature, ``density`` ρ the liquid density, ``static_suction_head`` h_s the height of
    the source surface above the pump centerline (positive for a flooded suction, negative when the
    pump must lift the liquid from below), and ``suction_friction_loss`` h_f the head lost in the
    suction line. Compare against the pump's required NPSH with :func:`npsh_margin`. Returns NPSH_a
    in meters.
    """
    _check(atmospheric_pressure, "[pressure]", "atmospheric_pressure")
    _check(vapor_pressure, "[pressure]", "vapor_pressure")
    _check(density, "[mass]/[length]**3", "density")
    _check(static_suction_head, "[length]", "static_suction_head")
    _check(suction_friction_loss, "[length]", "suction_friction_loss")
    p_atm = atmospheric_pressure.to("Pa").magnitude
    p_v = vapor_pressure.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    h_s = static_suction_head.to("m").magnitude
    h_f = suction_friction_loss.to("m").magnitude
    if p_atm <= 0 or rho <= 0:
        raise ValueError("atmospheric_pressure and density must be positive")
    if p_v < 0 or h_f < 0:
        raise ValueError("vapor_pressure and suction_friction_loss must be non-negative")
    npsh = (p_atm - p_v) / (rho * _GRAVITY) + h_s - h_f
    return Quantity(magnitude=npsh, unit="m")


def npsh_margin(*, npsh_available: Quantity, npsh_required: Quantity) -> Quantity:
    """The cavitation margin, NPSH_available − NPSH_required.

    A pump runs free of cavitation only while the suction head it *has* stays above the head it
    *needs*: the margin NPSH_a − NPSH_r. ``npsh_available`` comes from :func:`npsh_available` and
    ``npsh_required`` from the pump manufacturer's curve. A positive margin (a cushion of ~0.5–1 m
    is usual) means no cavitation; a negative one means the pump cavitates. Returns the margin in
    meters.
    """
    _check(npsh_available, "[length]", "npsh_available")
    _check(npsh_required, "[length]", "npsh_required")
    a = npsh_available.to("m").magnitude
    r = npsh_required.to("m").magnitude
    if r < 0:
        raise ValueError("npsh_required must be non-negative")
    return Quantity(magnitude=a - r, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
