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

from math import pi

from ..units import Quantity

__all__ = [
    "polar_second_moment_solid",
    "polar_second_moment_hollow",
    "shaft_torsional_stress",
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
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


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
