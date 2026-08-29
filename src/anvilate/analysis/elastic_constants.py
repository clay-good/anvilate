"""T1 analytical isotropic-elastic-constant conversion checks (closed-form).

An isotropic elastic material is fully described by any two of its elastic constants — Young's
modulus E, Poisson's ratio nu, the shear modulus G, the bulk modulus K, and the Lame parameters —
and the rest follow from closed-form relations. Converting between them is the routine that turns a
datasheet E and nu into the K and G a finite-element solver or the wave-speed relations of
:mod:`anvilate.analysis.elastic_waves` need. (The shear modulus G = E/(2(1+nu)) is already available
on a materials-database :class:`~anvilate.standards.materials.Material`; these are the complementary
conversions.)

The bulk modulus, resistance to uniform compression, is K = E/(3*(1 - 2*nu)) — it diverges as nu
approaches 0.5 (an incompressible material). The Lame first parameter is
lambda = E*nu/((1 + nu)*(1 - 2*nu)), the constant that pairs with the shear modulus in the stress-
strain law. Going the other way, Young's modulus follows from the bulk and shear moduli as
E = 9*K*G/(3*K + G), the form used when K and G are the measured (for example, wave-speed-derived)
quantities.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "bulk_modulus_from_youngs_poisson",
    "lame_first_parameter",
    "youngs_modulus_from_bulk_shear",
]


def bulk_modulus_from_youngs_poisson(
    *, elastic_modulus: Quantity, poisson_ratio: float
) -> Quantity:
    """The bulk modulus, K = E/(3*(1 - 2*nu)).

    The resistance to uniform (hydrostatic) compression, from the ``elastic_modulus`` E (Young's
    modulus) and ``poisson_ratio`` nu: K = E/(3*(1 - 2*nu)). It rises steeply as nu approaches 0.5,
    where the material becomes incompressible (rubber, a confined fluid). Returns K in Pa.
    """
    _check(elastic_modulus, "[pressure]", "elastic_modulus")
    e = elastic_modulus.to("Pa").magnitude
    if e <= 0:
        raise ValueError("elastic_modulus must be positive")
    if not -1.0 < poisson_ratio < 0.5:
        raise ValueError("poisson_ratio must be in (-1, 0.5)")
    return Quantity(magnitude=e / (3.0 * (1.0 - 2.0 * poisson_ratio)), unit="Pa")


def lame_first_parameter(*, elastic_modulus: Quantity, poisson_ratio: float) -> Quantity:
    """The Lame first parameter, lambda = E*nu/((1 + nu)*(1 - 2*nu)).

    The first Lame constant, which together with the shear modulus (the second Lame parameter)
    expresses the isotropic stress-strain law, from the ``elastic_modulus`` E and ``poisson_ratio``
    nu: lambda = E*nu/((1 + nu)*(1 - 2*nu)). It is zero at nu = 0 and diverges as nu nears 0.5.
    Returns the Lame parameter in Pa.
    """
    _check(elastic_modulus, "[pressure]", "elastic_modulus")
    e = elastic_modulus.to("Pa").magnitude
    if e <= 0:
        raise ValueError("elastic_modulus must be positive")
    if not -1.0 < poisson_ratio < 0.5:
        raise ValueError("poisson_ratio must be in (-1, 0.5)")
    return Quantity(
        magnitude=e * poisson_ratio / ((1.0 + poisson_ratio) * (1.0 - 2.0 * poisson_ratio)),
        unit="Pa",
    )


def youngs_modulus_from_bulk_shear(*, bulk_modulus: Quantity, shear_modulus: Quantity) -> Quantity:
    """Young's modulus from bulk and shear moduli, E = 9*K*G/(3*K + G).

    The Young's modulus implied by a ``bulk_modulus`` K and ``shear_modulus`` G: E = 9KG/(3K + G).
    It is the conversion used when K and G are the directly-measured quantities (for instance from
    the P- and S-wave speeds of :mod:`anvilate.analysis.elastic_waves`) and the tensile modulus is
    wanted. Returns Young's modulus in Pa.
    """
    _check(bulk_modulus, "[pressure]", "bulk_modulus")
    _check(shear_modulus, "[pressure]", "shear_modulus")
    k = bulk_modulus.to("Pa").magnitude
    g = shear_modulus.to("Pa").magnitude
    if k <= 0:
        raise ValueError("bulk_modulus must be positive")
    if g <= 0:
        raise ValueError("shear_modulus must be positive")
    return Quantity(magnitude=9.0 * k * g / (3.0 * k + g), unit="Pa")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
