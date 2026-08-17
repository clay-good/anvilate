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

Sources: Cengel & Cimbala, *Fluid Mechanics: Fundamentals and Applications*,
and White, *Fluid Mechanics*, for the hydrostatic pressure, submerged-surface resultant,
and buoyancy relations.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "buoyant_force",
    "capillary_rise",
    "center_of_pressure_depth",
    "hydrostatic_force_on_plane",
    "hydrostatic_pressure",
    "metacentric_height",
    "morton_number",
    "righting_moment",
    "bond_number",
    "capillary_number",
    "ohnesorge_number",
    "stack_effect_pressure",
    "weber_number",
]

_GRAVITY = 9.80665  # m/s^2, standard gravity
_AIR_GAS_CONSTANT = 287.0  # J/(kg*K), specific gas constant of dry air


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


def metacentric_height(
    *,
    waterplane_second_moment: Quantity,
    displaced_volume: Quantity,
    buoyancy_to_gravity_distance: Quantity,
) -> Quantity:
    """The metacentric height GM = I/V − BG that decides a floating body's stability.

    A floating body — a pontoon, a barge, a buoy — is stable in roll only if, when it heels, the
    upward buoyant force acts far enough outboard to push it back upright. The metacentric height
    measures that: GM = BM − BG, where the metacentric radius BM = I/V is the
    ``waterplane_second_moment`` I (of the waterline area about the roll axis) over the
    ``displaced_volume`` V, and
    ``buoyancy_to_gravity_distance`` BG is the height of the center of gravity above the center of
    buoyancy. A positive GM is stable (the body rights itself); a negative one capsizes. A wide,
    shallow hull has a large I and is hard to tip — which is why rafts are wide. Returns GM in
    meters.
    """
    _check(waterplane_second_moment, "[length]**4", "waterplane_second_moment")
    _check(displaced_volume, "[length]**3", "displaced_volume")
    _check(buoyancy_to_gravity_distance, "[length]", "buoyancy_to_gravity_distance")
    i = waterplane_second_moment.to("m**4").magnitude
    v = displaced_volume.to("m**3").magnitude
    bg = buoyancy_to_gravity_distance.to("m").magnitude
    if i <= 0 or v <= 0:
        raise ValueError("waterplane_second_moment and displaced_volume must be positive")
    return Quantity(magnitude=i / v - bg, unit="m")


def righting_moment(
    *,
    weight: Quantity,
    metacentric_height: Quantity,
    heel_angle: float,
) -> Quantity:
    """The righting moment M = W·GM·sin(θ) that returns a heeled floating body upright.

    When a stable floating body heels by a small angle, the buoyant force and the weight form a
    couple that rights it: M = W·GM·sin(θ). ``weight`` W is the body's weight (equal to its
    buoyancy), ``metacentric_height`` GM comes from :func:`metacentric_height`, and ``heel_angle`` θ
    is the roll angle in degrees. A larger GM gives a stiffer, snappier righting response — good for
    stability but harsh in a seaway. Returns the righting moment in kN·m.
    """
    from math import radians, sin

    _check(weight, "[force]", "weight")
    _check(metacentric_height, "[length]", "metacentric_height")
    w = weight.to("kN").magnitude
    gm = metacentric_height.to("m").magnitude
    if w <= 0:
        raise ValueError("weight must be positive")
    if gm <= 0:
        raise ValueError("metacentric_height must be positive for a stable, righting body")
    if not 0.0 <= heel_angle < 90.0:
        raise ValueError(f"heel_angle must be in [0, 90) degrees; got {heel_angle}")
    return Quantity(magnitude=w * gm * sin(radians(heel_angle)), unit="kN*m")


def capillary_rise(
    *,
    surface_tension: Quantity,
    contact_angle: float,
    density: Quantity,
    tube_radius: Quantity,
) -> Quantity:
    """The height liquid climbs (or drops) in a fine tube by surface tension, h = 2σ·cosθ/(ρ·g·r).

    A wetting liquid pulls itself up a narrow tube against gravity until the surface-tension force
    around the meniscus balances the weight of the raised column: h = 2σ·cosθ/(ρ·g·r).
    ``surface_tension`` σ is the liquid's (0.0728 N/m for water in air), ``contact_angle`` θ the
    wetting angle (0° for water on clean glass; above 90° the liquid is *depressed*, as mercury is),
    ``density`` ρ, and ``tube_radius`` r the tube (or pore) radius. The rise grows as the tube
    narrows, which is why it dominates in heat-pipe wicks, soil pores, and paper — and is negligible
    in anything you'd call a pipe. Returns the rise in mm (negative for a non-wetting liquid).
    """
    _check(surface_tension, "[force]/[length]", "surface_tension")
    _check(density, "[mass]/[length]**3", "density")
    _check(tube_radius, "[length]", "tube_radius")
    from math import cos, radians

    sigma = surface_tension.to("N/m").magnitude
    rho = density.to("kg/m**3").magnitude
    r = tube_radius.to("m").magnitude
    if sigma <= 0 or rho <= 0 or r <= 0:
        raise ValueError("surface_tension, density, and tube_radius must be positive")
    if not 0.0 <= contact_angle <= 180.0:
        raise ValueError(f"contact_angle must be in [0, 180] degrees; got {contact_angle}")
    h = 2.0 * sigma * cos(radians(contact_angle)) / (rho * _GRAVITY * r)
    return Quantity(magnitude=h * 1000.0, unit="mm")


