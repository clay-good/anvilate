"""T1 analytical aluminum member checks (Aluminum Design Manual, closed-form).

Aluminum structures — ladders, walkways, marine superstructures, curtain walls,
light poles — are designed to the Aluminum Design Manual (ADM), which handles a
buckling limit state differently from steel. Instead of a single smooth column
curve, the ADM fits each *buckling* strength (column flexural, beam lateral-
torsional, and thin-element local buckling all share the form) with a straight
inelastic line that meets the Euler elastic curve at a slenderness C:

    F = B − D·λ            for λ ≤ C   (inelastic)
    F = π²·E / λ²          for λ > C   (elastic),

where the *buckling constants* B (the intercept, a stress), D (the slope, a
stress), and C (the intersection slenderness) come from the ADM tables for the
alloy-temper and the buckling mode — supplied by the caller the same way a
material allowable is, so this module needs no built-in alloy database. Aluminum's
low modulus (about a third of steel's) makes these members buckling-governed far
sooner than a steel one of the same slenderness. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "aluminum_buckling_stress",
    "aluminum_tension_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def aluminum_buckling_stress(
    *,
    slenderness: float,
    intercept: Quantity,
    slope: Quantity,
    intersection_slenderness: float,
    elastic_modulus: Quantity,
) -> Quantity:
    """The Aluminum Design Manual buckling stress F from its straight-line/Euler curve.

    The ADM's unified buckling form, used for a column (flexural buckling), a beam
    (lateral-torsional buckling), or a thin element (local buckling) alike — only the
    constants change. Below the intersection slenderness the strength falls on the inelastic
    straight line F = B − D·λ; above it, it follows the Euler elastic curve F = π²·E/λ².
    ``slenderness`` λ is the governing slenderness (k·L/r for a column, or the element b/t
    for local buckling), ``intercept`` B and ``slope`` D the ADM buckling constants for the
    alloy-temper and mode (both stresses, from the ADM tables), ``intersection_slenderness``
    C the slenderness where the two curves meet, and ``elastic_modulus`` E (≈ 69 GPa for
    aluminum). The result is the buckling stress alone — compare it against the yield/squash
    limit F_cy for a very stocky member, which governs separately. Returns F in MPa.
    """
    _require(intercept, "[pressure]", "intercept")
    _require(slope, "[pressure]", "slope")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    b = intercept.to("MPa").magnitude
    d = slope.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if slenderness <= 0:
        raise ValueError(f"slenderness must be positive; got {slenderness}")
    if intersection_slenderness <= 0:
        raise ValueError(
            f"intersection_slenderness must be positive; got {intersection_slenderness}"
        )
    if b <= 0 or d <= 0 or e <= 0:
        raise ValueError("intercept, slope, and elastic_modulus must be positive")
    if slenderness <= intersection_slenderness:
        stress = b - d * slenderness
        if stress <= 0:
            raise ValueError(
                "the inelastic line has gone non-positive; the slenderness exceeds the "
                "constants' valid range (check that it is below the intersection)"
            )
    else:
        stress = pi**2 * e / slenderness**2
    return Quantity(magnitude=stress, unit="MPa")


def aluminum_tension_stress(
    *,
    yield_strength: Quantity,
    ultimate_strength: Quantity,
    tension_coefficient: float = 1.0,
) -> Quantity:
    """The Aluminum Design Manual nominal tensile stress — the lesser of yield and rupture.

    An aluminum tension member is limited by whichever gives less: yielding on the gross
    section at F_ty, or rupture on the net section at F_tu/k_t. The ADM tension coefficient
    k_t (Table A.3.3, ≈ 1.0 for most tempers, up to ~1.25 for a few) derates the rupture
    strength for the alloy's notch sensitivity. ``yield_strength`` F_ty, ``ultimate_strength``
    F_tu, and ``tension_coefficient`` k_t. Because aluminum's ultimate is often only a little
    above its yield, a k_t above 1 can make rupture govern where it never would in steel.
    Returns the nominal tensile stress F = min(F_ty, F_tu/k_t) in MPa (multiply by the net or
    gross area and the resistance factor for the member strength).
    """
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(ultimate_strength, "[pressure]", "ultimate_strength")
    fty = yield_strength.to("MPa").magnitude
    ftu = ultimate_strength.to("MPa").magnitude
    if fty <= 0 or ftu <= 0:
        raise ValueError("yield_strength and ultimate_strength must be positive")
    if tension_coefficient < 1.0:
        raise ValueError(f"tension_coefficient must be at least 1.0; got {tension_coefficient}")
    return Quantity(magnitude=min(fty, ftu / tension_coefficient), unit="MPa")
