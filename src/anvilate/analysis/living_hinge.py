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

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (design for polymer
processing) — the outer-fibre strain a folded hinge web sees, and the web length a strain limit
requires.
"""

from __future__ import annotations

from math import radians

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_HINGE_GEOMETRY_SOURCE = "the molded-part drawing or verified hinge geometry record"
_HINGE_MATERIAL_SOURCE = "the polymer datasheet or qualified living-hinge material record"
_HINGE_MOTION_SOURCE = "the product articulation requirement or verified fold-angle record"


class _LivingHingeInputError(RefusalError, ValueError):
    """A living-hinge input that cannot be used without correction."""


def _living_hinge_refusal(message: str, *, subject: str, source: str) -> _LivingHingeInputError:
    return _LivingHingeInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "living_hinge_fold_strain",
    "living_hinge_web_length_for_strain",
]


def _positive_mm(value: Quantity, name: str) -> float:
    if not isinstance(value, Quantity):
        raise _living_hinge_refusal(
            f"{name} must be a [length] quantity; got {value!r}",
            subject=name,
            source=_HINGE_GEOMETRY_SOURCE,
        )
    if not value.has_dimension("[length]"):
        raise _living_hinge_refusal(
            f"{name} must be a [length] quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_HINGE_GEOMETRY_SOURCE,
        )
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise _living_hinge_refusal(
            f"{name} must be positive; got {value}",
            subject=name,
            source=_HINGE_GEOMETRY_SOURCE,
        )
    return magnitude


def _check_fold_angle(fold_angle: float) -> float:
    if not 0 < fold_angle <= 180:
        raise _living_hinge_refusal(
            f"fold_angle must be in (0, 180] degrees; got {fold_angle}",
            subject="fold_angle",
            source=_HINGE_MOTION_SOURCE,
        )
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
    require_finite(fold_angle, name="fold_angle")
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
    require_finite(permissible_strain, name="permissible_strain")
    require_finite(fold_angle, name="fold_angle")
    t = _positive_mm(web_thickness, "web_thickness")
    if permissible_strain <= 0:
        raise _living_hinge_refusal(
            f"permissible_strain must be positive; got {permissible_strain}",
            subject="permissible_strain",
            source=_HINGE_MATERIAL_SOURCE,
        )
    theta = radians(_check_fold_angle(fold_angle))
    return Quantity(magnitude=theta * t / (2.0 * permissible_strain), unit="mm")