def stack_effect_pressure(
    *,
    height: Quantity,
    indoor_temperature: Quantity,
    outdoor_temperature: Quantity,
    atmospheric_pressure: Quantity,
) -> Quantity:
    """The stack-effect (buoyancy) pressure difference across a building or chimney height.

    Warm air is lighter than cold, so a column of it inside a building or a chimney floats and draws
    a pressure difference over the height — the same buoyancy that lifts a boat, acting on air
    instead of water. From the ideal-gas density difference it is Δp = g·h·(P/R)·(1/T_o − 1/T_i),
    with ``height`` h the vertical separation (from a low inlet to a high outlet), the absolute
    ``indoor_temperature`` T_i and ``outdoor_temperature`` T_o, and ``atmospheric_pressure`` P (R is
    the gas constant of air). This is the natural draft of a chimney and the stack pressure that
    drives smoke and air up tall buildings; it is largest in winter, when the inside–outside
    temperature gap is widest. Returns the pressure difference in Pa (positive when the inside is
    warmer, drawing air upward).
    """
    _check(height, "[length]", "height")
    _check(indoor_temperature, "[temperature]", "indoor_temperature")
    _check(outdoor_temperature, "[temperature]", "outdoor_temperature")
    _check(atmospheric_pressure, "[pressure]", "atmospheric_pressure")
    h = height.to("m").magnitude
    t_i = indoor_temperature.to("K").magnitude
    t_o = outdoor_temperature.to("K").magnitude
    p = atmospheric_pressure.to("Pa").magnitude
    if h <= 0 or t_i <= 0 or t_o <= 0 or p <= 0:
        raise ValueError("height, temperatures, and atmospheric_pressure must be positive")
    delta_p = _GRAVITY * h * (p / _AIR_GAS_CONSTANT) * (1.0 / t_o - 1.0 / t_i)
    return Quantity(magnitude=delta_p, unit="Pa")


def weber_number(
    *,
    density: Quantity,
    velocity: Quantity,
    characteristic_length: Quantity,
    surface_tension: Quantity,
) -> float:
    """The Weber number of a moving interface, We = ρ·V²·L/σ.

    The ratio of a flow's disrupting inertia to the surface tension holding a droplet, bubble, or
    liquid sheet together: We = ρ·V²·L/σ, from the ``density`` ρ, relative ``velocity`` V, drop or
    jet ``characteristic_length`` L, and ``surface_tension`` σ. At low We surface tension keeps a
    droplet round; above a critical value (~12 for a drop in a gas stream) the aerodynamic pressure
    overwhelms it and the drop shatters — which is exactly what an atomizer, a fuel injector, or a
    spray nozzle is engineered to do. Returns the dimensionless Weber number.
    """
    _check(density, "[mass]/[length]**3", "density")
    _check(velocity, "[length]/[time]", "velocity")
    _check(characteristic_length, "[length]", "characteristic_length")
    _check(surface_tension, "[force]/[length]", "surface_tension")
    rho = density.to("kg/m**3").magnitude
    v = velocity.to("m/s").magnitude
    length = characteristic_length.to("m").magnitude
    sigma = surface_tension.to("N/m").magnitude
    if rho <= 0 or length <= 0:
        raise ValueError("density and characteristic_length must be positive")
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    return rho * v**2 * length / sigma


def bond_number(
    *,
    density_difference: Quantity,
    characteristic_length: Quantity,
    surface_tension: Quantity,
) -> float:
    """The Bond (Eötvös) number, Bo = Δρ·g·L²/σ.

    The ratio of gravity/buoyancy to surface tension across a two-phase interface: Bo = Δρ·g·L²/σ,
    from the ``density_difference`` Δρ between the two phases, the ``characteristic_length`` L (a
    drop, bubble, or tube radius), and the ``surface_tension`` σ. When Bo ≪ 1 surface tension
    dominates and a drop or bubble stays spherical and a meniscus climbs a capillary; when Bo ≫ 1
    gravity flattens the interface and buoyancy detaches the bubble. It sets whether capillary or
    gravitational effects govern — the deciding number for capillary rise, bubble departure, and
    droplet shape. Returns the dimensionless Bond number.
    """
    _check(density_difference, "[mass]/[length]**3", "density_difference")
    _check(characteristic_length, "[length]", "characteristic_length")
    _check(surface_tension, "[force]/[length]", "surface_tension")
    d_rho = density_difference.to("kg/m**3").magnitude
    length = characteristic_length.to("m").magnitude
    sigma = surface_tension.to("N/m").magnitude
    if d_rho <= 0 or length <= 0:
        raise ValueError("density_difference and characteristic_length must be positive")
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    return d_rho * _GRAVITY * length**2 / sigma


