"""T1 analytical flat-plate boundary-layer checks (Blasius and 1/7-power, closed-form).

When a fluid streams over a solid surface, the no-slip condition drags a thin sheet of it to rest at
the wall; the region where the velocity climbs back to the free stream is the *boundary layer*. For
a flat plate held parallel to a steady laminar stream, Blasius' similarity solution gives its
thickness, the wall shear it exerts, and the drag on the plate — all as simple functions of the
Reynolds number, distinct from the bluff-body drag coefficients of :mod:`anvilate.analysis.drag`.

Everything scales with the local Reynolds number Re_x = U·x/ν, built from the free-stream velocity
U, the distance x from the leading edge, and the kinematic viscosity ν. The layer grows as
δ = 5·x/√Re_x — thickening downstream and thinning in faster or thinner flow. The local wall shear
follows the skin-friction coefficient C_f = 0.664/√Re_x, and integrating it over a plate of length L
gives the average drag coefficient C_D = 1.328/√Re_L. These hold while the layer stays laminar,
roughly Re < 5×10⁵; beyond that the layer trips to turbulence and a separate set of relations
applies, built on the empirical 1/7-power velocity profile rather than on Blasius:
δ = 0.37·x/Re_x^0.2 and C_D = 0.074/Re_L^0.2, with the integral thicknesses fixed fractions of the
layer itself (δ* = δ/8, θ = 7δ/72).

The 99% thickness δ is a convenient edge but not a quantity that appears in any conservation law.
The two *integral* thicknesses are: the displacement thickness δ* = 1.721·x/√Re_x is how far the
wall effectively moves out into the flow (the area correction a duct or nozzle needs), and the
momentum thickness θ = 0.664·x/√Re_x carries the momentum deficit, so the drag on the plate is
D = ρU²θ by von Kármán. Their ratio H = δ*/θ is the shape factor — 2.59 laminar, about 1.3
turbulent — and a rising H is the standard warning that the layer is heading for separation.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity


def _reynolds(velocity: Quantity, length: Quantity, kinematic_viscosity: Quantity) -> float:
    u = velocity.to("m/s").magnitude
    x = length.to("m").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if u <= 0:
        raise ValueError("freestream_velocity must be positive")
    if x <= 0:
        raise ValueError("distance must be positive")
    if nu <= 0:
        raise ValueError("kinematic_viscosity must be positive")
    return u * x / nu


# The laminar-to-turbulent transition on a flat plate sits near Re = 5e5, and the 1/7-power
# turbulent correlations are fitted only out to about 1e7. Both limits are stated in every
# docstring below and both are computable from the arguments already passed, so they are
# enforced rather than advised. Past the transition the laminar forms are wrong by close to
# an order of magnitude in the unconservative direction: at Re_x = 1e7 the laminar thickness
# reads 4.74 mm against the turbulent 44.2 mm (9.3x), and the laminar plate drag coefficient
# 4.20e-4 against 2.95e-3 (7.0x low). The library already enforces this same transition in
# `thermal.flat_plate_forced_convection_coefficient` and the same idea in
# `pipe_flow.laminar_hydrodynamic_entry_length`; this module was the outlier.
_TRANSITION_REYNOLDS = 5.0e5
_TURBULENT_FIT_LIMIT = 1.0e7


def _require_laminar(reynolds: float, symbol: str) -> float:
    if reynolds > _TRANSITION_REYNOLDS:
        raise ValueError(
            f"the Blasius laminar forms hold below the transition at "
            f"{_TRANSITION_REYNOLDS:.0e}, and {symbol} = {reynolds:.4g} is past it: the "
            f"layer has tripped to turbulence and the laminar result understates the "
            f"thickness and the drag by up to an order of magnitude. Use the "
            f"turbulent_* form."
        )
    return reynolds


def _require_turbulent(reynolds: float, symbol: str) -> float:
    if reynolds < _TRANSITION_REYNOLDS:
        raise ValueError(
            f"the 1/7-power turbulent forms hold above the transition at "
            f"{_TRANSITION_REYNOLDS:.0e}, and {symbol} = {reynolds:.4g} is below it: the "
            f"layer is still laminar. Use the laminar_* form."
        )
    if reynolds > _TURBULENT_FIT_LIMIT:
        raise ValueError(
            f"the 1/7-power turbulent correlations are fitted to about "
            f"{_TURBULENT_FIT_LIMIT:.0e}, and {symbol} = {reynolds:.4g} is past the end of "
            f"the fit; use a log-law or Schlichting correlation instead of extrapolating."
        )
    return reynolds


__all__ = [
    "turbulent_displacement_thickness",
    "turbulent_momentum_thickness",
    "boundary_layer_shape_factor",
    "laminar_boundary_layer_thickness",
    "laminar_displacement_thickness",
    "laminar_momentum_thickness",
    "laminar_plate_drag_coefficient",
    "laminar_skin_friction_coefficient",
    "turbulent_boundary_layer_thickness",
    "turbulent_plate_drag_coefficient",
    "turbulent_skin_friction_coefficient",
]


def laminar_boundary_layer_thickness(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> Quantity:
    """The laminar boundary-layer thickness, δ = 5*x/√Re_x.

    The distance from a flat plate at which the velocity reaches 99% of the free stream, from the
    ``freestream_velocity`` U, the ``distance`` x from the leading edge, and the
    ``kinematic_viscosity`` ν, with Re_x = U*x/ν: δ = 5*x/√Re_x. The layer thickens downstream (as
    √x) and thins in faster or less viscous flow. Valid while laminar (Re_x below ~5e5). Returns the
    boundary-layer thickness in m.
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(distance, "[length]", "distance")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_x = _require_laminar(_reynolds(freestream_velocity, distance, kinematic_viscosity), "Re_x")
    x = distance.to("m").magnitude
    return Quantity(magnitude=5.0 * x / sqrt(re_x), unit="m")


