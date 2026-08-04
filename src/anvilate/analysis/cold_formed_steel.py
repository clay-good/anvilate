"""AISI cold-formed steel: the effective width of a thin compression element.

A thin cold-formed element does not carry uniform stress up to yield — it buckles
locally well before, and the middle of the element sheds load to the stiffer edges.
The AISI S100 effective-width method (Winter's formula) captures this by replacing
the full flat width with a reduced *effective* width that carries the edge stress
uniformly. That reduction is the defining calculation of cold-formed design: a wide,
thin flange can be barely half effective, and its section properties must be
recomputed on the effective section, not the gross one.

Anvilate evaluates the Winter formula from the element geometry and the applied
edge stress; the yield strength and modulus are the caller's material inputs. The
plate-buckling coefficient k is caller-supplied (4.0 for a stiffened element, 0.43
for an unstiffened one, or a computed value for an edge- or intermediately-stiffened
element).
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "aisi_plate_slenderness",
    "aisi_effective_width",
]

# AISI S100 slenderness limit below which an element is fully effective, and the
# coefficient of Winter's slenderness expression.
_AISI_SLENDERNESS_LIMIT = 0.673
_AISI_WINTER_COEFFICIENT = 1.052


def aisi_plate_slenderness(
    *,
    flat_width: Quantity,
    thickness: Quantity,
    stress: Quantity,
    elastic_modulus: Quantity,
    plate_buckling_coefficient: float = 4.0,
) -> float:
    """The AISI S100 plate slenderness λ = (1.052/√k)·(w/t)·√(f/E).

    The dimensionless slenderness that decides whether a compression element is fully
    effective: ``flat_width`` w and ``thickness`` t are the element's flat dimensions,
    ``stress`` f the applied edge (compression) stress, ``elastic_modulus`` E the
    steel's modulus, and ``plate_buckling_coefficient`` k the element's buckling
    coefficient (4.0 stiffened, 0.43 unstiffened). At λ ≤ 0.673 the element is fully
    effective; above it, it sheds load. Returns the dimensionless λ.
    """
    if not flat_width.has_dimension("[length]"):
        raise ValueError(f"flat_width must be a [length] quantity; got {flat_width}")
    if not thickness.has_dimension("[length]"):
        raise ValueError(f"thickness must be a [length] quantity; got {thickness}")
    if not stress.has_dimension("[pressure]"):
        raise ValueError(f"stress must be a [pressure] quantity; got {stress}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    w = flat_width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    f = stress.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if w <= 0 or t <= 0 or f <= 0 or e <= 0:
        raise ValueError("flat_width, thickness, stress, and elastic_modulus must be positive")
    if plate_buckling_coefficient <= 0:
        raise ValueError(
            f"plate_buckling_coefficient must be positive; got {plate_buckling_coefficient}"
        )
    return (_AISI_WINTER_COEFFICIENT / sqrt(plate_buckling_coefficient)) * (w / t) * sqrt(f / e)


def aisi_effective_width(
    *,
    flat_width: Quantity,
    thickness: Quantity,
    stress: Quantity,
    elastic_modulus: Quantity,
    plate_buckling_coefficient: float = 4.0,
) -> Quantity:
    """The AISI S100 effective width b of a compression element (Winter's formula).

    Below the slenderness limit (:func:`aisi_plate_slenderness` λ ≤ 0.673) the element
    is fully effective and b = w. Above it, the reduction factor ρ = (1 − 0.22/λ)/λ
    gives the effective width b = ρ·w — the width that, carrying the edge stress
    uniformly, matches the real post-buckling capacity. Recompute the section's area
    and modulus on the effective section. Arguments are as in
    :func:`aisi_plate_slenderness`. Returns the effective width in mm.
    """
    lam = aisi_plate_slenderness(
        flat_width=flat_width,
        thickness=thickness,
        stress=stress,
        elastic_modulus=elastic_modulus,
        plate_buckling_coefficient=plate_buckling_coefficient,
    )
    w = flat_width.to("mm").magnitude
    if lam <= _AISI_SLENDERNESS_LIMIT:
        return Quantity(magnitude=w, unit="mm")  # fully effective
    rho = (1.0 - 0.22 / lam) / lam
    return Quantity(magnitude=rho * w, unit="mm")
