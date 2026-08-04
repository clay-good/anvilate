"""T1 analytical incompressible pipe-flow checks (Darcy-Weisbach head loss, closed-form).

Sizing a pump or a pipe run comes down to one question — how much pressure does it cost to
push the fluid through — and the Darcy-Weisbach equation answers it: the friction head lost
over a length L of pipe is h_f = f·(L/D)·V²/(2g). The friction factor f is where the physics
lives. In laminar flow (Reynolds number below ~2300) it is exactly 64/Re; in turbulent flow
it depends on both Re and the pipe's relative roughness ε/D through the implicit Colebrook
equation, which :func:`darcy_friction_factor` evaluates with the explicit Swamee-Jain fit
(within ~1% of Colebrook over the whole turbulent range).

Fittings, valves, bends and entrances add *minor* losses h_m = K·V²/(2g) on top, and the
total head loss converts to a pressure drop through Δp = ρ·g·h. Together these size the
run: :func:`reynolds_number` → :func:`darcy_friction_factor` → :func:`darcy_weisbach_head_loss`
(plus :func:`minor_loss_head`) → :func:`pipe_pressure_drop`.

For water distribution the empirical Hazen-Williams equation is the common shortcut — it needs
only a roughness coefficient C (no Reynolds number or friction factor), giving the head loss
directly as h_f = 10.67·L·Q^1.852/(C^1.852·D^4.87). Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import log10

from ..units import Quantity

__all__ = [
    "cavitation_number",
    "darcy_friction_factor",
    "darcy_weisbach_head_loss",
    "hazen_williams_flow_capacity",
    "hazen_williams_head_loss",
    "hydraulic_diameter",
    "joukowsky_surge_pressure",
    "minor_loss_head",
    "pipe_pressure_drop",
    "reynolds_number",
    "surge_wave_period",
]

# Hazen-Williams SI constant and exponents: h_f = 10.67*L*Q^1.852 / (C^1.852 * D^4.87),
# with Q in m^3/s, D and L in m. The empirical form for water near 15-20 C.
_HW_CONSTANT = 10.67
_HW_FLOW_EXPONENT = 1.852
_HW_DIAMETER_EXPONENT = 4.87

_GRAVITY = 9.80665  # m/s^2, standard gravity
_LAMINAR_LIMIT = 2300.0  # Reynolds number below which flow is laminar


def reynolds_number(
    *,
    velocity: Quantity,
    diameter: Quantity,
    kinematic_viscosity: Quantity,
) -> float:
    """The pipe-flow Reynolds number Re = V·D/ν.

    The dimensionless ratio of inertial to viscous forces that decides whether pipe flow is
    laminar or turbulent: Re = V·D/ν from the mean ``velocity`` V, the inside ``diameter`` D, and
    the fluid's ``kinematic_viscosity`` ν (its dynamic viscosity over its density). Below about
    2300 the flow is laminar; above about 4000 it is fully turbulent. Feed the result to
    :func:`darcy_friction_factor`. Returns the dimensionless Reynolds number.
    """
    _check(velocity, "[length]/[time]", "velocity")
    _check(diameter, "[length]", "diameter")
    _check(kinematic_viscosity, "[length]**2/[time]", "kinematic_viscosity")
    v = velocity.to("m/s").magnitude
    d = diameter.to("m").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if v <= 0 or d <= 0 or nu <= 0:
        raise ValueError("velocity, diameter, and kinematic_viscosity must be positive")
    return v * d / nu


def darcy_friction_factor(*, reynolds: float, relative_roughness: float = 0.0) -> float:
    """The Darcy friction factor f for pipe flow, from the Reynolds number and relative roughness.

    The dimensionless factor in the Darcy-Weisbach head-loss equation. In laminar flow
    (``reynolds`` Re ≤ 2300) it is exactly 64/Re and roughness does not matter. In turbulent flow
    it follows the implicit Colebrook equation, evaluated here with the explicit Swamee-Jain
    approximation f = 0.25 / [log₁₀(ε/D/3.7 + 5.74/Re^0.9)]², accurate to about 1%.
    ``relative_roughness`` is ε/D, the pipe wall roughness over its inside diameter (0 for a
    hydraulically smooth pipe). Returns the dimensionless friction factor.
    """
    if reynolds <= 0:
        raise ValueError(f"reynolds must be positive; got {reynolds}")
    if relative_roughness < 0:
        raise ValueError(f"relative_roughness must be non-negative; got {relative_roughness}")
    if reynolds <= _LAMINAR_LIMIT:
        return 64.0 / reynolds
    denom = log10(relative_roughness / 3.7 + 5.74 / reynolds**0.9)
    return 0.25 / denom**2


def darcy_weisbach_head_loss(
    *,
    friction_factor: float,
    length: Quantity,
    diameter: Quantity,
    velocity: Quantity,
) -> Quantity:
    """The Darcy-Weisbach friction head loss over a length of pipe, h_f = f·(L/D)·V²/(2g).

    The head (height of fluid) lost to wall friction as the fluid travels a ``length`` L of pipe
    of inside ``diameter`` D at mean ``velocity`` V, with ``friction_factor`` f from
    :func:`darcy_friction_factor`. Add any :func:`minor_loss_head` from fittings, then convert the
    total to a pressure with :func:`pipe_pressure_drop`. Returns the head loss in meters of fluid.
    """
    _check(length, "[length]", "length")
    _check(diameter, "[length]", "diameter")
    _check(velocity, "[length]/[time]", "velocity")
    lo = length.to("m").magnitude
    d = diameter.to("m").magnitude
    v = velocity.to("m/s").magnitude
    if friction_factor <= 0:
        raise ValueError("friction_factor must be positive")
    if lo <= 0 or d <= 0 or v <= 0:
        raise ValueError("length, diameter, and velocity must be positive")
    h_f = friction_factor * (lo / d) * v**2 / (2.0 * _GRAVITY)
    return Quantity(magnitude=h_f, unit="m")


def minor_loss_head(*, loss_coefficient: float, velocity: Quantity) -> Quantity:
    """The minor (local) head loss of a fitting, valve, or bend, h_m = K·V²/(2g).

    The head lost at a discrete disturbance — an elbow, a valve, an entrance or exit — expressed
    as a multiple of the velocity head: h_m = K·V²/(2g). ``loss_coefficient`` K is the fitting's
    tabulated coefficient (e.g. ~0.5 for a sharp entrance, ~10 for a globe valve) and
    ``velocity`` V the mean pipe velocity. Sum these with the :func:`darcy_weisbach_head_loss`
    friction head for the total. Returns the head loss in meters of fluid.
    """
    _check(velocity, "[length]/[time]", "velocity")
    v = velocity.to("m/s").magnitude
    if loss_coefficient < 0:
        raise ValueError("loss_coefficient must be non-negative")
    if v <= 0:
        raise ValueError("velocity must be positive")
    return Quantity(magnitude=loss_coefficient * v**2 / (2.0 * _GRAVITY), unit="m")


def pipe_pressure_drop(*, head_loss: Quantity, density: Quantity) -> Quantity:
    """The pressure drop equivalent to a head loss, Δp = ρ·g·h.

    Converts a head loss (in meters of fluid, from :func:`darcy_weisbach_head_loss` plus any
    :func:`minor_loss_head`) into the pressure the pump must supply to overcome it:
    Δp = ρ·g·h. ``head_loss`` h is the total head and ``density`` ρ the fluid density. Returns
    the pressure drop in kPa.
    """
    _check(head_loss, "[length]", "head_loss")
    _check(density, "[mass]/[length]**3", "density")
    h = head_loss.to("m").magnitude
    rho = density.to("kg/m**3").magnitude
    if h < 0 or rho <= 0:
        raise ValueError("head_loss must be non-negative and density positive")
    return Quantity(magnitude=rho * _GRAVITY * h / 1000.0, unit="kPa")


def hazen_williams_head_loss(
    *,
    flow_rate: Quantity,
    pipe_diameter: Quantity,
    length: Quantity,
    roughness_coefficient: float,
) -> Quantity:
    """The Hazen-Williams friction head loss for water flow in a pipe.

    The empirical head loss water utilities use, needing only a roughness coefficient rather than a
    Reynolds number and friction factor: h_f = 10.67·L·Q^1.852 / (C^1.852·D^4.87) (SI form).
    ``flow_rate`` Q, ``pipe_diameter`` D, and ``length`` L set the geometry, and
    ``roughness_coefficient`` C is the Hazen-Williams C (~130–150 for new cast iron or PVC, ~100
    for older or tuberculated pipe — a higher C is smoother). Valid for water near ambient
    temperature; for other fluids or regimes use :func:`darcy_weisbach_head_loss`. Returns the head
    loss in meters.
    """
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(pipe_diameter, "[length]", "pipe_diameter")
    _check(length, "[length]", "length")
    q = flow_rate.to("m**3/s").magnitude
    d = pipe_diameter.to("m").magnitude
    lo = length.to("m").magnitude
    if q <= 0 or d <= 0 or lo <= 0:
        raise ValueError("flow_rate, pipe_diameter, and length must be positive")
    if roughness_coefficient <= 0:
        raise ValueError("roughness_coefficient must be positive")
    h_f = (
        _HW_CONSTANT
        * lo
        * q**_HW_FLOW_EXPONENT
        / (roughness_coefficient**_HW_FLOW_EXPONENT * d**_HW_DIAMETER_EXPONENT)
    )
    return Quantity(magnitude=h_f, unit="m")


def hazen_williams_flow_capacity(
    *,
    head_loss: Quantity,
    pipe_diameter: Quantity,
    length: Quantity,
    roughness_coefficient: float,
) -> Quantity:
    """The water flow a pipe carries for a given Hazen-Williams head loss (capacity inverse).

    The inverse of :func:`hazen_williams_head_loss`, Q = [h_f·C^1.852·D^4.87 / (10.67·L)]^(1/1.852)
    — the discharge a main delivers when a head or pressure budget ``head_loss`` h_f is spent over
    its ``length`` L. ``pipe_diameter`` D and ``roughness_coefficient`` C are as in the forward
    relation. Returns the flow rate in m³/s.
    """
    _check(head_loss, "[length]", "head_loss")
    _check(pipe_diameter, "[length]", "pipe_diameter")
    _check(length, "[length]", "length")
    h_f = head_loss.to("m").magnitude
    d = pipe_diameter.to("m").magnitude
    lo = length.to("m").magnitude
    if h_f <= 0 or d <= 0 or lo <= 0:
        raise ValueError("head_loss, pipe_diameter, and length must be positive")
    if roughness_coefficient <= 0:
        raise ValueError("roughness_coefficient must be positive")
    numerator = h_f * roughness_coefficient**_HW_FLOW_EXPONENT * d**_HW_DIAMETER_EXPONENT
    q = (numerator / (_HW_CONSTANT * lo)) ** (1.0 / _HW_FLOW_EXPONENT)
    return Quantity(magnitude=q, unit="m**3/s")


def hydraulic_diameter(*, flow_area: Quantity, wetted_perimeter: Quantity) -> Quantity:
    """The hydraulic diameter D_h = 4·A/P of a non-circular duct.

    The Darcy-Weisbach and Reynolds-number relations are written for round pipe, but they carry over
    to a rectangular HVAC duct, an annulus, or any other closed non-circular section if the diameter
    is replaced by the hydraulic diameter D_h = 4·A/P — four times the ``flow_area`` A over the
    ``wetted_perimeter`` P. For a full circular pipe it reduces exactly to the pipe diameter. Feed
    the result in as the ``diameter`` of :func:`reynolds_number` and
    :func:`darcy_weisbach_head_loss` to size a non-round duct. Returns D_h in meters.
    """
    _check(flow_area, "[area]", "flow_area")
    _check(wetted_perimeter, "[length]", "wetted_perimeter")
    a = flow_area.to("m**2").magnitude
    p = wetted_perimeter.to("m").magnitude
    if a <= 0 or p <= 0:
        raise ValueError("flow_area and wetted_perimeter must be positive")
    return Quantity(magnitude=4.0 * a / p, unit="m")


def joukowsky_surge_pressure(
    *,
    density: Quantity,
    wave_speed: Quantity,
    velocity_change: Quantity,
) -> Quantity:
    """The Joukowsky water-hammer pressure surge from a sudden change in flow, Δp = ρ·a·Δv.

    Stopping a column of moving liquid abruptly — slamming a valve shut, a pump tripping — converts
    its momentum into a pressure spike that races back up the pipe as a wave: Δp = ρ·a·Δv. The surge
    is startlingly large (halting water at just 2 m/s can spike the pressure by ~2.4 MPa), which is
    why it bursts pipes and why valves are closed slowly. ``density`` ρ, ``wave_speed`` a (the
    pressure-wave celerity, ~1200–1400 m/s for water in steel pipe), and ``velocity_change`` Δv (the
    change in flow velocity). The surge only reaches this full value for a closure faster than the
    wave round-trip — see :func:`surge_wave_period`. Returns the pressure rise in kPa.
    """
    _check(density, "[mass]/[length]**3", "density")
    _check(wave_speed, "[length]/[time]", "wave_speed")
    _check(velocity_change, "[length]/[time]", "velocity_change")
    rho = density.to("kg/m**3").magnitude
    a = wave_speed.to("m/s").magnitude
    dv = velocity_change.to("m/s").magnitude
    if rho <= 0 or a <= 0:
        raise ValueError("density and wave_speed must be positive")
    if dv < 0:
        raise ValueError("velocity_change must be non-negative")
    return Quantity(magnitude=rho * a * dv / 1000.0, unit="kPa")


def surge_wave_period(*, pipe_length: Quantity, wave_speed: Quantity) -> Quantity:
    """The pressure-wave round-trip time 2L/a — the critical valve-closure time for water hammer.

    A pressure wave launched by a closing valve travels to the far end of the pipe and reflects
    back in a time 2L/a. Close the valve faster than this and the flow is stopped before any relief
    arrives, so the full :func:`joukowsky_surge_pressure` develops; close it slower and the surge is
    reduced roughly in proportion. ``pipe_length`` L is the distance to the reservoir or reflection
    point and ``wave_speed`` a the pressure-wave celerity. Returns the critical closure time in
    seconds.
    """
    _check(pipe_length, "[length]", "pipe_length")
    _check(wave_speed, "[length]/[time]", "wave_speed")
    lo = pipe_length.to("m").magnitude
    a = wave_speed.to("m/s").magnitude
    if lo <= 0 or a <= 0:
        raise ValueError("pipe_length and wave_speed must be positive")
    return Quantity(magnitude=2.0 * lo / a, unit="s")


def cavitation_number(
    *,
    local_pressure: Quantity,
    vapor_pressure: Quantity,
    density: Quantity,
    velocity: Quantity,
) -> float:
    """The cavitation number of a flow, σ = (p − p_v)/(½·ρ·V²).

    A dimensionless margin against cavitation: how far the local absolute pressure sits above the
    liquid's vapor pressure, scaled by the flow's dynamic pressure. σ = (p − p_v)/(½·ρ·V²), from the
    ``local_pressure`` p (absolute), the ``vapor_pressure`` p_v, the ``density`` ρ, and the
    ``velocity`` V. A high σ is safe; as a valve throttles or a flow accelerates, p falls and V
    rises, driving σ down, and below a device-specific incipient value σ_i the pressure reaches
    vapor and the liquid flashes to cavities that collapse and erode the metal. It is the general
    form behind valve, orifice, and propeller cavitation. Returns the dimensionless cavitation
    number.
    """
    _check(local_pressure, "[pressure]", "local_pressure")
    _check(vapor_pressure, "[pressure]", "vapor_pressure")
    _check(density, "[mass]/[length]**3", "density")
    _check(velocity, "[length]/[time]", "velocity")
    rho = density.to("kg/m**3").magnitude
    v = velocity.to("m/s").magnitude
    if rho <= 0:
        raise ValueError("density must be positive")
    if v <= 0:
        raise ValueError("velocity must be positive")
    p = local_pressure.to("Pa").magnitude
    p_v = vapor_pressure.to("Pa").magnitude
    if p_v < 0:
        raise ValueError("vapor_pressure must be non-negative")
    return (p - p_v) / (0.5 * rho * v**2)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
