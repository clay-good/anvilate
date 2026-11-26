"""T1 Eurocode 3 member buckling: EN 1993-1-1 §6.3.1 and §6.3.2, closed-form.

Where §6.2 asks what a cross-section can carry, §6.3 asks what the *member* can: a column
long enough to buckle never reaches N_c,Rd, and a beam that can sway sideways never reaches
M_c,Rd. Both are the same construction — a non-dimensional slenderness, a curve chosen for
the section, and a reduction factor off that curve.

**Flexural buckling (§6.3.1).**

    N_b,Rd = χ·A·f_y/γ_M1                                             (6.3.1.1, Eq. 1.35)
    χ      = 1/(Φ + √(Φ² − λ̄²)),  χ ≤ 1,00                            (6.3.1.2, Eq. 1.37)
    Φ      = 0,5[1 + α(λ̄ − 0,2) + λ̄²]
    λ̄      = √(A·f_y/N_cr) = (L_cr/i)/λ₁                               (6.3.1.2, Eq. 1.38)
    λ₁     = π·√(E/f_y) = 93,9ε

A class 4 section takes A_eff in place of A in both the resistance and the slenderness
(Eqs. 1.36 and 1.39), so pass A_eff as ``area``; the slenderness then carries the √(A_eff/A)
the clause writes, because √(A_eff·f_y/N_cr) is the same thing.

The **imperfection factor** α is what distinguishes the five European design buckling
curves: 0,13 / 0,21 / 0,34 / 0,49 / 0,76 for a₀, a, b, c and d. Which curve a member takes
depends on its section geometry, steel grade, fabrication and buckling plane, and that
selection table is **not** bundled — it is the standard's Table 6.2 and the caller reads it.
What is bundled is the α each curve carries, which the source prints as a list rather than a
table.

**Lateral-torsional buckling (§6.3.2).** The same shape with its own slenderness:

    M_b,Rd  = χ_LT·W_y·f_y/γ_M1
    λ̄_LT    = √(W_y·f_y/M_cr)
    general method (§6.3.2.2)     χ_LT = 1/(Φ_LT + √(Φ_LT² − λ̄_LT²)),  ≤ 1,00
                                  Φ_LT = 0,5[1 + α_LT(λ̄_LT − 0,2) + λ̄_LT²]
    rolled sections (§6.3.2.3)    χ_LT = 1/(Φ_LT + √(Φ_LT² − β·λ̄_LT²))
                                  ≤ 1,00 **and** ≤ 1/λ̄_LT²
                                  Φ_LT = 0,5[1 + α_LT(λ̄_LT − λ̄_LT,0) + β·λ̄_LT²]

The general method's Φ_LT is the same expression as the column's, so
:func:`buckling_reduction_factor` serves both and there is no near-duplicate beside it. What
differs is the **curve**, and the two methods choose differently from the same geometry —
:func:`lateral_torsional_curve` gives both tables, and a rolled I with h/b ≤ 2 is curve *a*
under the general method and curve *b* under the alternative one.

``M_cr``, the elastic critical moment, is **not** computed here. EN 1993-1-1 does not give
it: it depends on the support conditions, the moment diagram and where the load is applied
relative to the shear centre, through C₁, C₂ and k factors from the literature. It is a
declared input, and the source's own worked examples obtain it the same way.

**N_cr is not computed here either.** :func:`~anvilate.analysis.column.euler_buckling_load`
is already π²EI/(KL)², and a second copy of it would be a second place to be wrong.

**Source, read rather than recalled.** EN 1993-1-1 is copyrighted and is not bundled. The
equations, the α values and both curve-selection tables are read from
[*Eurocodes: Background and Applications — Design of Steel Buildings*](https://orbi.uliege.be/bitstream/2268/194798/1/Eurocodes%20Background&applications%20design%20of%20steel%20buildings.pdf),
the European Commission JRC report: §1.3.3.1 for the column, §1.3.4.1 and its Tables 1.22
and 1.23 for the beam. The pages were read as images, because the text layer drops every χ,
Φ, λ̄ and √ and turns `h/b ≤ 2` into `h b2`, which is the inequality and its direction gone.

**What the arithmetic is checked against.** Three worked results from the same report, all
replayed: an HEB 340 column on curve c at λ̄ = 0,75 giving Φ = 0,92, χ = 0,69 and
N_b,Rd = 4186,2 kN; and an IPE 400 beam worked **twice** at λ̄_LT = 1,68 and λ̄_LT = 0,51 on
curve b, giving Φ_LT = 2,16 and 0,68, χ_LT = 0,28 and 0,89, and M_b,Rd = 129,9 kNm and
412,9 kNm. The pair is the useful part: the same section and curve at two slendernesses
pins the shape of the curve and not just one point on it.

**The edition** is the 2005 generation with its 2014 amendment, as in the sibling modules.
λ̄_LT,0 and β are nationally determined parameters — the source gives 0,4 as a maximum and
0,75 as a minimum recommended value — and like every partial factor here they are arguments
with no default.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite, pi, sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "EuropeanBucklingCurve",
    "curve_imperfection_factor",
    "reference_slenderness",
    "non_dimensional_slenderness",
    "buckling_reduction_factor",
    "flexural_buckling_resistance",
    "buckling_may_be_neglected",
    "lateral_torsional_curve",
    "lateral_torsional_slenderness",
    "lateral_torsional_reduction_rolled",
    "lateral_torsional_buckling_resistance",
]

_STEEL_SOURCE = "the steel grade's product standard, at the element's thickness"
_SECTION_SOURCE = "the section table or the measured cross-section"
_MEMBER_SOURCE = "the member's buckling length and support conditions"
_ANNEX_SOURCE = "the National Annex, or EN 1993-1-1's recommended value where it defers"
_CURVE_SOURCE = "EN 1993-1-1 Table 6.2, for this section, grade and buckling plane"

#: The plateau of every curve: below this slenderness buckling is not reduced for
#: (clause 6.3.1.2(4)), and it is also the 0,2 subtracted inside Φ.
_PLATEAU = 0.2
#: Clause 6.3.1.2(4)'s other escape: a member whose axial force is this small a share of
#: its critical load need not be checked for buckling.
_NEGLIGIBLE_LOAD_SHARE = 0.04
#: Table 1.22/1.23's one geometric limit, h/b.
_HEIGHT_TO_WIDTH_LIMIT = 2.0


class _En1993BucklingInputError(RefusalError, ValueError):
    """An EN 1993 buckling input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str) -> _En1993BucklingInputError:
    return _En1993BucklingInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _quantity(value: object, dimension: str, name: str, *, source: str) -> float:
    """``value`` as a finite, positive magnitude of ``dimension``, in its own unit."""
    if not isinstance(value, Quantity):
        raise _refuse(
            f"{name} must be a {dimension} quantity; got {value!r}", subject=name, source=source
        )
    if not value.has_dimension(dimension):
        raise _refuse(
            f"{name} must be a {dimension} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=source,
        )
    if not isfinite(value.magnitude):
        raise _refuse(f"{name} must be finite; got {value}", subject=name, source=source)
    if value.magnitude <= 0:
        raise _refuse(f"{name} must be positive; got {value}", subject=name, source=source)
    return value.magnitude


