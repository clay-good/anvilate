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

from math import log10, pi, sqrt

from ..units import Quantity

__all__ = [
    "cavitation_number",
    "darcy_friction_factor",
    "dean_number",
    "darcy_weisbach_head_loss",
    "graetz_number",
    "hagen_poiseuille_flow_rate",
    "hagen_poiseuille_pressure_drop",
    "hagen_poiseuille_radius_for_flow",
    "hazen_williams_flow_capacity",
    "hazen_williams_head_loss",
    "hydraulic_diameter",
    "joukowsky_surge_pressure",
    "laminar_hydrodynamic_entry_length",
    "laminar_thermal_entry_length",
    "turbulent_entry_length",
    "minor_loss_head",
    "pipe_pressure_drop",
    "pressure_wave_speed",
    "reynolds_number",
    "surge_wave_period",
    "womersley_number",
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


def dean_number(
    *,
    reynolds: float,
    tube_diameter: Quantity,
    coil_diameter: Quantity,
) -> float:
    """The Dean number of flow in a curved pipe, De = Re·√(d/D).

    The dimensionless group that governs the secondary (Dean) vortices set up when flow is forced
    around a bend: De = Re·√(d/D), from the straight-pipe ``reynolds`` number Re, the
    ``tube_diameter`` d, and the coil or bend ``coil_diameter`` D (twice the radius of curvature of
    the pipe's centreline). Curvature throws the faster core fluid outward, and the return flow
    along the walls forms a counter-rotating vortex pair that boosts mixing and heat transfer while
    delaying the transition to turbulence. Below roughly De ≈ 40 the secondary flow is negligible;
    above it the Dean vortices dominate — the reason helical-coil heat exchangers and curved
    reactor tubes outperform straight ones. Returns the dimensionless Dean number.
    """
    _check(tube_diameter, "[length]", "tube_diameter")
    _check(coil_diameter, "[length]", "coil_diameter")
    if reynolds <= 0:
        raise ValueError("reynolds must be positive")
    d = tube_diameter.to("m").magnitude
    big_d = coil_diameter.to("m").magnitude
    if d <= 0 or big_d <= 0:
        raise ValueError("tube_diameter and coil_diameter must be positive")
    return reynolds * (d / big_d) ** 0.5


def womersley_number(
    *,
    radius: Quantity,
    frequency: Quantity,
    kinematic_viscosity: Quantity,
) -> float:
    """The Womersley number of pulsatile pipe flow, α = R·√(2π·f/ν).

    The dimensionless group that sets the character of an oscillating internal flow: α = R·√(ω/ν)
    with ω = 2π·f, from the pipe ``radius`` R, the oscillation ``frequency`` f, and the fluid's
    ``kinematic_viscosity`` ν. It compares the transient (unsteady inertia) timescale to the
    viscous-diffusion timescale across the pipe. When α ≲ 1 viscosity has time to diffuse across the
    bore every cycle, so the flow stays quasi-steady with a parabolic Poiseuille profile in phase
    with the driving pressure; when α ≫ 1 inertia dominates, the core moves as a flat plug that lags
    the pressure gradient by up to 90° and shear concentrates in a thin wall layer. It is the master
    parameter of hemodynamics (the aorta runs α ≈ 15) and of any reciprocating or acoustically
    driven pipe flow. ``frequency`` is taken in hertz and converted to angular frequency internally.
    Returns the dimensionless Womersley number.
    """
    _check(radius, "[length]", "radius")
    _check(frequency, "1/[time]", "frequency")
    _check(kinematic_viscosity, "[length]**2/[time]", "kinematic_viscosity")
    r = radius.to("m").magnitude
    f = frequency.to("Hz").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if r <= 0:
        raise ValueError("radius must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    if nu <= 0:
        raise ValueError("kinematic_viscosity must be positive")
    return r * sqrt(2.0 * pi * f / nu)


def laminar_hydrodynamic_entry_length(*, reynolds: float, diameter: Quantity) -> Quantity:
    """The laminar hydrodynamic entry length, L_h = 0.05·Re·D.

    The pipe length over which the velocity profile develops from flat to fully parabolic:
    L_h = 0.05·``reynolds``·``diameter`` D (laminar). Downstream of it the flow is hydrodynamically
    developed, where the Hagen-Poiseuille and fully-developed friction relations apply; upstream the
    wall shear (and pressure gradient) is higher. The entry can be metres long even in a modest
    laminar pipe, so a short line may never fully develop. Valid for laminar flow (Re ≤ 2300); for
    turbulent flow use :func:`turbulent_entry_length`. Returns the entry length in metres.
    """
    _check(diameter, "[length]", "diameter")
    d = diameter.to("m").magnitude
    if reynolds <= 0:
        raise ValueError("reynolds must be positive")
    if d <= 0:
        raise ValueError("diameter must be positive")
    if reynolds > _LAMINAR_LIMIT:
        raise ValueError(
            f"the laminar entry-length form applies for Re <= {_LAMINAR_LIMIT}; "
            "use turbulent_entry_length for turbulent flow"
        )
    return Quantity(magnitude=0.05 * reynolds * d, unit="m")


def laminar_thermal_entry_length(
    *, reynolds: float, prandtl: float, diameter: Quantity
) -> Quantity:
    """The laminar thermal entry length, L_t = 0.05·Re·Pr·D.

    The pipe length over which the temperature profile develops, longer than the hydrodynamic one by
    the Prandtl number: L_t = 0.05·``reynolds``·``prandtl``·``diameter`` D (laminar). For oils
    (Pr in the hundreds) the thermal entry can be enormous, so the flow is thermally developing over
    the whole heated length and the constant-Nusselt fully-developed value badly under-predicts the
    coefficient. For Pr < 1 (liquid metals) the thermal profile develops first instead. Valid for
    laminar flow (Re ≤ 2300). Returns the thermal entry length in metres.
    """
    _check(diameter, "[length]", "diameter")
    d = diameter.to("m").magnitude
    if reynolds <= 0:
        raise ValueError("reynolds must be positive")
    if prandtl <= 0:
        raise ValueError("prandtl must be positive")
    if d <= 0:
        raise ValueError("diameter must be positive")
    if reynolds > _LAMINAR_LIMIT:
        raise ValueError(
            f"the laminar entry-length form applies for Re <= {_LAMINAR_LIMIT}; "
            "use turbulent_entry_length for turbulent flow"
        )
    return Quantity(magnitude=0.05 * reynolds * prandtl * d, unit="m")


def graetz_number(
    *,
    reynolds: float,
    prandtl: float,
    diameter: Quantity,
    length: Quantity,
) -> float:
    """The Graetz number of developing laminar duct flow, Gz = (D/L)·Re·Pr.

    An inverse dimensionless axial distance that measures how far a heated (or cooled) laminar duct
    flow is from thermally fully developed: Gz = (D/L)·Re·Pr, from the ``reynolds`` number Re, the
    ``prandtl`` number Pr, the ``diameter`` D, and the run ``length`` L from the start of heating. A
    large Gz (short duct, fast or high-Pr flow) means the thermal boundary layer is still thin and
    the local Nusselt number is well above its fully-developed value; as Gz falls below ~1 the flow
    has become thermally developed and the constant-Nusselt result applies. Because the thermal
    entry length is L_t = 0.05·Re·Pr·D, evaluating Gz there gives exactly 20 — the classic
    developing/developed threshold. It is the argument of the Hausen and Sieder-Tate entry-region
    Nusselt correlations. Returns the dimensionless Graetz number.
    """
    _check(diameter, "[length]", "diameter")
    _check(length, "[length]", "length")
    if reynolds <= 0:
        raise ValueError("reynolds must be positive")
    if prandtl <= 0:
        raise ValueError("prandtl must be positive")
    d = diameter.to("m").magnitude
    ell = length.to("m").magnitude
    if d <= 0:
        raise ValueError("diameter must be positive")
    if ell <= 0:
        raise ValueError("length must be positive")
    return (d / ell) * reynolds * prandtl


def turbulent_entry_length(*, diameter: Quantity) -> Quantity:
    """The turbulent entry length, L ≈ 10·D.

    In turbulent pipe flow the profiles develop far faster than in laminar flow and, to first order,
    independently of the Reynolds number: the hydrodynamic and thermal entry lengths are both about
    L ≈ 10·``diameter`` D (the common engineering estimate, with the fully-developed condition
    reached somewhere between 10 and 60 diameters). Beyond a short entry a turbulent line is
    effectively fully developed everywhere, which is why the fully-developed correlations are
    usually safe for it. Returns the entry length in metres.
    """
    _check(diameter, "[length]", "diameter")
    d = diameter.to("m").magnitude
    if d <= 0:
        raise ValueError("diameter must be positive")
    return Quantity(magnitude=10.0 * d, unit="m")


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


def pressure_wave_speed(
    *,
    fluid_bulk_modulus: Quantity,
    fluid_density: Quantity,
    pipe_diameter: Quantity,
    wall_thickness: Quantity,
    wall_elastic_modulus: Quantity,
) -> Quantity:
    """The water-hammer wave celerity in an elastic pipe, a = √[(K/ρ) / (1 + K·d/(E·t))] (Korteweg).

    The pressure-wave speed that :func:`joukowsky_surge_pressure` and :func:`surge_wave_period`
    both take as a given is itself a closed form. In a rigid pipe the wave travels at the fluid's
    acoustic speed √(K/ρ) (≈1483 m/s for water); a real pipe's wall stretches under the surge and
    stores some of the energy, slowing the wave by the Korteweg correction 1 + K·d/(E·t).
    ``fluid_bulk_modulus`` K (~2.2 GPa for water) and ``fluid_density`` ρ are the fluid's;
    ``pipe_diameter`` d, ``wall_thickness`` t, and ``wall_elastic_modulus`` E (~200 GPa for steel)
    are the pipe's. A thin-walled or soft pipe (small E·t) drops the celerity sharply — the reason
    plastic pipe hammers softer than steel. Returns the wave speed in m/s.
    """
    _check(fluid_bulk_modulus, "[pressure]", "fluid_bulk_modulus")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    _check(pipe_diameter, "[length]", "pipe_diameter")
    _check(wall_thickness, "[length]", "wall_thickness")
    _check(wall_elastic_modulus, "[pressure]", "wall_elastic_modulus")
    k = fluid_bulk_modulus.to("Pa").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    d = pipe_diameter.to("m").magnitude
    t = wall_thickness.to("m").magnitude
    e = wall_elastic_modulus.to("Pa").magnitude
    if k <= 0 or rho <= 0 or d <= 0 or t <= 0 or e <= 0:
        raise ValueError("all inputs must be positive")
    a = sqrt((k / rho) / (1.0 + (k * d) / (e * t)))
    return Quantity(magnitude=a, unit="m/s")


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


def hagen_poiseuille_flow_rate(
    *, pressure_drop: Quantity, radius: Quantity, viscosity: Quantity, length: Quantity
) -> Quantity:
    """The laminar volumetric flow rate, Q = π·ΔP·r⁴/(8·μ·L) (Hagen-Poiseuille).

    The exact laminar-flow solution for a round tube: the flow a ``pressure_drop`` ΔP drives through
    a tube of ``radius`` r and ``length`` L filled with a fluid of ``viscosity`` μ,
    Q = π·ΔP·r⁴/(8·μ·L). The fourth-power dependence on radius makes it very sensitive to bore —
    halving the radius cuts the flow sixteenfold. Valid only in laminar flow (Re ≲ 2300), unlike the
    turbulent Darcy-Weisbach and Hazen-Williams laws. Returns the flow rate in m**3/s.
    """
    _check(pressure_drop, "[pressure]", "pressure_drop")
    _check(radius, "[length]", "radius")
    _check(viscosity, "[pressure]*[time]", "viscosity")
    _check(length, "[length]", "length")
    dp = pressure_drop.to("Pa").magnitude
    r = radius.to("m").magnitude
    mu = viscosity.to("Pa*s").magnitude
    length_m = length.to("m").magnitude
    if r <= 0:
        raise ValueError("radius must be positive")
    if mu <= 0:
        raise ValueError("viscosity must be positive")
    if length_m <= 0:
        raise ValueError("length must be positive")
    return Quantity(magnitude=pi * dp * r**4 / (8.0 * mu * length_m), unit="m**3/s")


def hagen_poiseuille_pressure_drop(
    *, flow_rate: Quantity, radius: Quantity, viscosity: Quantity, length: Quantity
) -> Quantity:
    """The laminar pressure drop, ΔP = 8·μ·L·Q/(π·r⁴).

    The pressure inverse of :func:`hagen_poiseuille_flow_rate`: the drop needed to push a
    ``flow_rate`` Q through a tube of ``radius`` r and ``length`` L against a ``viscosity`` μ,
    ΔP = 8·μ·L·Q/(π·r⁴). It is the pump head a laminar line (a capillary, a microchannel, a viscous
    transfer line) demands, and it soars as the bore narrows. Valid in laminar flow. Returns the
    pressure drop in Pa.
    """
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    _check(radius, "[length]", "radius")
    _check(viscosity, "[pressure]*[time]", "viscosity")
    _check(length, "[length]", "length")
    q = flow_rate.to("m**3/s").magnitude
    r = radius.to("m").magnitude
    mu = viscosity.to("Pa*s").magnitude
    length_m = length.to("m").magnitude
    if q < 0:
        raise ValueError("flow_rate must be non-negative")
    if r <= 0:
        raise ValueError("radius must be positive")
    if mu <= 0:
        raise ValueError("viscosity must be positive")
    if length_m <= 0:
        raise ValueError("length must be positive")
    return Quantity(magnitude=8.0 * mu * length_m * q / (pi * r**4), unit="Pa")


def hagen_poiseuille_radius_for_flow(
    *, flow_rate: Quantity, pressure_drop: Quantity, viscosity: Quantity, length: Quantity
) -> Quantity:
    """The tube radius for a target laminar flow, r = (8·μ·L·Q/(π·ΔP))^(1/4).

    The geometry inverse of :func:`hagen_poiseuille_flow_rate`: the bore ``radius`` a tube needs to
    pass a target ``flow_rate`` Q under an available ``pressure_drop`` ΔP, for a fluid of
    ``viscosity`` μ over a ``length`` L, r = (8·μ·L·Q/(π·ΔP))^(1/4). The quarter-power means the
    radius barely changes for large flow changes — sizing a microchannel or capillary. Returns the
    radius in m.
    """
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    _check(pressure_drop, "[pressure]", "pressure_drop")
    _check(viscosity, "[pressure]*[time]", "viscosity")
    _check(length, "[length]", "length")
    q = flow_rate.to("m**3/s").magnitude
    dp = pressure_drop.to("Pa").magnitude
    mu = viscosity.to("Pa*s").magnitude
    length_m = length.to("m").magnitude
    if q <= 0:
        raise ValueError("flow_rate must be positive")
    if dp <= 0:
        raise ValueError("pressure_drop must be positive")
    if mu <= 0:
        raise ValueError("viscosity must be positive")
    if length_m <= 0:
        raise ValueError("length must be positive")
    return Quantity(magnitude=(8.0 * mu * length_m * q / (pi * dp)) ** 0.25, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