def capillary_number(
    *,
    dynamic_viscosity: Quantity,
    velocity: Quantity,
    surface_tension: Quantity,
) -> float:
    """The capillary number, Ca = μ·V/σ.

    The ratio of viscous drag to surface tension at a moving interface: Ca = μ·V/σ, from the
    ``dynamic_viscosity`` μ, interface ``velocity`` V, and ``surface_tension`` σ. At low Ca surface
    tension holds the interface's shape and capillary forces trap residual fluid (a drop resists
    being pushed through a pore); at high Ca viscous forces smear and elongate it. It governs
    two-phase displacement in porous media, coating film thickness, and the onset of viscous
    fingering. Returns the dimensionless capillary number.
    """
    _check(dynamic_viscosity, "[pressure]*[time]", "dynamic_viscosity")
    _check(velocity, "[length]/[time]", "velocity")
    _check(surface_tension, "[force]/[length]", "surface_tension")
    mu = dynamic_viscosity.to("Pa*s").magnitude
    v = velocity.to("m/s").magnitude
    sigma = surface_tension.to("N/m").magnitude
    if mu <= 0:
        raise ValueError("dynamic_viscosity must be positive")
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    return mu * v / sigma


def ohnesorge_number(
    *,
    dynamic_viscosity: Quantity,
    density: Quantity,
    characteristic_length: Quantity,
    surface_tension: Quantity,
) -> float:
    """The Ohnesorge number, Oh = μ/√(ρ·σ·L).

    A viscosity-scaled group for atomization and droplet breakup: Oh = μ/√(ρ·σ·L), from the
    ``dynamic_viscosity`` μ, ``density`` ρ, drop or jet ``characteristic_length`` L, and
    ``surface_tension`` σ. It measures viscous forces against the geometric mean of inertia and
    surface tension, and is exactly Oh = √We/Re — independent of velocity, so it characterizes the
    fluid and length scale alone. Low Oh liquids (like water) break into clean droplets; high Oh
    liquids resist breakup and form long ligaments. Together with the Weber number it maps the
    regimes of a spray, an inkjet, or a fuel injector. Returns the dimensionless Ohnesorge number.
    """
    _check(dynamic_viscosity, "[pressure]*[time]", "dynamic_viscosity")
    _check(density, "[mass]/[length]**3", "density")
    _check(characteristic_length, "[length]", "characteristic_length")
    _check(surface_tension, "[force]/[length]", "surface_tension")
    mu = dynamic_viscosity.to("Pa*s").magnitude
    rho = density.to("kg/m**3").magnitude
    length = characteristic_length.to("m").magnitude
    sigma = surface_tension.to("N/m").magnitude
    if mu <= 0:
        raise ValueError("dynamic_viscosity must be positive")
    if rho <= 0 or length <= 0:
        raise ValueError("density and characteristic_length must be positive")
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    return mu / (rho * sigma * length) ** 0.5


def morton_number(
    *,
    dynamic_viscosity: Quantity,
    density_difference: Quantity,
    density: Quantity,
    surface_tension: Quantity,
) -> float:
    """The Morton number, Mo = g·μ⁴·Δρ / (ρ²·σ³).

    A pure material-property group for a bubble or drop rising in a quiescent liquid:
    Mo = g·μ⁴·Δρ / (ρ²·σ³), from the continuous-phase ``dynamic_viscosity`` μ and ``density`` ρ,
    the ``density_difference`` Δρ across the interface, and the ``surface_tension`` σ. Unlike the
    Weber or Reynolds number it contains no velocity or length — it depends only on the fluids, so
    it stays fixed as a bubble grows or accelerates. Paired with the Eötvös (Bond) number it fixes
    a bubble's position on the Grace diagram, predicting whether it rises as a sphere, an
    ellipsoid, or a wobbling spherical cap. Low Mo (like an air bubble in water, ~2.5×10⁻¹¹) gives
    clean ellipsoidal bubbles; high Mo viscous liquids keep bubbles spherical. Returns the
    dimensionless Morton number.
    """
    _check(dynamic_viscosity, "[pressure]*[time]", "dynamic_viscosity")
    _check(density_difference, "[mass]/[length]**3", "density_difference")
    _check(density, "[mass]/[length]**3", "density")
    _check(surface_tension, "[force]/[length]", "surface_tension")
    mu = dynamic_viscosity.to("Pa*s").magnitude
    d_rho = density_difference.to("kg/m**3").magnitude
    rho = density.to("kg/m**3").magnitude
    sigma = surface_tension.to("N/m").magnitude
    if mu <= 0:
        raise ValueError("dynamic_viscosity must be positive")
    if d_rho <= 0:
        raise ValueError("density_difference must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    return _GRAVITY * mu**4 * d_rho / (rho**2 * sigma**3)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