def _slenderness(value: float, name: str = "slenderness") -> float:
    """A non-dimensional slenderness: finite and not negative."""
    require_finite(value, name=name)
    if value < 0:
        raise _refuse(
            f"{name} is √(A·f_y/N_cr) and cannot be negative; got {value}",
            subject=name,
            source=_MEMBER_SOURCE,
        )
    return float(value)


def _factor(value: float, name: str) -> float:
    """A partial factor: finite and at least 1, since it divides a resistance."""
    require_finite(value, name=name)
    if value < 1.0:
        raise _refuse(
            f"{name} divides a resistance and is at least 1; got {value}",
            subject=name,
            source=_ANNEX_SOURCE,
        )
    return float(value)


class EuropeanBucklingCurve(StrEnum):
    """One of EN 1993-1-1's five European design buckling curves.

    They differ only in their imperfection factor α, which is what
    :func:`curve_imperfection_factor` returns: a₀ is the straightest column the research
    programme found and d the most imperfect, and the spread between them is large — at a
    slenderness of 1,0 curve a₀ keeps 0,725 of the squash load against curve d's 0,467, which
    is **55% more**. Picking the curve is not a detail of the paperwork.
    """

    A0 = "a0"
    A = "a"
    B = "b"
    C = "c"
    D = "d"


