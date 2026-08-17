"""T1 analytical finite-wing aerodynamics checks (closed-form).

A wing holds an aircraft up by deflecting air downward, and three numbers govern whether it can: the
lift it develops, the drag penalty that lift costs on a finite-span wing, and the slowest speed at
which it can still carry the weight. These are the lift-side companions to the bluff-body drag of
:mod:`anvilate.analysis.drag` — that module gives the streamwise drag force, this one gives the lift
and the *induced* drag that only a lifting, finite-span wing produces.

Lift follows the same dynamic-pressure form as drag, L = ½·ρ·V²·S·C_L, from the air density ρ, the
airspeed V, the wing area S, and the lift coefficient C_L. Generating that lift on a finite wing
sheds trailing vortices whose downwash adds induced drag, C_Di = C_L²/(π·e·AR), set by the aspect
ratio AR and the Oswald efficiency e — the penalty for a stubby, low-aspect wing. Rearranging the
lift equation for the speed that just carries the weight at maximum lift gives the stall speed,
V_stall = √(2·W/(ρ·S·C_L,max)), the slowest the aircraft can fly. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "finite_wing_lift_curve_slope",
    "induced_drag_coefficient",
    "lift_coefficient_required",
    "lift_force",
    "stall_speed",
    "lift_to_drag_ratio",
    "glide_range",
    "wing_loading",
]


def lift_force(
    *,
    air_density: Quantity,
    airspeed: Quantity,
    wing_area: Quantity,
    lift_coefficient: float,
) -> Quantity:
    """The wing lift force, L = ½*ρ*V²*S*C_L.

    The aerodynamic lift a wing develops, from the ``air_density`` ρ, the ``airspeed`` V, the
    ``wing_area`` S, and the dimensionless ``lift_coefficient`` C_L: L = ½*ρ*V²*S*C_L. It grows with
    the square of airspeed, so an aircraft needs far less lift coefficient (a smaller angle of
    attack) to hold its weight at cruise than on approach. Returns the lift force in N.
    """
    _check(air_density, "[mass]/[volume]", "air_density")
    _check(airspeed, "[velocity]", "airspeed")
    _check(wing_area, "[area]", "wing_area")
    rho = air_density.to("kg/m**3").magnitude
    v = airspeed.to("m/s").magnitude
    s = wing_area.to("m**2").magnitude
    if rho <= 0:
        raise ValueError("air_density must be positive")
    if v < 0:
        raise ValueError("airspeed must be non-negative")
    if s <= 0:
        raise ValueError("wing_area must be positive")
    return Quantity(magnitude=0.5 * rho * v * v * s * lift_coefficient, unit="N")


def lift_coefficient_required(
    *,
    lift: Quantity,
    air_density: Quantity,
    airspeed: Quantity,
    wing_area: Quantity,
) -> float:
    """The lift coefficient a wing must fly at, C_L = 2·L/(ρ·V²·S).

    The design inverse of :func:`lift_force`: to carry a required ``lift`` L (the weight, in level
    flight) at a given ``air_density`` ρ, ``airspeed`` V, and ``wing_area`` S, the wing must operate
    at C_L = 2·L/(ρ·V²·S). Because it falls with the square of speed, a wing cruises at a low C_L
    (small angle of attack) and must climb toward its C_L,max — and toward the stall — as it slows.
    Comparing the required C_L against the airfoil's C_L,max is the check that the aircraft can
    actually hold altitude at that speed. Returns the dimensionless lift coefficient.
    """
    _check(lift, "[force]", "lift")
    _check(air_density, "[mass]/[volume]", "air_density")
    _check(airspeed, "[velocity]", "airspeed")
    _check(wing_area, "[area]", "wing_area")
    lift_n = lift.to("N").magnitude
    rho = air_density.to("kg/m**3").magnitude
    v = airspeed.to("m/s").magnitude
    s = wing_area.to("m**2").magnitude
    if lift_n < 0:
        raise ValueError("lift must be non-negative")
    if rho <= 0:
        raise ValueError("air_density must be positive")
    if v <= 0:
        raise ValueError("airspeed must be positive")
    if s <= 0:
        raise ValueError("wing_area must be positive")
    return 2.0 * lift_n / (rho * v * v * s)


def induced_drag_coefficient(
    *, lift_coefficient: float, aspect_ratio: float, oswald_efficiency: float = 1.0
) -> float:
    """The induced-drag coefficient, C_Di = C_L²/(π*e*AR).

    The drag coefficient due to lift on a finite wing, from the ``lift_coefficient`` C_L, the
    ``aspect_ratio`` AR (span²/area), and the ``oswald_efficiency`` e (1.0 for an ideal elliptical
    loading, ~0.7-0.85 for real wings): C_Di = C_L²/(π*e*AR). A long, high-aspect wing pays a
    smaller induced-drag penalty for the same lift. Returns the induced-drag coefficient as a float.
    """
    if aspect_ratio <= 0:
        raise ValueError("aspect_ratio must be positive")
    if not 0.0 < oswald_efficiency <= 1.0:
        raise ValueError(f"oswald_efficiency must be in (0, 1]; got {oswald_efficiency}")
    return lift_coefficient**2 / (pi * oswald_efficiency * aspect_ratio)


def stall_speed(
    *,
    weight: Quantity,
    air_density: Quantity,
    wing_area: Quantity,
    max_lift_coefficient: float,
) -> Quantity:
    """The stall speed, V_stall = √(2*W/(ρ*S*C_L,max)).

    The slowest speed at which a wing can still carry the aircraft ``weight`` W, from the
    ``air_density`` ρ, the ``wing_area`` S, and the ``max_lift_coefficient`` C_L,max, by solving the
    lift equation at maximum lift: V_stall = √(2*W/(ρ*S*C_L,max)). Below it the wing cannot generate
    enough lift and stalls. Heavier weight or thinner air raises it. Returns the stall speed in m/s.
    """
    _check(weight, "[force]", "weight")
    _check(air_density, "[mass]/[volume]", "air_density")
    _check(wing_area, "[area]", "wing_area")
    w = weight.to("N").magnitude
    rho = air_density.to("kg/m**3").magnitude
    s = wing_area.to("m**2").magnitude
    if w <= 0:
        raise ValueError("weight must be positive")
    if rho <= 0:
        raise ValueError("air_density must be positive")
    if s <= 0:
        raise ValueError("wing_area must be positive")
    if max_lift_coefficient <= 0:
        raise ValueError("max_lift_coefficient must be positive")
    return Quantity(magnitude=sqrt(2.0 * w / (rho * s * max_lift_coefficient)), unit="m/s")


def lift_to_drag_ratio(*, lift_coefficient: float, drag_coefficient: float) -> float:
    """The lift-to-drag ratio (glide ratio), L/D = C_L/C_D.

    The single number that grades aerodynamic efficiency: L/D = ``lift_coefficient`` C_L /
    ``drag_coefficient`` C_D (the total drag, parasite plus induced). It is the glide ratio — how
    far a wing travels forward per unit of height lost with no thrust — and it sets the cruise range
    and best-glide performance. A trainer runs 10–15, a sailplane 40–60. Both coefficients are
    dimensionless and taken at the same flight condition. Returns the dimensionless L/D.
    """
    if lift_coefficient < 0:
        raise ValueError("lift_coefficient must be non-negative")
    if drag_coefficient <= 0:
        raise ValueError("drag_coefficient must be positive")
    return lift_coefficient / drag_coefficient


def glide_range(*, lift_to_drag_ratio: float, altitude: Quantity) -> Quantity:
    """The still-air glide range, R = (L/D)·h.

    How far an unpowered aircraft glides from a given height: R = ``lift_to_drag_ratio`` ·
    ``altitude`` h. It follows from the glide ratio (see :func:`lift_to_drag_ratio`) — the distance
    is the height lost times L/D — and is independent of weight (a heavier aircraft glides
    the same distance, just faster). Returns the glide range in metres.
    """
    _check(altitude, "[length]", "altitude")
    h = altitude.to("m").magnitude
    if lift_to_drag_ratio < 0:
        raise ValueError("lift_to_drag_ratio must be non-negative")
    if h < 0:
        raise ValueError("altitude must be non-negative")
    return Quantity(magnitude=lift_to_drag_ratio * h, unit="m")


def wing_loading(*, weight: Quantity, wing_area: Quantity) -> Quantity:
    """The wing loading, W/S.

    The weight a wing carries per unit of its planform area: W/S, from the ``weight`` W and the
    ``wing_area`` S. It is the primary sizing parameter behind stall speed (which rises with its
    square root), turn rate, and ride quality — a low wing loading gives slow, gentle flight and
    short field lengths, a high one gives fast, smooth cruise. Returns the wing loading in Pa
    (N/m²).
    """
    _check(weight, "[force]", "weight")
    _check(wing_area, "[area]", "wing_area")
    w = weight.to("N").magnitude
    s = wing_area.to("m**2").magnitude
    if w < 0:
        raise ValueError("weight must be non-negative")
    if s <= 0:
        raise ValueError("wing_area must be positive")
    return Quantity(magnitude=w / s, unit="Pa")


def finite_wing_lift_curve_slope(
    *,
    section_lift_curve_slope: float,
    aspect_ratio: float,
    oswald_efficiency: float = 0.85,
) -> float:
    """The 3D lift-curve slope, a = a₀/(1 + a₀/(π·e·AR)).

    The module already carries the aspect ratio and Oswald efficiency for induced drag, but a user
    converting an angle of attack into a lift coefficient had only the two-dimensional
    (infinite-span) slope to work with — and that is not what a wing does.

    A finite wing sheds tip vortices, and their downwash tilts the local flow so each section sees
    a smaller effective angle of attack than the wing's geometric one. The wing therefore needs
    *more* geometric incidence for the same lift, which is exactly a shallower slope. The
    correction depends only on the aspect ratio and the span efficiency: a long thin wing loses
    little, a short stubby one loses a lot.

    Thin-airfoil theory gives a₀ = 2π ≈ 6.283 per radian. At AR = 8 and e = 0.85 the wing slope is
    4.855 per radian — the 2D value overstates it by a factor of 1.294. Using the 2D slope
    overpredicts lift by 29% at a given angle, which puts the stall angle and the wing incidence
    badly wrong in the unconservative direction.

    ``section_lift_curve_slope`` a₀ is per radian, ``aspect_ratio`` AR = b²/S (span squared over
    wing area), and ``oswald_efficiency`` e is the span efficiency, defaulting to 0.85 for a
    typical straight wing. Returns the finite-wing slope per radian as a plain float.
    """
    if section_lift_curve_slope <= 0:
        raise ValueError(
            f"section_lift_curve_slope must be positive; got {section_lift_curve_slope}"
        )
    if aspect_ratio <= 0:
        raise ValueError(f"aspect_ratio must be positive; got {aspect_ratio}")
    if not 0.0 < oswald_efficiency <= 1.0:
        raise ValueError(f"oswald_efficiency must lie in (0, 1]; got {oswald_efficiency}")
    return section_lift_curve_slope / (
        1.0 + section_lift_curve_slope / (pi * oswald_efficiency * aspect_ratio)
    )


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
