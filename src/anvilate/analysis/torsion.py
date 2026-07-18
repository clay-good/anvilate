"""T1 analytical torsion checks for solid and hollow circular shafts (closed-form).

A shaft transmitting torque ``T`` carries a maximum torsional shear stress at its
surface, ``τ_max = T·r/J`` with the polar second moment ``J = π·d⁴/32`` (solid) or
``π·(D⁴−d⁴)/32`` (hollow) and ``r`` the outer radius, and twists through an angle
``θ = T·L/(G·J)``. These are the Roark / Shigley closed forms for a prismatic,
linear-elastic round shaft.

A thin-walled *closed* non-circular tube (a rectangular box frame member, say)
does not follow ``T·r/J``; its shear flows uniformly around the wall by Bredt's
formulas: ``τ = T/(2·A_m·t)`` with the median-line enclosed area ``A_m`` and wall
thickness ``t``, twisting at ``θ = T·L·s/(4·A_m²·G·t)`` over the median perimeter
``s``. A thin *open* section (a flat strip, or a slit tube / channel / angle) has
no closed shear path, so it carries torque only through its thin thickness:
``J = b·t³/3`` and ``τ = 3·T/(b·t²)`` over the developed wall width ``b`` — orders
of magnitude weaker and floppier than a closed tube of the same material, which is
why torque tubes are closed. As with the beam and column checks, inputs and
outputs are dimension-checked :class:`~anvilate.units.Quantity` values and the
arithmetic runs through Pint.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "torque_from_power",
    "polar_second_moment_solid",
    "polar_second_moment_hollow",
    "shaft_torsional_stress",
    "shaft_von_mises_stress",
    "shaft_diameter_for_torque",
    "shaft_diameter_for_bending_torsion",
    "hollow_shaft_diameter_for_bending_torsion",
    "hollow_shaft_torsional_stress",
    "shaft_twist_angle",
    "hollow_shaft_twist_angle",
    "shaft_torsional_stiffness",
    "rectangular_tube_enclosed_area",
    "rectangular_tube_torsional_stress",
    "rectangular_tube_twist_angle",
    "thin_open_strip_torsion_constant",
    "thin_open_strip_torsional_stress",
    "thin_open_strip_twist_angle",
    "elliptical_bar_torsional_stress",
    "elliptical_bar_twist_angle",
    "triangular_bar_torsional_stress",
    "triangular_bar_twist_angle",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


def torque_from_power(*, power: Quantity, rotational_speed: Quantity) -> Quantity:
    """The shaft torque T = P/ω that transmits ``power`` at ``rotational_speed``.

    The first step of any drivetrain shaft calc: a shaft delivering ``power`` P
    while turning at angular speed ω carries the torque T = P/ω. ``rotational_speed``
    is the shaft speed — pass it as **rpm or rad/s** (an angular measure that carries
    the 2π); it feeds :func:`shaft_diameter_for_torque` and
    :func:`shaft_torsional_stress`. ``power`` must be a power and
    ``rotational_speed`` a positive rotational frequency. Returns the torque in N·m.
    """
    _require(power, "[power]", "power")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    if rotational_speed.to("rad/s").magnitude <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    if power.to("W").magnitude <= 0:
        raise ValueError(f"power must be positive; got {power}")
    return _as_quantity(power.pint / rotational_speed.pint, "N*m")


def polar_second_moment_solid(diameter: Quantity) -> Quantity:
    """The polar second moment J = π·d⁴/32 of a solid circular section."""
    _require(diameter, "[length]", "diameter")
    return _as_quantity(pi * diameter.pint**4 / 32, "mm**4")


def polar_second_moment_hollow(*, outer_diameter: Quantity, inner_diameter: Quantity) -> Quantity:
    """The polar second moment J = π·(D⁴−d⁴)/32 of a hollow circular (tube)
    section. ``inner_diameter`` must be smaller than ``outer_diameter``."""
    _require(outer_diameter, "[length]", "outer_diameter")
    _require(inner_diameter, "[length]", "inner_diameter")
    do = outer_diameter.to("mm").magnitude
    di = inner_diameter.to("mm").magnitude
    if not 0 <= di < do:
        raise ValueError(
            f"inner_diameter ({inner_diameter}) must be non-negative and below "
            f"outer_diameter ({outer_diameter})"
        )
    return _as_quantity(pi * (outer_diameter.pint**4 - inner_diameter.pint**4) / 32, "mm**4")


def shaft_torsional_stress(*, torque: Quantity, diameter: Quantity) -> Quantity:
    """The maximum torsional shear stress τ_max = T·r/J = 16·T/(π·d³) at the
    surface of a solid round shaft of ``diameter`` carrying ``torque``.

    ``torque`` must be a torque (force·length) and ``diameter`` a length. Returns
    the peak shear stress as a pressure.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(diameter, "[length]", "diameter")
    d = diameter.pint
    j = pi * d**4 / 32
    r = d / 2
    stress = torque.pint * r / j
    return _as_quantity(stress, "MPa")


