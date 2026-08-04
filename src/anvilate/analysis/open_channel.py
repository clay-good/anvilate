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

from math import acos, sin, sqrt

from ..units import Quantity

__all__ = [
    "circular_channel_properties",
    "critical_depth_rectangular",
    "froude_number",
    "hydraulic_radius",
    "manning_flow_rate",
    "manning_flow_velocity",
    "trapezoidal_channel_properties",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
