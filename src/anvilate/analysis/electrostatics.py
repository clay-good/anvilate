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

from ..units import Quantity

_COULOMB_CONSTANT = 8.9875517873681764e9  # N*m**2/C**2, 1/(4*pi*eps0)

__all__ = [
    "coulomb_force",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
