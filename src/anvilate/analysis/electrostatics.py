"""T1 analytical electrostatics (Coulomb) checks (closed-form).

Electric charges push and pull on each other by the same inverse-square geometry that governs
gravity, but far more strongly and in both signs. Coulomb's law fixes the force between charges, the
field one charge sets up in the space around it, and the potential that field is the gradient of —
the foundation of capacitors, sensors, and every electrostatic effect. This is the charge-based
counterpart to the mass-based :mod:`anvilate.analysis.gravitation`, and it underlies the junction
fields of :mod:`anvilate.analysis.pn_junction`.

The force between two point charges is F = k·q₁·q₂/r², from the charges q₁ and q₂ and their
``separation`` r, with the Coulomb constant k = 1/(4π·ε₀) ≈ 8.99×10⁹ N·m²/C² — attractive for
opposite signs, repulsive for like. A single charge q sets up a field E = k·q/r² at distance r (the
force per unit test charge) and a potential V = k·q/r (the work per unit charge to bring one in from
infinity); the field is how strongly it pushes, the potential how much energy that push represents.
Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import log, pi

from ..units import Quantity

_COULOMB_CONSTANT = 8.9875517873681764e9  # N*m**2/C**2, 1/(4*pi*eps0)
_VACUUM_PERMITTIVITY = 8.8541878128e-12  # F/m (eps0)

__all__ = [
    "coaxial_capacitance",
    "coulomb_force",
    "electric_field_energy_density",
    "electric_field_point_charge",
    "electric_potential_point_charge",
]


def coulomb_force(*, charge1: Quantity, charge2: Quantity, separation: Quantity) -> Quantity:
    """Coulomb's law, F = k·q₁·q₂/r².

    The electrostatic force between two point charges, from ``charge1`` q₁, ``charge2`` q₂, and the
    ``separation`` r: F = k·q₁·q₂/r². The sign follows the product of the charges — positive
    (repulsive) for like charges, negative (attractive) for opposite. It weakens as the inverse
    square of distance. Returns the force in N (signed).
    """
    _check(charge1, "[charge]", "charge1")
    _check(charge2, "[charge]", "charge2")
    _check(separation, "[length]", "separation")
    q1 = charge1.to("C").magnitude
    q2 = charge2.to("C").magnitude
    r = separation.to("m").magnitude
    if r <= 0:
        raise ValueError("separation must be positive")
    return Quantity(magnitude=_COULOMB_CONSTANT * q1 * q2 / (r * r), unit="N")


def electric_field_point_charge(*, charge: Quantity, distance: Quantity) -> Quantity:
    """The point-charge electric field, E = k·q/r².

    The electric field a point ``charge`` q produces at a ``distance`` r — the force per unit test
    charge: E = k·q/r². It points away from a positive charge and toward a negative one, and falls
    off as the inverse square of distance. Returns the field in V/m (signed with the charge).
    """
    _check(charge, "[charge]", "charge")
    _check(distance, "[length]", "distance")
    q = charge.to("C").magnitude
    r = distance.to("m").magnitude
    if r <= 0:
        raise ValueError("distance must be positive")
    return Quantity(magnitude=_COULOMB_CONSTANT * q / (r * r), unit="V/m")


def electric_potential_point_charge(*, charge: Quantity, distance: Quantity) -> Quantity:
    """The point-charge electric potential, V = k·q/r.

    The electric potential a point ``charge`` q produces at a ``distance`` r — the work per unit
    charge to bring a test charge in from infinity: V = k·q/r. Unlike the field it falls off only as
    1/r, and it is positive near a positive charge. Returns the potential in V (signed).
    """
    _check(charge, "[charge]", "charge")
    _check(distance, "[length]", "distance")
    q = charge.to("C").magnitude
    r = distance.to("m").magnitude
    if r <= 0:
        raise ValueError("distance must be positive")
    return Quantity(magnitude=_COULOMB_CONSTANT * q / r, unit="V")


def electric_field_energy_density(
    *, electric_field: Quantity, relative_permittivity: float = 1.0
) -> Quantity:
    """The energy stored per unit volume in an electric field, u = ½·ε₀·ε_r·E².

    An electric field carries energy even in empty space: every cubic metre holds
    u = ½·ε₀·ε_r·E², from the field strength ``electric_field`` E and the medium's
    ``relative_permittivity`` ε_r (1 for vacuum/air, higher in a dielectric). It is why a charged
    capacitor stores energy in the gap between its plates, and — integrated over the field volume —
    it recovers the ½·C·V² of a capacitor. A dielectric packs in more energy at the same field, up
    to its breakdown limit. ``electric_field`` E and ``relative_permittivity`` ε_r ≥ 1. Returns the
    energy density in J/m³.
    """
    _check(electric_field, "[electric_potential]/[length]", "electric_field")
    e = electric_field.to("V/m").magnitude
    if relative_permittivity < 1.0:
        raise ValueError("relative_permittivity must be at least 1")
    return Quantity(
        magnitude=0.5 * _VACUUM_PERMITTIVITY * relative_permittivity * e**2, unit="J/m**3"
    )


def coaxial_capacitance(
    *,
    length: Quantity,
    inner_radius: Quantity,
    outer_radius: Quantity,
    relative_permittivity: float = 1.0,
) -> Quantity:
    """The capacitance of a coaxial cylinder pair, C = 2π·ε₀·ε_r·L/ln(b/a).

    The capacitance between an inner conductor of radius a and a coaxial outer shield of radius b —
    a coax cable, a cylindrical capacitor, a feedthrough: C = 2π·ε₀·``relative_permittivity`` ε_r ·
    ``length`` L / ln(``outer_radius`` b / ``inner_radius`` a). Unlike the parallel-plate form the
    field is radial, so the geometry enters through the log of the radius ratio — a snug shield (b
    near a) gives a high capacitance per metre. ``outer_radius`` must exceed ``inner_radius`` and
    ε_r ≥ 1. Returns the capacitance in farads.
    """
    _check(length, "[length]", "length")
    _check(inner_radius, "[length]", "inner_radius")
    _check(outer_radius, "[length]", "outer_radius")
    length_m = length.to("m").magnitude
    a = inner_radius.to("m").magnitude
    b = outer_radius.to("m").magnitude
    if length_m <= 0:
        raise ValueError("length must be positive")
    if a <= 0:
        raise ValueError("inner_radius must be positive")
    if b <= a:
        raise ValueError("outer_radius must exceed inner_radius")
    if relative_permittivity < 1.0:
        raise ValueError("relative_permittivity must be at least 1")
    c = 2.0 * pi * _VACUUM_PERMITTIVITY * relative_permittivity * length_m / log(b / a)
    return Quantity(magnitude=c, unit="F")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
