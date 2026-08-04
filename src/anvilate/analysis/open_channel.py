"""T1 analytical open-channel flow checks (Manning's equation, closed-form).

Water in a ditch, culvert, or spillway flows with a free surface under gravity, not pressure,
so pipe-flow head loss does not apply. The workhorse is Manning's equation, which gives the
mean velocity from the channel's shape, slope, and lining roughness:

    V = (1/n)·R^(2/3)·S^(1/2)        Q = V·A = (1/n)·A·R^(2/3)·S^(1/2)

where R = A/P is the hydraulic radius (flow area A over wetted perimeter P), S the bed slope,
and n the Manning roughness coefficient (~0.013 for concrete, ~0.030 for a natural stream).
This is the SI form — the hidden 1.0 constant carries units, so inputs are taken in and
results returned in SI (meters, m²/s, m³/s).

Whether that flow is tranquil (subcritical) or rapid (supercritical) is set by the Froude
number Fr = V/√(g·y): below 1 the flow is subcritical and controlled from downstream, above 1
supercritical. The dividing depth is the critical depth, y_c = (q²/g)^(1/3) for a rectangular
channel carrying unit discharge q = Q/b. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import acos, radians, sin, sqrt, tan

from ..units import Quantity

__all__ = [
    "circular_channel_properties",
    "critical_depth_rectangular",
    "froude_number",
    "hydraulic_jump_downstream_depth",
    "hydraulic_jump_energy_loss",
    "hydraulic_radius",
    "manning_flow_rate",
    "manning_flow_velocity",
    "broad_crested_weir_flow",
    "minimum_specific_energy_rectangular",
    "rational_method_peak_runoff",
    "rectangular_weir_flow",
    "specific_energy",
    "trapezoidal_channel_properties",
    "triangular_weir_flow",
]

_GRAVITY = 9.80665  # m/s^2, standard gravity


def hydraulic_radius(*, flow_area: Quantity, wetted_perimeter: Quantity) -> Quantity:
    """The hydraulic radius R = A/P of a channel section.

    The single length that captures how efficiently a channel carries water: the flow ``flow_area``
    A divided by its ``wetted_perimeter`` P — the length of the boundary actually in contact with
    the water (the free surface is not counted). A deep, narrow section has a larger R, and less of
    its flow drags on the walls, than a wide shallow one of the same area. Feed R to
    :func:`manning_flow_velocity` or :func:`manning_flow_rate`. Returns R in meters.
    """
    _check(flow_area, "[area]", "flow_area")
    _check(wetted_perimeter, "[length]", "wetted_perimeter")
    a = flow_area.to("m**2").magnitude
    p = wetted_perimeter.to("m").magnitude
    if a <= 0 or p <= 0:
        raise ValueError("flow_area and wetted_perimeter must be positive")
    return Quantity(magnitude=a / p, unit="m")


def manning_flow_velocity(
    *,
    roughness_coefficient: float,
    hydraulic_radius: Quantity,
    channel_slope: float,
) -> Quantity:
    """The Manning mean flow velocity V = (1/n)·R^(2/3)·S^(1/2) in an open channel.

    The average velocity of gravity-driven free-surface flow, from Manning's equation.
    ``roughness_coefficient`` n is the channel lining's Manning value (~0.013 smooth concrete,
    ~0.025 earth, ~0.035 weedy stream), ``hydraulic_radius`` R comes from
    :func:`hydraulic_radius`, and ``channel_slope`` S is the dimensionless bed slope (rise over
    run). This is the SI form of Manning's equation; the result is in m/s.
    """
    _check(hydraulic_radius, "[length]", "hydraulic_radius")
    r = hydraulic_radius.to("m").magnitude
    if roughness_coefficient <= 0:
        raise ValueError("roughness_coefficient must be positive")
    if channel_slope <= 0:
        raise ValueError("channel_slope must be positive")
    if r <= 0:
        raise ValueError("hydraulic_radius must be positive")
    return Quantity(
        magnitude=(1.0 / roughness_coefficient) * r ** (2.0 / 3.0) * sqrt(channel_slope), unit="m/s"
    )


def manning_flow_rate(
    *,
    roughness_coefficient: float,
    flow_area: Quantity,
    hydraulic_radius: Quantity,
    channel_slope: float,
) -> Quantity:
    """The Manning volumetric flow rate Q = (1/n)·A·R^(2/3)·S^(1/2) of an open channel.

    The discharge a channel carries at a given depth, Manning's velocity times the flow area.
    ``roughness_coefficient`` n, ``flow_area`` A, ``hydraulic_radius`` R (from
    :func:`hydraulic_radius`), and the dimensionless ``channel_slope`` S. This is the SI form; the
    result is in m³/s. Compare against the design storm or supply to size the channel.
    """
    _check(flow_area, "[area]", "flow_area")
    _check(hydraulic_radius, "[length]", "hydraulic_radius")
    a = flow_area.to("m**2").magnitude
    r = hydraulic_radius.to("m").magnitude
    if roughness_coefficient <= 0:
        raise ValueError("roughness_coefficient must be positive")
    if channel_slope <= 0:
        raise ValueError("channel_slope must be positive")
    if a <= 0 or r <= 0:
        raise ValueError("flow_area and hydraulic_radius must be positive")
    v = (1.0 / roughness_coefficient) * r ** (2.0 / 3.0) * sqrt(channel_slope)
    return Quantity(magnitude=v * a, unit="m**3/s")


def froude_number(*, velocity: Quantity, hydraulic_depth: Quantity) -> float:
    """The Froude number Fr = V/√(g·y) of open-channel flow.

    The ratio of flow speed to the speed of a shallow-water wave, which decides the flow regime:
    below 1 the flow is subcritical (tranquil, controlled from downstream), above 1 supercritical
    (rapid, controlled from upstream), and exactly 1 critical. ``velocity`` V is the mean velocity
    and ``hydraulic_depth`` y the flow area over the top width (the depth itself for a wide or
    rectangular channel). Returns the dimensionless Froude number.
    """
    _check(velocity, "[length]/[time]", "velocity")
    _check(hydraulic_depth, "[length]", "hydraulic_depth")
    v = velocity.to("m/s").magnitude
    y = hydraulic_depth.to("m").magnitude
    if v <= 0 or y <= 0:
        raise ValueError("velocity and hydraulic_depth must be positive")
    return v / sqrt(_GRAVITY * y)


def specific_energy(*, depth: Quantity, velocity: Quantity) -> Quantity:
    """The specific energy of open-channel flow, E = y + V²/(2g).

    The flow's energy measured from the channel bed — its depth (pressure) head plus its velocity
    head: E = y + V²/(2g), from the flow ``depth`` y and mean ``velocity`` V. Specific energy is the
    currency of open-channel transitions: a sluice gate, a step, or a weir works by trading depth
    against velocity at constant (or reduced) E, and for a given E and discharge there are two
    possible depths (one sub-, one supercritical). It bottoms out at the critical depth (see
    :func:`minimum_specific_energy_rectangular`). Returns E in meters.
    """
    _check(depth, "[length]", "depth")
    _check(velocity, "[length]/[time]", "velocity")
    y = depth.to("m").magnitude
    v = velocity.to("m/s").magnitude
    if y <= 0 or v < 0:
        raise ValueError("depth must be positive and velocity non-negative")
    return Quantity(magnitude=y + v**2 / (2.0 * _GRAVITY), unit="m")


def minimum_specific_energy_rectangular(
    *,
    flow_rate: Quantity,
    channel_width: Quantity,
) -> Quantity:
    """The minimum specific energy of a rectangular channel, E_min = 1.5·y_c.

    For a fixed discharge, a rectangular channel cannot carry the flow below a floor of specific
    energy — and that floor sits exactly at the critical depth, with the tidy result
    E_min = 1.5·y_c. Any real flow needs at least this much energy; a channel or a control structure
    operating near it is at critical flow. ``flow_rate`` Q and ``channel_width`` b give y_c via
    :func:`critical_depth_rectangular`. Returns E_min in meters.
    """
    y_c = critical_depth_rectangular(flow_rate=flow_rate, channel_width=channel_width)
    return Quantity(magnitude=1.5 * y_c.to("m").magnitude, unit="m")


def critical_depth_rectangular(*, flow_rate: Quantity, channel_width: Quantity) -> Quantity:
    """The critical depth y_c = (q²/g)^(1/3) of a rectangular open channel.

    The depth at which a rectangular channel's flow is exactly critical (Fr = 1), the boundary
    between subcritical and supercritical: y_c = (q²/g)^(1/3) from the unit discharge q = Q/b.
    ``flow_rate`` Q is the total discharge and ``channel_width`` b the channel width. A normal
    (Manning) depth above y_c means the flow runs subcritical; below it, supercritical. Returns
    y_c in meters.
    """
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(channel_width, "[length]", "channel_width")
    q_total = flow_rate.to("m**3/s").magnitude
    b = channel_width.to("m").magnitude
    if q_total <= 0 or b <= 0:
        raise ValueError("flow_rate and channel_width must be positive")
    unit_discharge = q_total / b
    return Quantity(magnitude=(unit_discharge**2 / _GRAVITY) ** (1.0 / 3.0), unit="m")


def hydraulic_jump_downstream_depth(
    *,
    upstream_depth: Quantity,
    upstream_froude_number: float,
) -> Quantity:
    """The downstream (sequent) depth of a hydraulic jump, y₂ = (y₁/2)·(√(1 + 8·Fr₁²) − 1).

    Where fast, shallow supercritical flow slams into slower water — below a spillway or a sluice
    gate — it leaps up in a turbulent hydraulic jump to a deeper, subcritical depth. The two depths
    are tied by the momentum equation: y₂ = (y₁/2)·(√(1 + 8·Fr₁²) − 1). ``upstream_depth`` y₁ is the
    supercritical depth and ``upstream_froude_number`` Fr₁ (> 1) its Froude number from
    :func:`froude_number`. The jump is the workhorse energy dissipator of stilling-basin design.
    Returns the downstream depth y₂ in meters.
    """
    _check(upstream_depth, "[length]", "upstream_depth")
    y1 = upstream_depth.to("m").magnitude
    if y1 <= 0:
        raise ValueError("upstream_depth must be positive")
    if upstream_froude_number <= 1.0:
        raise ValueError(
            f"upstream_froude_number must exceed 1 (supercritical) for a jump; "
            f"got {upstream_froude_number}"
        )
    y2 = (y1 / 2.0) * (sqrt(1.0 + 8.0 * upstream_froude_number**2) - 1.0)
    return Quantity(magnitude=y2, unit="m")


def hydraulic_jump_energy_loss(
    *,
    upstream_depth: Quantity,
    downstream_depth: Quantity,
) -> Quantity:
    """The head (energy) dissipated across a hydraulic jump, ΔE = (y₂ − y₁)³/(4·y₁·y₂).

    A hydraulic jump is violent on purpose — it exists to burn kinetic energy so the flow leaves a
    spillway tame. The specific energy it destroys is ΔE = (y₂ − y₁)³/(4·y₁·y₂), from the
    ``upstream_depth`` y₁ and ``downstream_depth`` y₂ (from
    :func:`hydraulic_jump_downstream_depth`). The stronger the jump (the larger the depth ratio),
    the more head it dissipates. Returns the energy loss as a head in meters.
    """
    _check(upstream_depth, "[length]", "upstream_depth")
    _check(downstream_depth, "[length]", "downstream_depth")
    y1 = upstream_depth.to("m").magnitude
    y2 = downstream_depth.to("m").magnitude
    if y1 <= 0 or y2 <= 0:
        raise ValueError("upstream_depth and downstream_depth must be positive")
    if y2 < y1:
        raise ValueError("downstream_depth must be at least the upstream depth (a jump raises it)")
    return Quantity(magnitude=(y2 - y1) ** 3 / (4.0 * y1 * y2), unit="m")


def trapezoidal_channel_properties(
    *,
    bottom_width: Quantity,
    depth: Quantity,
    side_slope: float,
) -> dict[str, Quantity]:
    """The flow geometry of a trapezoidal channel — the shape most earthen canals actually are.

    A trapezoidal section with ``bottom_width`` b, flow ``depth`` y, and ``side_slope`` z (the
    horizontal run per unit rise of the banks, z:1) has area A = (b + z·y)·y, wetted perimeter
    P = b + 2·y·√(1 + z²), hydraulic radius R = A/P, and top width T = b + 2·z·y. A rectangular
    channel is the z = 0 case and a triangular one the b = 0 case. Feed the area and hydraulic
    radius to :func:`manning_flow_rate`, and the top width and area to :func:`froude_number` as the
    hydraulic depth A/T. Returns a dict with keys ``"area"``, ``"wetted_perimeter"``,
    ``"hydraulic_radius"``, ``"top_width"``.
    """
    _check(bottom_width, "[length]", "bottom_width")
    _check(depth, "[length]", "depth")
    b = bottom_width.to("m").magnitude
    y = depth.to("m").magnitude
    if b < 0 or y <= 0:
        raise ValueError("bottom_width must be non-negative and depth positive")
    if side_slope < 0:
        raise ValueError("side_slope must be non-negative")
    area = (b + side_slope * y) * y
    perimeter = b + 2.0 * y * sqrt(1.0 + side_slope**2)
    if area <= 0 or perimeter <= 0:
        raise ValueError("a trapezoidal channel needs a positive bottom width or side slope")
    top_width = b + 2.0 * side_slope * y
    return {
        "area": Quantity(magnitude=area, unit="m**2"),
        "wetted_perimeter": Quantity(magnitude=perimeter, unit="m"),
        "hydraulic_radius": Quantity(magnitude=area / perimeter, unit="m"),
        "top_width": Quantity(magnitude=top_width, unit="m"),
    }


def circular_channel_properties(
    *,
    diameter: Quantity,
    depth: Quantity,
) -> dict[str, Quantity]:
    """The flow geometry of a partially-full circular pipe — the culvert and sewer case.

    A circular pipe of ``diameter`` D running at a flow ``depth`` y (0 < y < D) is filled to a
    sector subtending an angle θ = 2·arccos(1 − 2y/D). The flow area is A = (r²/2)(θ − sin θ), the
    wetted perimeter is the arc P = r·θ, and R = A/P — which for a half-full pipe reduces to the
    tidy D/4. Feed A and R to :func:`manning_flow_rate`; note a circular channel carries its
    *maximum* flow slightly below full (near 0.94·D), because the last sliver of area adds more
    wetted perimeter than flow. Returns a dict with keys ``"area"``, ``"wetted_perimeter"``,
    ``"hydraulic_radius"``, ``"top_width"``.
    """
    _check(diameter, "[length]", "diameter")
    _check(depth, "[length]", "depth")
    d = diameter.to("m").magnitude
    y = depth.to("m").magnitude
    if d <= 0:
        raise ValueError("diameter must be positive")
    if not 0.0 < y < d:
        raise ValueError("depth must be between 0 and the diameter (a free surface)")
    r = d / 2.0
    theta = 2.0 * acos(1.0 - 2.0 * y / d)
    area = (r**2 / 2.0) * (theta - sin(theta))
    perimeter = r * theta
    top_width = 2.0 * sqrt(y * (d - y))
    return {
        "area": Quantity(magnitude=area, unit="m**2"),
        "wetted_perimeter": Quantity(magnitude=perimeter, unit="m"),
        "hydraulic_radius": Quantity(magnitude=area / perimeter, unit="m"),
        "top_width": Quantity(magnitude=top_width, unit="m"),
    }


def rectangular_weir_flow(
    *,
    discharge_coefficient: float,
    crest_length: Quantity,
    head: Quantity,
) -> Quantity:
    """The discharge over a sharp-crested rectangular weir, Q = C_d·(2/3)·b·√(2g)·H^(3/2).

    A weir gauges open-channel flow the way an orifice gauges pipe flow: dam the stream, and the
    discharge follows from the head of water backed up over the crest. For a rectangular weir,
    Q = C_d·(2/3)·b·√(2g)·H^(3/2). ``discharge_coefficient`` C_d (~0.62 for a sharp crest),
    ``crest_length`` b (the weir width), and ``head`` H (the upstream water surface above the
    crest). The 3/2 power means a modest rise in head is a large rise in flow. Returns the discharge
    in m³/s.
    """
    _check(crest_length, "[length]", "crest_length")
    _check(head, "[length]", "head")
    b = crest_length.to("m").magnitude
    h = head.to("m").magnitude
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if b <= 0 or h <= 0:
        raise ValueError("crest_length and head must be positive")
    q = discharge_coefficient * (2.0 / 3.0) * b * sqrt(2.0 * _GRAVITY) * h**1.5
    return Quantity(magnitude=q, unit="m**3/s")


def broad_crested_weir_flow(
    *,
    discharge_coefficient: float,
    crest_length: Quantity,
    head: Quantity,
) -> Quantity:
    """The discharge over a broad-crested weir, Q = C_d·(2/3)^(3/2)·√g·b·H^(3/2).

    A broad-crested weir — a flat-topped sill long enough that the flow goes critical on the crest,
    the physics behind spillway sills and flumes — passes Q = C_d·(2/3)^(3/2)·√g·b·H^(3/2). Unlike a
    sharp-crested weir (a free overfall, see :func:`rectangular_weir_flow`), the discharge follows
    from the critical-flow condition on the crest, so the coefficient is different and steadier.
    ``discharge_coefficient`` C_d (~0.85–1.0, absorbing approach and friction effects),
    ``crest_length`` b (weir width), and ``head`` H (upstream depth above the crest). Returns the
    discharge in m³/s.
    """
    _check(crest_length, "[length]", "crest_length")
    _check(head, "[length]", "head")
    b = crest_length.to("m").magnitude
    h = head.to("m").magnitude
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if b <= 0 or h <= 0:
        raise ValueError("crest_length and head must be positive")
    q = discharge_coefficient * (2.0 / 3.0) ** 1.5 * sqrt(_GRAVITY) * b * h**1.5
    return Quantity(magnitude=q, unit="m**3/s")


def triangular_weir_flow(
    *,
    discharge_coefficient: float,
    notch_angle: float,
    head: Quantity,
) -> Quantity:
    """The discharge over a V-notch (triangular) weir, Q = C_d·(8/15)·tan(θ/2)·√(2g)·H^(5/2).

    A V-notch weir measures small flows more precisely than a rectangular one, because its opening
    narrows toward the bottom so even a trickle produces a readable head: Q = C_d·(8/15)·tan(θ/2)·
    √(2g)·H^(5/2). ``discharge_coefficient`` C_d (~0.58), the ``notch_angle`` θ of the vee (degrees,
    commonly 90°), and the ``head`` H above the notch vertex. The steep 5/2 power gives it its fine
    low-flow resolution. Returns the discharge in m³/s.
    """
    _check(head, "[length]", "head")
    h = head.to("m").magnitude
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if not 0.0 < notch_angle < 180.0:
        raise ValueError(f"notch_angle must be in (0, 180) degrees; got {notch_angle}")
    if h <= 0:
        raise ValueError("head must be positive")
    q = (
        discharge_coefficient
        * (8.0 / 15.0)
        * tan(radians(notch_angle) / 2.0)
        * sqrt(2.0 * _GRAVITY)
        * h**2.5
    )
    return Quantity(magnitude=q, unit="m**3/s")


def rational_method_peak_runoff(
    *,
    runoff_coefficient: float,
    rainfall_intensity: Quantity,
    drainage_area: Quantity,
) -> Quantity:
    """The peak stormwater runoff of a catchment by the rational method, Q = C·i·A.

    The design flow a storm drain, culvert, or channel must carry off a catchment: Q = C·i·A, from
    the dimensionless ``runoff_coefficient`` C (the fraction of rain that runs off rather than soaks
    in — ~0.9 for pavement, ~0.2 for lawn), the ``rainfall_intensity`` i (depth per time, for the
    design storm), and the ``drainage_area`` A. It is the peak flow the whole downstream sizing
    starts from — feed Q to :func:`manning_flow_rate` (inverted for depth) or a pipe to size the
    conduit. C must be in (0, 1]. Returns the peak runoff as a volumetric flow rate (m³/s).
    """
    _check(rainfall_intensity, "[length]/[time]", "rainfall_intensity")
    _check(drainage_area, "[length]**2", "drainage_area")
    if not 0.0 < runoff_coefficient <= 1.0:
        raise ValueError(f"runoff_coefficient must be in (0, 1]; got {runoff_coefficient}")
    i = rainfall_intensity.to("m/s").magnitude
    a = drainage_area.to("m**2").magnitude
    if i < 0:
        raise ValueError("rainfall_intensity must be non-negative")
    if a <= 0:
        raise ValueError("drainage_area must be positive")
    return Quantity(magnitude=runoff_coefficient * i * a, unit="m**3/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
