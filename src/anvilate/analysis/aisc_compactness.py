"""T1 AISC 360 flexural compactness classification (Table B4.1b, closed-form).

Before a beam's bending strength can be found, its plate elements must be classified: a *compact*
section can reach its full plastic moment M_p, a *noncompact* one yields only partway before a
flange or web buckles locally, and a *slender* one buckles while still elastic. The class decides
which strength equation (§F2 vs §F3/§F4) governs.

The test is slenderness against two limits. For a rolled I-shape in flexure the flange slenderness
is λ = b_f/(2·t_f) and the web slenderness is λ = h/t_w, each compared to a plastic limit λ_p and a
noncompact limit λ_r that scale with √(E/F_y): compact when λ ≤ λ_p, noncompact when λ_p < λ ≤ λ_r,
slender when λ > λ_r. The Table B4.1b coefficients — 0.38 and 1.0 for the flange, 3.76 and 5.70 for
the web — are AISC's; the yield strength and modulus are the caller's.
"""

from __future__ import annotations

from enum import StrEnum
from math import sqrt

from ..units import Quantity

__all__ = [
    "CompactnessClass",
    "classify_flexural_element",
    "flexural_flange_slenderness_limits",
    "flexural_web_slenderness_limits",
]

# AISC 360 Table B4.1b coefficients (× √(E/F_y)) for a doubly-symmetric I-shape in flexure.
_FLANGE_PLASTIC_COEFFICIENT = 0.38
_FLANGE_NONCOMPACT_COEFFICIENT = 1.0
_WEB_PLASTIC_COEFFICIENT = 3.76
_WEB_NONCOMPACT_COEFFICIENT = 5.70


class CompactnessClass(StrEnum):
    """The flexural classification of a section element (AISC §B4.1).

    ``COMPACT`` reaches the plastic moment; ``NONCOMPACT`` yields partway before local buckling;
    ``SLENDER`` buckles locally while still elastic. The governing element (the worst of flange and
    web) sets the section's class and its flexural-strength equation.
    """

    COMPACT = "compact"
    NONCOMPACT = "noncompact"
    SLENDER = "slender"


def _slenderness_root(elastic_modulus: Quantity, yield_strength: Quantity) -> float:
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    if not yield_strength.has_dimension("[pressure]"):
        raise ValueError(f"yield_strength must be a [pressure] quantity; got {yield_strength}")
    e = elastic_modulus.to("MPa").magnitude
    fy = yield_strength.to("MPa").magnitude
    if e <= 0 or fy <= 0:
        raise ValueError("elastic_modulus and yield_strength must be positive")
    return sqrt(e / fy)


def flexural_flange_slenderness_limits(
    *,
    elastic_modulus: Quantity,
    yield_strength: Quantity,
) -> tuple[float, float]:
    """The flange plastic and noncompact slenderness limits, (0.38·√(E/F_y), 1.0·√(E/F_y)).

    The two limits a compression flange's slenderness λ = b_f/(2·t_f) is judged against (AISC Table
    B4.1b, case 10): λ_p = 0.38·√(E/F_y) and λ_r = 1.0·√(E/F_y), from the ``elastic_modulus`` E and
    the ``yield_strength`` F_y. A stronger steel (higher F_y) lowers both limits, so a flange
    compact in mild steel can be noncompact in high-strength steel. Returns the tuple (λ_p, λ_r).
    """
    root = _slenderness_root(elastic_modulus, yield_strength)
    return (_FLANGE_PLASTIC_COEFFICIENT * root, _FLANGE_NONCOMPACT_COEFFICIENT * root)


def flexural_web_slenderness_limits(
    *,
    elastic_modulus: Quantity,
    yield_strength: Quantity,
) -> tuple[float, float]:
    """The web plastic and noncompact slenderness limits, (3.76·√(E/F_y), 5.70·√(E/F_y)).

    The two limits a web's slenderness λ = h/t_w is judged against (AISC Table B4.1b, case 15):
    λ_p = 3.76·√(E/F_y) and λ_r = 5.70·√(E/F_y), from the ``elastic_modulus`` E and the
    ``yield_strength`` F_y. Standard rolled shapes have compact webs; slender webs appear in
    deep welded plate girders, which is where web local buckling starts to govern. Returns the tuple
    (λ_p, λ_r).
    """
    root = _slenderness_root(elastic_modulus, yield_strength)
    return (_WEB_PLASTIC_COEFFICIENT * root, _WEB_NONCOMPACT_COEFFICIENT * root)


def classify_flexural_element(
    *,
    slenderness: float,
    plastic_limit: float,
    noncompact_limit: float,
) -> CompactnessClass:
    """Classify a plate element from its slenderness and the two limits.

    Compares an element's ``slenderness`` λ against its ``plastic_limit`` λ_p and the
    ``noncompact_limit`` λ_r (from :func:`flexural_flange_slenderness_limits` or
    :func:`flexural_web_slenderness_limits`): COMPACT when λ ≤ λ_p, NONCOMPACT when λ_p < λ ≤ λ_r,
    and SLENDER when λ > λ_r. The section's overall class is the worse of its flange and web.
    Returns the :class:`CompactnessClass`.
    """
    if slenderness < 0:
        raise ValueError("slenderness must be non-negative")
    if not 0 < plastic_limit < noncompact_limit:
        raise ValueError("require 0 < plastic_limit < noncompact_limit")
    if slenderness <= plastic_limit:
        return CompactnessClass.COMPACT
    if slenderness <= noncompact_limit:
        return CompactnessClass.NONCOMPACT
    return CompactnessClass.SLENDER