#: The imperfection factors the source prints for a₀, a, b, c and d. These are bundled
#: because the source states them as a list in running text; the TABLE that says which curve
#: a member takes (Table 6.2) is not bundled and is the caller's to read.
_IMPERFECTION_FACTORS = {
    EuropeanBucklingCurve.A0: 0.13,
    EuropeanBucklingCurve.A: 0.21,
    EuropeanBucklingCurve.B: 0.34,
    EuropeanBucklingCurve.C: 0.49,
    EuropeanBucklingCurve.D: 0.76,
}


def curve_imperfection_factor(curve: EuropeanBucklingCurve) -> float:
    """The imperfection factor α of an EN 1993-1-1 buckling curve (clause 6.3.1.2(2))."""
    if not isinstance(curve, EuropeanBucklingCurve):
        raise _refuse(
            f"curve must be a EuropeanBucklingCurve; got {curve!r}",
            subject="curve",
            source=_CURVE_SOURCE,
        )
    return _IMPERFECTION_FACTORS[curve]


def reference_slenderness(*, elastic_modulus: Quantity, yield_strength: Quantity) -> float:
    """EN 1993-1-1's λ₁ = π·√(E/f_y), the slenderness the member's is divided by.

    The source also gives it as 93,9ε, and the two agree: at f_y = 235 N/mm² with
    E = 210 000 N/mm², π·√(210000/235) is 93,91. That identity is a test, because λ₁ and ε
    are the two places the same 235 appears and an error in either reads as a plausible
    slenderness.
    """
    e = _quantity(elastic_modulus, "[pressure]", "elastic_modulus", source=_STEEL_SOURCE)
    fy = _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    del e, fy
    return pi * sqrt(elastic_modulus.to("MPa").magnitude / yield_strength.to("MPa").magnitude)


