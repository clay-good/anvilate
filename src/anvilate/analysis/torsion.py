"""T1 analytical torsion checks for solid and hollow circular shafts (closed-form).

A shaft transmitting torque ``T`` carries a maximum torsional shear stress at its
surface, ``τ_max = T·r/J`` with the polar second moment ``J = π·d⁴/32`` (solid) or
``π·(D⁴−d⁴)/32`` (hollow) and ``r`` the outer radius, and twists through an angle
``θ = T·L/(G·J)``. These are the Roark / Shigley closed forms for a prismatic,
linear-elastic round shaft. As with the beam and column checks, inputs and
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
