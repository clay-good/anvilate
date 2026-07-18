"""T1 analytical living-hinge checks (closed-form fold strain).

A living hinge is a thin web of polypropylene or polyethylene moulded in one piece with the
parts it joins, folding a hundred thousand times without a pin — the lid of a flip-top cap,
a battery door, a clamshell. It works only because it is designed by *strain*: fold a web of
thickness ``t`` and flat length ``L`` through an angle ``θ`` and the web bends to a neutral
radius R = L/θ, so its outer fibre stretches to a strain

    ε = θ · t / (2·L)   (θ in radians),

and the whole trick is keeping that strain low enough that the web survives repeated flexing
(polypropylene tolerates a strikingly high fold strain, which is why it is *the* hinge
material). A thicker web strains more; a longer one strains less, which is why a coined
living hinge is a thin, wide, generously long web, not a sharp crease.

So the design screen is: at the fold angle the hinge must reach, is the web's fold strain
under the material's permissible flexural strain? Inverting the same relation gives the
minimum web length a permissible strain demands. The fold angle is a plain-float degrees
value (the units layer carries no angles); the web thickness and length are dimension-checked
:class:`~anvilate.units.Quantity` values, and the strain is dimensionless.
"""

from __future__ import annotations

from math import radians

from ..units import Quantity

__all__ = [
    "living_hinge_fold_strain",
    "living_hinge_web_length_for_strain",
]


def _positive_mm(value: Quantity, name: str) -> float:
    if not value.has_dimension("[length]"):
        raise ValueError(
            f"{name} must be a [length] quantity; got {value.dimensionality} ({value})"
        )
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def _check_fold_angle(fold_angle: float) -> float:
    if not 0 < fold_angle <= 180:
        raise ValueError(f"fold_angle must be in (0, 180] degrees; got {fold_angle}")
    return fold_angle


def living_hinge_fold_strain(
    *, web_thickness: Quantity, web_length: Quantity, fold_angle: float = 180.0
) -> float:
    """The outer-fibre fold strain ε = θ·t/(2·L) of a living hinge.

    The peak tensile strain in the web when it is folded: for a ``web_thickness`` t and
    flat ``web_length`` L bent through ``fold_angle`` θ (degrees, default 180° for a
    full flat fold), the web bends to a neutral radius L/θ and the outer fibre strains
    ε = θ·t/(2·L) (θ in radians). Compare it against the material's permissible flexural
    strain. Returns the dimensionless strain.
    """
    t = _positive_mm(web_thickness, "web_thickness")
    ell = _positive_mm(web_length, "web_length")
    theta = radians(_check_fold_angle(fold_angle))
    return theta * t / (2.0 * ell)


def living_hinge_web_length_for_strain(
    *, web_thickness: Quantity, permissible_strain: float, fold_angle: float = 180.0
) -> Quantity:
    """The minimum web length L = θ·t/(2·ε) a permissible fold strain requires.

    The inverse of :func:`living_hinge_fold_strain`: the shortest web that keeps the fold
    strain at or below ``permissible_strain`` ε for a ``web_thickness`` t folded through
    ``fold_angle`` θ (degrees, default 180°). A longer web is fine (lower strain); a
    shorter one over-strains. ε must be positive. Returns the web length in mm.
    """
    t = _positive_mm(web_thickness, "web_thickness")
    if permissible_strain <= 0:
        raise ValueError(f"permissible_strain must be positive; got {permissible_strain}")
    theta = radians(_check_fold_angle(fold_angle))
    return Quantity(magnitude=theta * t / (2.0 * permissible_strain), unit="mm")
