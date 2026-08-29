"""T1 analytical comminution (size-reduction) energy laws (closed-form).

Crushing and grinding a solid to a smaller size costs energy, and three classical laws bracket how
that energy scales with the size reduction — each the integral of dE = −C·dx/xⁿ for a different
exponent, so each fits a different size range.

Rittinger's law (n = 2) says the energy is proportional to the new surface area created,
E = C_R·(1/x₂ − 1/x₁), and fits fine grinding where surface dominates. Kick's law (n = 1) says the
energy depends only on the size-reduction *ratio*, E = C_K·ln(x₁/x₂), and fits coarse crushing of
large lumps. Bond's law (n = 1.5) sits between them and is the one plant engineers actually use:
W = W_i·(10/√P₈₀ − 10/√F₈₀), with the sizes as the 80%-passing feed F₈₀ and product P₈₀ in
micrometres and the Bond work index W_i (a tabulated material property, in kWh per tonne) the energy
to grind that material from a very large size down to 80% passing 100 µm.

Rittinger's and Kick's constants carry their own units so those two are dimensionally clean; Bond's
law is the empirical micrometre/kWh-per-tonne convention (like Hazen-Williams in hydraulics), so its
sizes are taken in µm and its work index and result in kWh/tonne. All are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Wills, *Mineral Processing Technology*, for the Rittinger, Kick and Bond
comminution-energy laws and the work-index convention.
"""

from __future__ import annotations

from math import log, sqrt

from ..units import Quantity

__all__ = [
    "bond_comminution_work",
    "kick_comminution_energy",
    "rittinger_comminution_energy",
]


def rittinger_comminution_energy(
    *,
    rittinger_constant: Quantity,
    feed_size: Quantity,
    product_size: Quantity,
) -> Quantity:
    """Rittinger's law specific energy, E = C_R·(1/x₂ − 1/x₁).

    The grinding energy per unit mass on the assumption it goes into new surface area: from the
    ``rittinger_constant`` C_R (a material property with units of energy·length/mass), the
    ``feed_size`` x₁, and the ``product_size`` x₂, E = C_R·(1/x₂ − 1/x₁). Because it weights the
    fine end (1/x grows as x shrinks), Rittinger's law fits fine grinding, where creating surface is
    the dominant cost. Returns the specific energy in J/kg.
    """
    _check(rittinger_constant, "[energy]*[length]/[mass]", "rittinger_constant")
    _check(feed_size, "[length]", "feed_size")
    _check(product_size, "[length]", "product_size")
    c_r = rittinger_constant.to("J*m/kg").magnitude
    x1 = feed_size.to("m").magnitude
    x2 = product_size.to("m").magnitude
    if c_r < 0:
        raise ValueError("rittinger_constant must be non-negative")
    if x1 <= 0 or x2 <= 0:
        raise ValueError("feed_size and product_size must be positive")
    if x2 > x1:
        raise ValueError("product_size cannot exceed feed_size (grinding makes particles smaller)")
    return Quantity(magnitude=c_r * (1.0 / x2 - 1.0 / x1), unit="J/kg")


def kick_comminution_energy(
    *,
    kick_constant: Quantity,
    feed_size: Quantity,
    product_size: Quantity,
) -> Quantity:
    """Kick's law specific energy, E = C_K·ln(x₁/x₂).

    The grinding energy per unit mass on the assumption it depends only on the size-reduction ratio:
    from the ``kick_constant`` C_K (a material property with units of energy/mass), the
    ``feed_size`` x₁, and the ``product_size`` x₂, E = C_K·ln(x₁/x₂). Because it sees only the ratio
    x₁/x₂, Kick's law fits coarse crushing of large lumps, where reducing a 1 m rock to 0.5 m costs
    the same as reducing 1 cm to 0.5 cm. Returns the specific energy in J/kg.
    """
    _check(kick_constant, "[energy]/[mass]", "kick_constant")
    _check(feed_size, "[length]", "feed_size")
    _check(product_size, "[length]", "product_size")
    c_k = kick_constant.to("J/kg").magnitude
    x1 = feed_size.to("m").magnitude
    x2 = product_size.to("m").magnitude
    if c_k < 0:
        raise ValueError("kick_constant must be non-negative")
    if x1 <= 0 or x2 <= 0:
        raise ValueError("feed_size and product_size must be positive")
    if x2 > x1:
        raise ValueError("product_size cannot exceed feed_size (grinding makes particles smaller)")
    return Quantity(magnitude=c_k * log(x1 / x2), unit="J/kg")


def bond_comminution_work(
    *,
    bond_work_index: Quantity,
    feed_size_80: Quantity,
    product_size_80: Quantity,
) -> Quantity:
    """Bond's law grinding work, W = W_i·(10/√P₈₀ − 10/√F₈₀).

    The practical grinding energy per tonne used across the industry: from the ``bond_work_index``
    W_i (a tabulated material property in kWh/tonne), the 80%-passing ``feed_size_80`` F₈₀, and the
    80%-passing ``product_size_80`` P₈₀, W = W_i·(10/√P₈₀ − 10/√F₈₀) with the sizes taken in
    micrometres. W_i is defined as the work to grind a material from a very coarse feed to 80%
    passing 100 µm, so the 10/√100-µm terms make W come out directly in kWh/tonne. It is the
    intermediate (n = 1.5) law between Rittinger and Kick and the standard basis for sizing ball and
    rod mills. Returns the specific grinding work in kWh/tonne.
    """
    _check(bond_work_index, "[energy]/[mass]", "bond_work_index")
    _check(feed_size_80, "[length]", "feed_size_80")
    _check(product_size_80, "[length]", "product_size_80")
    wi = bond_work_index.to("kW*hour/tonne").magnitude
    f80 = feed_size_80.to("um").magnitude
    p80 = product_size_80.to("um").magnitude
    if wi < 0:
        raise ValueError("bond_work_index must be non-negative")
    if f80 <= 0 or p80 <= 0:
        raise ValueError("feed_size_80 and product_size_80 must be positive")
    if p80 > f80:
        raise ValueError(
            "product_size_80 cannot exceed feed_size_80 (grinding makes particles smaller)"
        )
    work = wi * (10.0 / sqrt(p80) - 10.0 / sqrt(f80))
    return Quantity(magnitude=work, unit="kW*hour/tonne")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