def laminar_displacement_thickness(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> Quantity:
    """The laminar displacement thickness, δ* = 1.721*x/√Re_x.

    How far the wall effectively pushes the outer streamlines away from itself: the slowed fluid
    near the surface carries less mass than the free stream would through the same gap, and δ* is
    the wall offset that would produce the same deficit in an inviscid flow. From the
    ``freestream_velocity`` U, the ``distance`` x from the leading edge, and the
    ``kinematic_viscosity`` ν, with Re_x = U*x/ν: δ* = 1.721*x/√Re_x, about 34% of the 99%
    thickness δ of :func:`laminar_boundary_layer_thickness`. It is the correction that matters in
    internal flow — a duct, a nozzle throat, a wind-tunnel test section all lose effective area by
    δ* around their perimeter, and ignoring it is why a nominal throat passes less than its
    geometric area suggests. Valid while laminar (Re_x below ~5e5). Returns the displacement
    thickness in m.
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(distance, "[length]", "distance")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_x = _require_laminar(_reynolds(freestream_velocity, distance, kinematic_viscosity), "Re_x")
    x = distance.to("m").magnitude
    return Quantity(magnitude=1.721 * x / sqrt(re_x), unit="m")


def laminar_momentum_thickness(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> Quantity:
    """The laminar momentum thickness, θ = 0.664*x/√Re_x.

    The thickness of free stream whose momentum equals the momentum the boundary layer has lost to
    the wall. From the ``freestream_velocity`` U, the ``distance`` x from the leading edge, and the
    ``kinematic_viscosity`` ν, with Re_x = U*x/ν: θ = 0.664*x/√Re_x. It is the quantity the von
    Kármán integral momentum equation is written in, and it converts directly to drag: the friction
    force on one side of a plate of width b wetted to station x is D = ρ·U²·θ·b, with no
    coefficient needed.

    The 0.664 it shares with :func:`laminar_skin_friction_coefficient` is a Blasius coincidence,
    not an identity — θ is a length and C_f a dimensionless coefficient, and the two part company
    in the turbulent regime (θ/x = 0.036/Re^0.2 against C_f = 0.0592/Re^0.2). Valid while laminar
    (Re_x below ~5e5). Returns the momentum thickness in m.
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(distance, "[length]", "distance")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_x = _require_laminar(_reynolds(freestream_velocity, distance, kinematic_viscosity), "Re_x")
    x = distance.to("m").magnitude
    return Quantity(magnitude=0.664 * x / sqrt(re_x), unit="m")


def boundary_layer_shape_factor(
    *, displacement_thickness: Quantity, momentum_thickness: Quantity
) -> float:
    """The boundary-layer shape factor, H = δ*/θ.

    The ratio of the ``displacement_thickness`` δ* to the ``momentum_thickness`` θ — the one number
    that describes the *shape* of the velocity profile independent of how thick the layer is. A
    Blasius laminar layer sits at H = 1.721/0.664 = 2.59; a turbulent layer, fuller near the wall,
    runs about 1.3. Between those it says which regime a measured profile is in.

    Its real use is as a separation warning: an adverse pressure gradient hollows out the profile
    near the wall, which raises H, and a laminar layer separates around H ≈ 3.5 while a turbulent
    one goes at roughly 2.4. A rising H along a diffuser or an aerofoil's aft surface is the
    standard signal that the flow is about to detach — before any of the thickness relations here
    stop applying. Returns the dimensionless shape factor as a plain float.
    """
    _check(displacement_thickness, "[length]", "displacement_thickness")
    _check(momentum_thickness, "[length]", "momentum_thickness")
    delta_star = displacement_thickness.to("m").magnitude
    theta = momentum_thickness.to("m").magnitude
    if delta_star <= 0:
        raise ValueError("displacement_thickness must be positive")
    if theta <= 0:
        raise ValueError("momentum_thickness must be positive")
    return delta_star / theta


def laminar_skin_friction_coefficient(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> float:
    """The local skin-friction coefficient, C_f = 0.664/√Re_x.

    The dimensionless local wall shear on a flat plate, τ_w/(½ρU²), from the ``freestream_velocity``
    U, the ``distance`` x from the leading edge, and the ``kinematic_viscosity`` ν, with
    Re_x = U*x/ν: C_f = 0.664/√Re_x. It falls as the boundary layer thickens downstream. Valid while
    laminar (Re_x below ~5e5). Returns the skin-friction coefficient as a plain float.
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(distance, "[length]", "distance")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_x = _require_laminar(_reynolds(freestream_velocity, distance, kinematic_viscosity), "Re_x")
    return 0.664 / sqrt(re_x)


def laminar_plate_drag_coefficient(
    *, freestream_velocity: Quantity, plate_length: Quantity, kinematic_viscosity: Quantity
) -> float:
    """The average plate drag coefficient, C_D = 1.328/√Re_L.

    The friction drag coefficient of one side of a flat plate of length L, the local skin friction
    integrated over the plate, from the ``freestream_velocity`` U, the ``plate_length`` L, and the
    ``kinematic_viscosity`` ν, with Re_L = U*L/ν: C_D = 1.328/√Re_L — exactly twice the
    trailing-edge C_f. Valid while laminar (Re_L below ~5e5). Returns the drag coefficient (float).
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(plate_length, "[length]", "plate_length")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_l = _require_laminar(
        _reynolds(freestream_velocity, plate_length, kinematic_viscosity), "Re_L"
    )
    return 1.328 / sqrt(re_l)


def turbulent_boundary_layer_thickness(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> Quantity:
    """The turbulent boundary-layer thickness, δ = 0.37*x/Re_x^(1/5).

    Past transition (Re_x above ~5e5) the Blasius solution no longer applies, and the layer follows
    the empirical 1/7-power velocity profile instead: δ = 0.37*x/Re_x^(1/5), from the
    ``freestream_velocity`` U, the ``distance`` x from the leading edge, and the
    ``kinematic_viscosity`` ν, with Re_x = U*x/ν. Turbulent mixing carries free-stream momentum down
    to the wall, so the layer is markedly thicker than the laminar δ at the same Re and grows nearly
    linearly in x (as x^0.8) rather than as √x. This is the regime real plates, hulls, and fuselages
    actually run in. Assumes the layer is turbulent from the leading edge. Returns the
    boundary-layer thickness in m.
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(distance, "[length]", "distance")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_x = _require_turbulent(_reynolds(freestream_velocity, distance, kinematic_viscosity), "Re_x")
    x = distance.to("m").magnitude
    return Quantity(magnitude=0.37 * x / re_x**0.2, unit="m")


def turbulent_skin_friction_coefficient(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> float:
    """The turbulent local skin-friction coefficient, C_f = 0.0592/Re_x^(1/5).

    The dimensionless local wall shear τ_w/(½ρU²) once the layer has tripped to turbulence, the
    counterpart of :func:`laminar_skin_friction_coefficient`: C_f = 0.0592/Re_x^(1/5), from the
    ``freestream_velocity`` U, the ``distance`` x from the leading edge, and the
    ``kinematic_viscosity`` ν, with Re_x = U*x/ν. It decays far more slowly downstream than the
    laminar 1/√Re_x, and sits well above it at the same station — the steep near-wall velocity
    gradient of a turbulent profile is exactly why tripping a layer costs friction drag. Valid for
    roughly 5e5 < Re_x < 1e7. Returns the skin-friction coefficient as a plain float.
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(distance, "[length]", "distance")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_x = _require_turbulent(_reynolds(freestream_velocity, distance, kinematic_viscosity), "Re_x")
    return 0.0592 / re_x**0.2


def turbulent_plate_drag_coefficient(
    *, freestream_velocity: Quantity, plate_length: Quantity, kinematic_viscosity: Quantity
) -> float:
    """The turbulent average plate drag coefficient, C_D = 0.074/Re_L^(1/5).

    The friction drag coefficient of one side of a flat plate of length L in a fully turbulent
    layer, the local C_f integrated over the plate: C_D = 0.074/Re_L^(1/5), from the
    ``freestream_velocity`` U, the ``plate_length`` L, and the ``kinematic_viscosity`` ν, with
    Re_L = U*L/ν. The integration
    of x^(−1/5) puts it at exactly 1.25× the trailing-edge C_f (against 2× in the laminar case).
    Assumes turbulence from the leading edge, which overstates drag when the laminar run is a
    significant fraction of the plate. Valid for roughly 5e5 < Re_L < 1e7. Returns the drag
    coefficient as a plain float.
    """
    _check(freestream_velocity, "[velocity]", "freestream_velocity")
    _check(plate_length, "[length]", "plate_length")
    _check(kinematic_viscosity, "[area]/[time]", "kinematic_viscosity")
    re_l = _require_turbulent(
        _reynolds(freestream_velocity, plate_length, kinematic_viscosity), "Re_L"
    )
    return 0.074 / re_l**0.2


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def turbulent_displacement_thickness(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> Quantity:
    """The turbulent displacement thickness, δ* = δ/8 = 0.0463·x/Re_x^0.2.

    The distance the outer flow is pushed away from the wall by the momentum deficit in the
    boundary layer — the effective area loss a duct, a nozzle throat, or a wind-tunnel test
    section suffers. The module covers δ, C_f, and C_D in the turbulent regime that real plates,
    hulls, and fuselages actually run in, but δ* existed only for the laminar case.

    From the 1/7-power velocity profile, δ* = δ/8 with δ from
    :func:`turbulent_boundary_layer_thickness`. Applying the laminar coefficient at a turbulent
    Reynolds number is not a small error: at Re_x = 4×10⁶ the laminar form understates δ* by a
    factor of 2.6, and the gap widens with Reynolds number because the two carry different
    exponents (x^0.8 against x^0.5). The usual alternative is to omit the correction entirely. The
    1/7-power profile is an engineering fit valid for roughly 5×10⁵ < Re_x < 10⁷ and drifting
    slowly outside it. Returns the displacement thickness in m.
    """
    return Quantity(
        magnitude=turbulent_boundary_layer_thickness(
            freestream_velocity=freestream_velocity,
            distance=distance,
            kinematic_viscosity=kinematic_viscosity,
        )
        .to("m")
        .magnitude
        / 8.0,
        unit="m",
    )


def turbulent_momentum_thickness(
    *, freestream_velocity: Quantity, distance: Quantity, kinematic_viscosity: Quantity
) -> Quantity:
    """The turbulent momentum thickness, θ = (7/72)·δ = 0.036·x/Re_x^0.2.

    The thickness of freestream flow carrying the momentum the boundary layer has lost, and so —
    through the von Karman momentum integral — the drag on the plate up to ``distance`` x. It is
    the turbulent companion to :func:`laminar_momentum_thickness`, taken from the same 1/7-power
    profile as :func:`turbulent_displacement_thickness`.

    Two checks come for free. The shape factor δ*/θ = 72/56 = 1.286 reproduces the "about 1.3"
    that :func:`boundary_layer_shape_factor`'s own docstring gives for a turbulent layer, against
    2.59 for a laminar one — the single number that says which regime a profile is in. And the
    momentum integral C_D = 2θ/L lands within 3% of
    :func:`turbulent_plate_drag_coefficient`, the residual being the standard 1/7-power versus
    Schlichting-fit artifact rather than an error in either. Returns the momentum thickness in m.
    """
    return Quantity(
        magnitude=(7.0 / 72.0)
        * turbulent_boundary_layer_thickness(
            freestream_velocity=freestream_velocity,
            distance=distance,
            kinematic_viscosity=kinematic_viscosity,
        )
        .to("m")
        .magnitude,
        unit="m",
    )
