"""T1 analytical fluid-statics checks (hydrostatic pressure and forces, closed-form).

A fluid at rest still pushes. Its gauge pressure grows straight down with depth, p = ρ·g·h, and
that pressure is what loads a tank wall, a dam, a submerged gate, or a floating hull.

On a submerged plane surface the pressure varies over the area, but its resultant is simply the
pressure at the surface's centroid times the area, F = ρ·g·h_c·A. That resultant does not act at
the centroid, though — because pressure is heavier lower down, the line of action sits below it,
at the center of pressure h_cp = h_c + I_c/(h_c·A), where I_c is the area's second moment about
its own horizontal centroidal axis. Getting that lever arm right is what sizes a gate hinge or a
dam's overturning check.

A fully or partly submerged body feels the buoyant force of the fluid it displaces,
F_b = ρ·g·V (Archimedes). Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "buoyant_force",
    "center_of_pressure_depth",
    "hydrostatic_force_on_plane",
    "hydrostatic_pressure",
]

_GRAVITY = 9.80665  # m/s^2, standard gravity


def hydrostatic_pressure(*, depth: Quantity, density: Quantity) -> Quantity:
    """The hydrostatic gauge pressure p = ρ·g·h at a depth in a static fluid.

    The pressure a still fluid exerts by its own weight, rising linearly with depth: p = ρ·g·h
    from the ``depth`` h below the free surface and the fluid ``density`` ρ. This is gauge pressure
    (above the surface pressure) — the load a tank wall or dam face carries at that depth. Returns
    the pressure in kPa.
    """
    _check(depth, "[length]", "depth")
    _check(density, "[mass]/[length]**3", "density")
    h = depth.to("m").magnitude
    rho = density.to("kg/m**3").magnitude
    if h < 0 or rho <= 0:
        raise ValueError("depth must be non-negative and density positive")
    return Quantity(magnitude=rho * _GRAVITY * h / 1000.0, unit="kPa")


def hydrostatic_force_on_plane(
    *,
    density: Quantity,
    centroid_depth: Quantity,
    area: Quantity,
) -> Quantity:
    """The resultant hydrostatic force F = ρ·g·h_c·A on a submerged plane surface.

    The total push of a static fluid on a flat submerged surface (a gate, a tank wall, a dam
    face): although the pressure varies over the face, the resultant is the pressure at the
    surface's centroid times its area, F = ρ·g·h_c·A. ``density`` ρ is the fluid density,
    ``centroid_depth`` h_c the vertical depth of the area's centroid below the free surface, and
    ``area`` A the wetted area. The line of action is *below* the centroid — see
    :func:`center_of_pressure_depth`. Returns the force in kN.
    """
    _check(density, "[mass]/[length]**3", "density")
    _check(centroid_depth, "[length]", "centroid_depth")
    _check(area, "[area]", "area")
    rho = density.to("kg/m**3").magnitude
    h_c = centroid_depth.to("m").magnitude
    a = area.to("m**2").magnitude
    if rho <= 0 or a <= 0:
        raise ValueError("density and area must be positive")
    if h_c <= 0:
        raise ValueError("centroid_depth must be positive")
    return Quantity(magnitude=rho * _GRAVITY * h_c * a / 1000.0, unit="kN")


def center_of_pressure_depth(
    *,
    centroid_depth: Quantity,
    area: Quantity,
    second_moment: Quantity,
) -> Quantity:
    """The center-of-pressure depth h_cp = h_c + I_c/(h_c·A) of a submerged plane surface.

    Because a fluid's pressure grows with depth, the resultant force on a submerged surface acts
    below the surface's centroid, at h_cp = h_c + I_c/(h_c·A). ``centroid_depth`` h_c is the
    centroid's depth, ``area`` A the wetted area, and ``second_moment`` I_c the area's second
    moment about its own horizontal centroidal axis (b·h³/12 for a vertical rectangle). This is
    the lever arm a gate-hinge or overturning check needs — for a surface-piercing vertical
    rectangle it lands at two-thirds of the depth. Returns the depth in meters.
    """
    _check(centroid_depth, "[length]", "centroid_depth")
    _check(area, "[area]", "area")
    _check(second_moment, "[length]**4", "second_moment")
    h_c = centroid_depth.to("m").magnitude
    a = area.to("m**2").magnitude
    i_c = second_moment.to("m**4").magnitude
    if h_c <= 0 or a <= 0 or i_c <= 0:
        raise ValueError("centroid_depth, area, and second_moment must be positive")
    return Quantity(magnitude=h_c + i_c / (h_c * a), unit="m")


def buoyant_force(*, displaced_volume: Quantity, fluid_density: Quantity) -> Quantity:
    """The Archimedes buoyant force F_b = ρ·g·V on a submerged (or floating) body.

    The upward force a fluid exerts on a body equal to the weight of the fluid it displaces:
    F_b = ρ·g·V. ``displaced_volume`` V is the submerged volume and ``fluid_density`` ρ the
    fluid's density. A body floats when this equals its weight and sinks when its weight exceeds
    the fully-submerged buoyancy. Returns the force in kN.
    """
    _check(displaced_volume, "[length]**3", "displaced_volume")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    v = displaced_volume.to("m**3").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    if v <= 0 or rho <= 0:
        raise ValueError("displaced_volume and fluid_density must be positive")
    return Quantity(magnitude=rho * _GRAVITY * v / 1000.0, unit="kN")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