def shaft_von_mises_stress(
    *,
    bending_moment: Quantity,
    torque: Quantity,
    diameter: Quantity,
) -> Quantity:
    """The distortion-energy (von Mises) stress at the surface of a solid round
    shaft carrying a bending moment and a torque together.

    A shaft sees σ = 32·M/(π·d³) from bending and τ = 16·T/(π·d³) from torsion, and
    the von Mises stress combines them as σ' = √(σ² + 3·τ²) = (32/π·d³)·√(M² + ¾·T²)
    — the forward companion to :func:`shaft_diameter_for_bending_torsion`, which
    sizes the diameter to hold this stress below S_y/n. ``bending_moment`` M and
    ``torque`` T are the steady loads and ``diameter`` d the shaft diameter; the
    moment and torque are dimension-checked torques and d a length. Returns the
    equivalent stress in MPa. Screen it against the yield strength with a
    :func:`~anvilate.analysis.stress.yield_safety_factor`.
    """
    _require(bending_moment, "[force] * [length]", "bending_moment")
    _require(torque, "[force] * [length]", "torque")
    _require(diameter, "[length]", "diameter")
    m = bending_moment.to("N*mm").magnitude
    t = torque.to("N*mm").magnitude
    d = diameter.to("mm").magnitude
    equivalent = sqrt(m * m + 0.75 * t * t)
    vm = 32.0 * equivalent / (pi * d**3)
    return Quantity(magnitude=vm, unit="MPa")