def non_dimensional_slenderness(
    *,
    area: Quantity,
    yield_strength: Quantity,
    critical_load: Quantity,
) -> float:
    """λ̄ = √(A·f_y/N_cr) (EN 1993-1-1 clause 6.3.1.2(1), Eq. 1.38).

    The squash load over the buckling load, rooted: λ̄ = 1 is the member whose two failure
    loads coincide. ``critical_load`` N_cr comes from
    :func:`~anvilate.analysis.column.euler_buckling_load` for flexural buckling, or from
    whatever mode governs; this does not compute it, and a member with a torsional or
    flexural-torsional mode lower than its flexural one must pass that mode's N_cr here
    (clause 6.3.1.4).

    For a class 4 section pass A_eff as ``area``, which is Eq. 1.39 — √(A_eff·f_y/N_cr) is
    the same number as (L_cr/i)·√(A_eff/A)/λ₁.
    """
    _quantity(area, "[area]", "area", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    _quantity(critical_load, "[force]", "critical_load", source=_MEMBER_SOURCE)
    squash = area.to("mm^2").magnitude * yield_strength.to("MPa").magnitude
    return sqrt(squash / critical_load.to("N").magnitude)


def buckling_reduction_factor(
    *,
    slenderness: float,
    curve: EuropeanBucklingCurve,
) -> float:
    """The reduction factor χ (EN 1993-1-1 clause 6.3.1.2(1), Eq. 1.37).

    ``χ = 1/(Φ + √(Φ² − λ̄²))`` with ``Φ = 0,5[1 + α(λ̄ − 0,2) + λ̄²]``, capped at 1,00 — the
    cap being the clause's own ``but``, which binds for every λ̄ below the 0,2 plateau where
    the expression exceeds 1.

    **This serves the lateral-torsional general method of §6.3.2.2 as well**, whose Φ_LT is
    the same expression with α_LT in place of α. What differs between the two is which curve
    the section takes, not the arithmetic, so there is one function here and
    :func:`lateral_torsional_curve` for the selection. The *alternative* method of §6.3.2.3
    is a different expression and has its own function.

    Returns χ in (0, 1].
    """
    lam = _slenderness(slenderness)
    alpha = curve_imperfection_factor(curve)
    phi = 0.5 * (1.0 + alpha * (lam - _PLATEAU) + lam * lam)
    discriminant = phi * phi - lam * lam
    if discriminant < 0:
        # Φ² − λ̄² is non-negative for every λ̄ ≥ 0 and every α the curves use; a negative one
        # would mean the inputs are not a curve this clause describes, and taking its root
        # would be a complex number silently cast to a float.
        raise _refuse(
            f"Φ² − λ̄² came out {discriminant:.4g} for λ̄ = {lam:.4g} on curve {curve.value}, "
            f"so these are not a slenderness and a curve Eq. (1.37) describes",
            subject="slenderness and curve",
            source=_MEMBER_SOURCE,
        )
    return min(1.0 / (phi + sqrt(discriminant)), 1.0)


def flexural_buckling_resistance(
    *,
    area: Quantity,
    yield_strength: Quantity,
    partial_factor_m1: float,
    slenderness: float,
    curve: EuropeanBucklingCurve,
) -> Quantity:
    """N_b,Rd = χ·A·f_y/γ_M1 (EN 1993-1-1 clause 6.3.1.1(3), Eq. 1.35).

    Note the partial factor: buckling resistances take **γ_M1**, not the γ_M0 of §6.2's
    cross-section resistances. They are separate nationally determined parameters and a
    National Annex may set them apart, so passing one where the other belongs is a quiet
    error — which is why neither has a default anywhere in this pack.

    For a class 4 section pass A_eff as ``area`` (Eq. 1.36), and derive ``slenderness`` from
    the same A_eff.
    """
    _quantity(area, "[area]", "area", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    m1 = _factor(partial_factor_m1, "partial_factor_m1")
    chi = buckling_reduction_factor(slenderness=slenderness, curve=curve)
    return Quantity(
        magnitude=chi * area.to("mm^2").magnitude * yield_strength.to("MPa").magnitude / m1,
        unit="N",
    )


def buckling_may_be_neglected(
    *,
    slenderness: float,
    axial_force: Quantity | None = None,
    critical_load: Quantity | None = None,
) -> bool:
    """Whether EN 1993-1-1 clause 6.3.1.2(4) lets buckling be left out altogether.

    True when ``λ̄ ≤ 0,2`` **or** ``N_Ed/N_cr ≤ 0,04``; the clause gives two escapes and
    either one is enough. The second needs both ``axial_force`` and ``critical_load``, and
    they are declared together or not at all — given one without the other this refuses
    rather than silently testing only the slenderness, because a caller who meant to use the
    load escape and got the slenderness one would read False as "the clause requires the
    check" when it may not.

    A member this returns True for is designed on its cross-section resistance alone.
    """
    lam = _slenderness(slenderness)
    if lam <= _PLATEAU:
        return True
    declared = (axial_force, critical_load)
    if all(value is None for value in declared):
        return False
    if any(value is None for value in declared):
        raise _refuse(
            "axial_force and critical_load are declared together or not at all: clause "
            "6.3.1.2(4)'s second escape is N_Ed/N_cr <= 0,04 and needs both",
            subject="axial_force and critical_load",
            source=_MEMBER_SOURCE,
        )
    assert axial_force is not None and critical_load is not None  # narrowed above
    _quantity(axial_force, "[force]", "axial_force", source=_MEMBER_SOURCE)
    _quantity(critical_load, "[force]", "critical_load", source=_MEMBER_SOURCE)
    share = axial_force.to("N").magnitude / critical_load.to("N").magnitude
    return share <= _NEGLIGIBLE_LOAD_SHARE


def lateral_torsional_curve(
    *,
    height: Quantity,
    width: Quantity,
    rolled: bool,
    alternative_method: bool = False,
) -> EuropeanBucklingCurve:
    """The lateral-torsional buckling curve (EN 1993-1-1 §6.3.2, Tables 6.4 and 6.5).

    One geometric limit decides it, h/b against 2, and the two methods read the same
    geometry differently:

    | section | h/b | general (§6.3.2.2) | alternative (§6.3.2.3) |
    | --- | --- | --- | --- |
    | rolled I or H | ≤ 2 | a | b |
    | rolled I or H | > 2 | b | c |
    | welded I or H | ≤ 2 | c | c |
    | welded I or H | > 2 | d | d |

    So a rolled I with h/b ≤ 2 is curve *a* under the general method and curve *b* under
    the alternative — the alternative method is not simply the general one rearranged, and
    which method a design uses has to be declared rather than inferred.

    The general method's table has a fifth row, *other sections* → curve d, which this does
    not cover: ``height`` and ``width`` are an I or H section's, and a channel or an angle
    is not classified by its h/b. Pass ``EuropeanBucklingCurve.D`` directly for those.
    """
    h = _quantity(height, "[length]", "height", source=_SECTION_SOURCE)
    b = _quantity(width, "[length]", "width", source=_SECTION_SOURCE)
    del h, b
    if not isinstance(rolled, bool):
        raise _refuse(
            f"rolled is True for a rolled section and False for a welded one; got {rolled!r}. "
            f"The two take different curves at the same h/b",
            subject="rolled",
            source=_SECTION_SOURCE,
        )
    if not isinstance(alternative_method, bool):
        raise _refuse(
            f"alternative_method is True for clause 6.3.2.3 and False for 6.3.2.2; got "
            f"{alternative_method!r}",
            subject="alternative_method",
            source=_SECTION_SOURCE,
        )
    ratio = height.to("mm").magnitude / width.to("mm").magnitude
    stocky = ratio <= _HEIGHT_TO_WIDTH_LIMIT
    if rolled:
        if alternative_method:
            return EuropeanBucklingCurve.B if stocky else EuropeanBucklingCurve.C
        return EuropeanBucklingCurve.A if stocky else EuropeanBucklingCurve.B
    return EuropeanBucklingCurve.C if stocky else EuropeanBucklingCurve.D


def lateral_torsional_slenderness(
    *,
    section_modulus: Quantity,
    yield_strength: Quantity,
    critical_moment: Quantity,
) -> float:
    """λ̄_LT = √(W_y·f_y/M_cr) (EN 1993-1-1 clause 6.3.2.2(1)).

    The same construction as the column's λ̄, with the section's own moment resistance over
    the elastic critical moment. ``section_modulus`` W_y is the one the class calls for —
    W_pl,y for a class 1 or 2 section, W_el,y for a class 3 one — which is
    :func:`~anvilate.analysis.en1993_resistance.bending_resistance`'s rule applied here too.

    ``critical_moment`` M_cr is declared. EN 1993-1-1 does not give it: it depends on the
    support conditions, the moment diagram and where the load acts relative to the shear
    centre, through C₁, C₂ and k factors from the literature.
    """
    _quantity(section_modulus, "[volume]", "section_modulus", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    _quantity(critical_moment, "[energy]", "critical_moment", source=_MEMBER_SOURCE)
    resistance_nmm = section_modulus.to("mm^3").magnitude * yield_strength.to("MPa").magnitude
    return sqrt(resistance_nmm / critical_moment.to("N*mm").magnitude)


def lateral_torsional_reduction_rolled(
    *,
    slenderness: float,
    curve: EuropeanBucklingCurve,
    slenderness_limit: float,
    beta: float,
) -> float:
    """χ_LT by the rolled-section method of EN 1993-1-1 §6.3.2.3 (Eq. 1.58).

    ``χ_LT = 1/(Φ_LT + √(Φ_LT² − β·λ̄_LT²))`` with
    ``Φ_LT = 0,5[1 + α_LT(λ̄_LT − λ̄_LT,0) + β·λ̄_LT²]``, held to **two** caps: 1,00 and
    1/λ̄_LT². The second is the one that distinguishes this method and is easy to drop — it
    binds above λ̄_LT = 1 and is what keeps the alternative method from being more generous
    than the general one at high slenderness.

    ``slenderness_limit`` λ̄_LT,0 and ``beta`` are nationally determined parameters. The
    source gives 0,4 as the **maximum** recommended λ̄_LT,0 and 0,75 as the **minimum**
    recommended β; both are arguments with no default here, like every other NDP in this
    pack, and the recommended values are stated rather than applied.

    Below λ̄_LT,0 this returns 1,0: Φ_LT's first term then dominates and the caps bind, which
    is the plateau the method is built around.
    """
    lam = _slenderness(slenderness, "slenderness")
    alpha = curve_imperfection_factor(curve)
    require_finite(slenderness_limit, name="slenderness_limit")
    require_finite(beta, name="beta")
    if slenderness_limit < 0:
        raise _refuse(
            f"slenderness_limit is a slenderness and cannot be negative; got {slenderness_limit}",
            subject="slenderness_limit",
            source=_ANNEX_SOURCE,
        )
    if beta <= 0:
        raise _refuse(
            f"beta must be positive; got {beta}. The source's recommended minimum is 0,75",
            subject="beta",
            source=_ANNEX_SOURCE,
        )
    phi = 0.5 * (1.0 + alpha * (lam - slenderness_limit) + beta * lam * lam)
    discriminant = phi * phi - beta * lam * lam
    if discriminant < 0:
        raise _refuse(
            f"Φ_LT² − β·λ̄_LT² came out {discriminant:.4g}, so these are not a slenderness, "
            f"a curve and a β that Eq. (1.58) describes",
            subject="slenderness, curve and beta",
            source=_MEMBER_SOURCE,
        )
    chi = 1.0 / (phi + sqrt(discriminant))
    caps = [1.0]
    if lam > 0:
        caps.append(1.0 / (lam * lam))
    return min(chi, *caps)


def lateral_torsional_buckling_resistance(
    *,
    section_modulus: Quantity,
    yield_strength: Quantity,
    partial_factor_m1: float,
    reduction: float,
) -> Quantity:
    """M_b,Rd = χ_LT·W_y·f_y/γ_M1 (EN 1993-1-1 clause 6.3.2.1(3)).

    ``reduction`` is χ_LT, from :func:`buckling_reduction_factor` under the general method or
    :func:`lateral_torsional_reduction_rolled` under the alternative one. It is taken rather
    than computed here so that the method used is a decision the caller made and can be read
    back out of their code, not one buried in a flag.

    Like the column's, this takes **γ_M1**.
    """
    _quantity(section_modulus, "[volume]", "section_modulus", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    m1 = _factor(partial_factor_m1, "partial_factor_m1")
    require_finite(reduction, name="reduction")
    if not 0.0 < reduction <= 1.0:
        raise _refuse(
            f"reduction is χ_LT and lies in (0, 1]; got {reduction}",
            subject="reduction",
            source=_MEMBER_SOURCE,
        )
    return Quantity(
        magnitude=reduction
        * section_modulus.to("mm^3").magnitude
        * yield_strength.to("MPa").magnitude
        / m1,
        unit="N*mm",
    )
