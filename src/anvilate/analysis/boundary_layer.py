"""T1 analytical laminar flat-plate boundary-layer checks (Blasius, closed-form).

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
roughly Re < 5×10⁵; beyond that the layer trips to turbulence and these relations no longer apply.
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


__all__ = [
    "laminar_boundary_layer_thickness",
    "laminar_plate_drag_coefficient",
    "laminar_skin_friction_coefficient",
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
    re_x = _reynolds(freestream_velocity, distance, kinematic_viscosity)
    x = distance.to("m").magnitude
    return Quantity(magnitude=5.0 * x / sqrt(re_x), unit="m")


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
    re_x = _reynolds(freestream_velocity, distance, kinematic_viscosity)
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
    re_l = _reynolds(freestream_velocity, plate_length, kinematic_viscosity)
    return 1.328 / sqrt(re_l)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