def shaft_diameter_for_torque(
    *,
    torque: Quantity,
    allowable_shear: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least solid-shaft diameter to carry ``torque`` within an allowable
    torsional shear stress.

    The inverse of :func:`shaft_torsional_stress`: demanding 16·T/(π·d³) ≤
    τ_allow/n gives d_min = (16·n·T/(π·τ_allow))^(1/3) — the sizing step for a
    torque-carrying shaft. ``torque`` T is the transmitted torque,
    ``allowable_shear`` τ_allow the material's allowable shear stress, and
    ``required_safety_factor`` n the margin on it (default 1.0). Returns the
    minimum diameter in mm; the torque and stress are dimension-checked and
    ``n`` / ``allowable_shear`` must be positive.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    t = torque.to("N*mm").magnitude
    tau = allowable_shear.to("MPa").magnitude
    if tau <= 0:
        raise ValueError(f"allowable_shear must be positive; got {allowable_shear}")
    d_min = (16 * required_safety_factor * t / (pi * tau)) ** (1.0 / 3.0)
    return Quantity(magnitude=d_min, unit="mm")


def shaft_diameter_for_bending_torsion(
    *,
    bending_moment: Quantity,
    torque: Quantity,
    yield_strength: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least solid-shaft diameter to carry a steady bending moment and torque
    together, by the distortion-energy (von Mises) criterion.

    A round shaft under bending M and torsion T sees σ = 32·M/(π·d³) and τ =
    16·T/(π·d³); the von Mises stress σ' = √(σ² + 3·τ²) = (32/π·d³)·√(M² + ¾·T²).
    Setting σ' ≤ S_y/n and solving gives
    d_min = (32·n·√(M² + ¾·T²)/(π·S_y))^(1/3) — the classic ASME/Shigley static
    shaft-sizing equation (the same distortion-energy combination
    :func:`~anvilate.analysis.stress.von_mises_bending_torsion` evaluates, inverted
    for the diameter). ``bending_moment`` M and ``torque`` T are the steady loads,
    ``yield_strength`` S_y the material's yield stress, and
    ``required_safety_factor`` n the margin on yield (default 1.0). Returns the
    minimum diameter in mm; the moment/torque are dimension-checked torques, the
    strength a pressure, and ``n`` / ``yield_strength`` must be positive. Pure
    torsion (M=0) does not reduce to :func:`shaft_diameter_for_torque`, which sizes
    on shear yield τ_allow rather than the von Mises tensile yield used here.
    """
    _require(bending_moment, "[force] * [length]", "bending_moment")
    _require(torque, "[force] * [length]", "torque")
    _require(yield_strength, "[pressure]", "yield_strength")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    m = bending_moment.to("N*mm").magnitude
    t = torque.to("N*mm").magnitude
    sy = yield_strength.to("MPa").magnitude
    if sy <= 0:
        raise ValueError(f"yield_strength must be positive; got {yield_strength}")
    equivalent = sqrt(m * m + 0.75 * t * t)
    d_min = (32 * required_safety_factor * equivalent / (pi * sy)) ** (1.0 / 3.0)
    return Quantity(magnitude=d_min, unit="mm")


def hollow_shaft_diameter_for_bending_torsion(
    *,
    bending_moment: Quantity,
    torque: Quantity,
    yield_strength: Quantity,
    bore_ratio: float,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least *outer* diameter of a hollow shaft with a fixed bore ratio to
    carry a steady bending moment and torque by the distortion-energy criterion.

    A tube of outer diameter d_o and inner diameter d_i = k·d_o (bore ratio k)
    carries the same von Mises combination as a solid shaft, but its section
    properties scale by (1 − k⁴): σ' = (solid σ')/(1 − k⁴) at the same d_o. So the
    solid sizing (:func:`shaft_diameter_for_bending_torsion`) inflates by a single
    factor, d_o = d_solid/(1 − k⁴)^(1/3) — a modestly larger outer diameter that,
    hollowed out, weighs far less (a k = 0.6 bore drops ~30% of the metal). The
    load, strength, and ``required_safety_factor`` arguments are as in the solid
    form; ``bore_ratio`` k = d_i/d_o must be in [0, 1). Returns the minimum outer
    diameter in mm; k = 0 recovers the solid diameter exactly.
    """
    if not 0.0 <= bore_ratio < 1.0:
        raise ValueError(f"bore_ratio must be in [0, 1); got {bore_ratio}")
    solid = shaft_diameter_for_bending_torsion(
        bending_moment=bending_moment,
        torque=torque,
        yield_strength=yield_strength,
        required_safety_factor=required_safety_factor,
    )
    outer = solid.to("mm").magnitude / (1.0 - bore_ratio**4) ** (1.0 / 3.0)
    return Quantity(magnitude=outer, unit="mm")


def hollow_shaft_torsional_stress(
    *,
    torque: Quantity,
    outer_diameter: Quantity,
    inner_diameter: Quantity,
) -> Quantity:
    """The maximum torsional shear stress τ_max = T·r_o/J at the outer surface of
    a hollow round shaft (tube), with J = π·(D⁴−d⁴)/32 and r_o = D/2.

    ``torque`` must be a torque; ``inner_diameter`` must be below
    ``outer_diameter``. Returns the peak shear stress as a pressure.
    """
    _require(torque, "[force] * [length]", "torque")
    j = polar_second_moment_hollow(
        outer_diameter=outer_diameter, inner_diameter=inner_diameter
    ).pint
    r = outer_diameter.pint / 2
    stress = torque.pint * r / j
    return _as_quantity(stress, "MPa")


def shaft_twist_angle(
    *,
    torque: Quantity,
    length: Quantity,
    diameter: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The angle of twist θ = T·L/(G·J) of a solid round shaft.

    ``torque`` is the applied torque, ``length`` the shaft length, ``diameter``
    the shaft diameter, and ``shear_modulus`` the material's shear (rigidity)
    modulus G (= E/(2(1+ν)) for an isotropic material). Returns the twist in
    degrees. Every quantity argument is dimension-checked.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(length, "[length]", "length")
    _require(diameter, "[length]", "diameter")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    j = pi * diameter.pint**4 / 32
    angle = torque.pint * length.pint / (shear_modulus.pint * j)
    return _as_quantity(angle, "degree")


def shaft_torsional_stiffness(
    *,
    polar_second_moment: Quantity,
    length: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The torsional spring rate k_t = G·J/L of a uniform round shaft.

    The torque per unit twist a shaft of ``length`` presents at its free end,
    ``polar_second_moment`` J from :func:`polar_second_moment_solid` or
    :func:`polar_second_moment_hollow` and ``shear_modulus`` the material G.
    This is the stiffness a disc-on-shaft torsional resonance screen consumes
    (:func:`anvilate.analysis.torsional_natural_frequency`). Returns N·m per
    radian; every argument is dimension-checked.
    """
    _require(polar_second_moment, "[length]**4", "polar_second_moment")
    _require(length, "[length]", "length")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    stiffness = shear_modulus.pint * polar_second_moment.pint / length.pint
    return _as_quantity(stiffness, "N*m")


def hollow_shaft_twist_angle(
    *,
    torque: Quantity,
    length: Quantity,
    outer_diameter: Quantity,
    inner_diameter: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The angle of twist θ = T·L/(G·J) of a hollow round shaft (tube).

    Uses the hollow polar second moment J = π·(D⁴−d⁴)/32. ``length`` is the shaft
    length, ``shear_modulus`` the material G; ``inner_diameter`` must be below
    ``outer_diameter``. Returns the twist in degrees.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(length, "[length]", "length")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    j = polar_second_moment_hollow(
        outer_diameter=outer_diameter, inner_diameter=inner_diameter
    ).pint
    angle = torque.pint * length.pint / (shear_modulus.pint * j)
    return _as_quantity(angle, "degree")


def _rectangular_tube_median(width: Quantity, height: Quantity, wall_thickness: Quantity):
    """Validate a thin-walled rectangular tube and return its median-line
    ``(width, height)`` in millimetres. ``width``/``height`` are the outer
    dimensions; the wall must leave an actual cavity (``2·t`` below each side)."""
    _require(width, "[length]", "width")
    _require(height, "[length]", "height")
    _require(wall_thickness, "[length]", "wall_thickness")
    w = width.to("mm").magnitude
    h = height.to("mm").magnitude
    t = wall_thickness.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")
    if not (2 * t < w and 2 * t < h):
        raise ValueError(
            f"wall_thickness ({wall_thickness}) must be under half of both the width "
            f"({width}) and the height ({height}) to leave a cavity"
        )
    # Median (wall-centreline) side lengths: one half-wall in from each outer face.
    return w - t, h - t


def rectangular_tube_enclosed_area(
    *, width: Quantity, height: Quantity, wall_thickness: Quantity
) -> Quantity:
    """The median-line enclosed area A_m = (W−t)·(H−t) of a thin-walled
    rectangular (box) tube — the area bounded by the wall centreline, as Bredt's
    torsion formulas take it (not the outer or the clear-bore area).

    ``width`` W and ``height`` H are the outer dimensions and ``wall_thickness`` t
    the (uniform) wall. Returns an area in mm²; the wall must leave a cavity.
    """
    wm, hm = _rectangular_tube_median(width, height, wall_thickness)
    return Quantity(magnitude=wm * hm, unit="mm**2")


def rectangular_tube_torsional_stress(
    *, torque: Quantity, width: Quantity, height: Quantity, wall_thickness: Quantity
) -> Quantity:
    """The Bredt shear stress τ = T/(2·A_m·t) in the wall of a thin-walled
    rectangular (box) tube carrying ``torque``.

    The shear flows uniformly around a closed thin wall, so the stress is set by
    the median enclosed area A_m = (W−t)·(H−t) and the wall thickness t, not by
    ``T·r/J``. ``width`` W and ``height`` H are the outer dimensions. Returns the
    shear stress as a pressure; every quantity is dimension-checked.
    """
    _require(torque, "[force] * [length]", "torque")
    area = rectangular_tube_enclosed_area(
        width=width, height=height, wall_thickness=wall_thickness
    ).pint
    stress = torque.pint / (2 * area * wall_thickness.pint)
    return _as_quantity(stress, "MPa")


def rectangular_tube_twist_angle(
    *,
    torque: Quantity,
    length: Quantity,
    width: Quantity,
    height: Quantity,
    wall_thickness: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The Bredt angle of twist θ = T·L·s/(4·A_m²·G·t) of a thin-walled
    rectangular (box) tube of uniform wall.

    ``s`` is the median perimeter 2·[(W−t)+(H−t)] and A_m the median enclosed
    area; ``length`` is the member length and ``shear_modulus`` the material G.
    ``width`` W and ``height`` H are the outer dimensions. Returns the twist in
    degrees; every quantity argument is dimension-checked.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(length, "[length]", "length")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    wm, hm = _rectangular_tube_median(width, height, wall_thickness)
    area = Quantity(magnitude=wm * hm, unit="mm**2").pint
    perimeter = Quantity(magnitude=2 * (wm + hm), unit="mm").pint
    angle = (
        torque.pint
        * length.pint
        * perimeter
        / (4 * area**2 * shear_modulus.pint * wall_thickness.pint)
    )
    return _as_quantity(angle, "degree")


def _thin_open_strip_dims(width: Quantity, thickness: Quantity):
    """Validate a thin open strip and return its ``(width, thickness)`` in mm.

    ``width`` b is the developed wall width (the long dimension), ``thickness`` t
    the wall (the short one); the thin-open form wants b ≫ t (b/t ≳ 10) and
    requires b ≥ t and both positive."""
    _require(width, "[length]", "width")
    _require(thickness, "[length]", "thickness")
    b = width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    if b <= 0 or t <= 0:
        raise ValueError("width and thickness must be positive")
    if b < t:
        raise ValueError(
            f"width ({width}) is the long dimension and must be at least the "
            f"thickness ({thickness})"
        )
    return b, t


def thin_open_strip_torsion_constant(*, width: Quantity, thickness: Quantity) -> Quantity:
    """The Saint-Venant torsion constant J = b·t³/3 of a thin open section — a flat
    strip, or a slit tube / channel / angle unrolled to a developed wall width ``b``.

    An open thin wall has no closed shear loop, so its torsion constant is only
    ~(t/b)² of the enclosed-tube value; a composite open section sums the b·t³/3 of
    each leg. ``width`` b is the developed wall width and ``thickness`` t the wall.
    Returns the torsion constant in mm⁴ (the value a ``T·L/(G·J)`` twist consumes);
    the thin form wants b/t ≳ 10.
    """
    b, t = _thin_open_strip_dims(width, thickness)
    return Quantity(magnitude=b * t**3 / 3, unit="mm**4")


def thin_open_strip_torsional_stress(
    *, torque: Quantity, width: Quantity, thickness: Quantity
) -> Quantity:
    """The peak shear stress τ = 3·T/(b·t²) = T·t/J on the long face of a thin open
    section (flat strip / slit tube / channel leg) carrying ``torque``.

    With no closed shear path the torque is resisted only across the thin wall, so
    the stress runs far higher than a closed tube of the same size would.
    ``width`` b is the developed wall width and ``thickness`` t the wall. Returns
    the shear stress as a pressure; every quantity is dimension-checked.
    """
    _require(torque, "[force] * [length]", "torque")
    b, t = _thin_open_strip_dims(width, thickness)
    j = Quantity(magnitude=b * t**3 / 3, unit="mm**4").pint
    stress = torque.pint * thickness.pint / j
    return _as_quantity(stress, "MPa")


def thin_open_strip_twist_angle(
    *,
    torque: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The angle of twist θ = T·L/(G·J) = 3·T·L/(G·b·t³) of a thin open section.

    Uses the open-section torsion constant J = b·t³/3, so the same member twists
    orders of magnitude more than it would as a closed tube. ``length`` is the
    member length, ``shear_modulus`` the material G, ``width`` b the developed wall
    width, and ``thickness`` t the wall. Returns the twist in degrees; every
    quantity argument is dimension-checked.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(length, "[length]", "length")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    b, t = _thin_open_strip_dims(width, thickness)
    j = Quantity(magnitude=b * t**3 / 3, unit="mm**4").pint
    angle = torque.pint * length.pint / (shear_modulus.pint * j)
    return _as_quantity(angle, "degree")


def _elliptical_axes(semi_major_axis: Quantity, semi_minor_axis: Quantity) -> tuple[float, float]:
    _require(semi_major_axis, "[length]", "semi_major_axis")
    _require(semi_minor_axis, "[length]", "semi_minor_axis")
    a = semi_major_axis.to("mm").magnitude
    b = semi_minor_axis.to("mm").magnitude
    if a <= 0 or b <= 0:
        raise ValueError("semi_major_axis and semi_minor_axis must be positive")
    if b > a:
        raise ValueError(
            f"semi_minor_axis ({semi_minor_axis}) must not exceed semi_major_axis "
            f"({semi_major_axis})"
        )
    return a, b


def elliptical_bar_torsional_stress(
    *, torque: Quantity, semi_major_axis: Quantity, semi_minor_axis: Quantity
) -> Quantity:
    """The peak shear stress τ_max = 2·T/(π·a·b²) of a solid elliptical bar in torsion.

    The exact Saint-Venant result for a solid bar of elliptical cross-section: the
    shear stress peaks at the ends of the *minor* axis (the boundary points closest
    to the centroid) at τ_max = 2·T/(π·a·b²), where ``semi_major_axis`` a and
    ``semi_minor_axis`` b (a ≥ b) are the half-axes. At a = b it collapses to the
    circular-shaft 2·T/(π·r³). ``torque`` T is the applied torque. Returns the peak
    shear stress in MPa.
    """
    _require(torque, "[force] * [length]", "torque")
    a, b = _elliptical_axes(semi_major_axis, semi_minor_axis)
    t = torque.to("N*mm").magnitude
    return Quantity(magnitude=2.0 * t / (pi * a * b**2), unit="MPa")


def elliptical_bar_twist_angle(
    *,
    torque: Quantity,
    length: Quantity,
    semi_major_axis: Quantity,
    semi_minor_axis: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The twist θ = T·L/(G·J_t) of a solid elliptical bar, J_t = π·a³·b³/(a²+b²).

    The torsion constant of a solid ellipse is J_t = π·a³·b³/(a² + b²) — always less
    than the polar second moment, so the bar twists more than the polar-moment
    estimate would say (only a circle twists as its polar moment). ``length`` L,
    ``semi_major_axis`` a, ``semi_minor_axis`` b (a ≥ b), and ``shear_modulus`` G
    describe the bar and material. At a = b it recovers the circular-shaft twist.
    Returns the angle of twist in degrees.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(length, "[length]", "length")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    a, b = _elliptical_axes(semi_major_axis, semi_minor_axis)
    jt = Quantity(magnitude=pi * a**3 * b**3 / (a**2 + b**2), unit="mm**4").pint
    angle = torque.pint * length.pint / (shear_modulus.pint * jt)
    return _as_quantity(angle, "degree")


def _triangle_side(side_length: Quantity) -> float:
    _require(side_length, "[length]", "side_length")
    s = side_length.to("mm").magnitude
    if s <= 0:
        raise ValueError(f"side_length must be positive; got {side_length}")
    return s


def triangular_bar_torsional_stress(*, torque: Quantity, side_length: Quantity) -> Quantity:
    """The peak shear stress τ_max = 20·T/s³ of a solid equilateral-triangle bar.

    The exact Saint-Venant result for a solid bar whose cross-section is an
    equilateral triangle of side ``side_length`` s: the shear stress peaks at the
    midpoint of each side (not the corners, which are stress-free) at
    τ_max = 20·T/s³. ``torque`` T is the applied torque. Returns the peak shear
    stress in MPa.
    """
    _require(torque, "[force] * [length]", "torque")
    s = _triangle_side(side_length)
    t = torque.to("N*mm").magnitude
    return Quantity(magnitude=20.0 * t / s**3, unit="MPa")


def triangular_bar_twist_angle(
    *,
    torque: Quantity,
    length: Quantity,
    side_length: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The twist θ = T·L/(G·J_t) of a solid equilateral-triangle bar, J_t = √3·s⁴/80.

    The torsion constant of a solid equilateral triangle of side ``side_length`` s
    is J_t = √3·s⁴/80. ``length`` L and ``shear_modulus`` G are the member length
    and material shear modulus. Returns the angle of twist in degrees.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(length, "[length]", "length")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    s = _triangle_side(side_length)
    jt = Quantity(magnitude=sqrt(3.0) * s**4 / 80.0, unit="mm**4").pint
    angle = torque.pint * length.pint / (shear_modulus.pint * jt)
    return _as_quantity(angle, "degree")
