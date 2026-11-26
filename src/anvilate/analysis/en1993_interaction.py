"""T1 Eurocode 3 beam-columns: EN 1993-1-1 §6.3.3, bending and axial compression.

§6.3.1 asks what a column can carry and §6.3.2 what a beam can. A member carrying both at
once is not covered by either: the axial force makes the member more likely to buckle
sideways under its moment, and the moment makes it more likely to buckle under its axial
force. §6.3.3 states that coupling as two inequalities, one per buckling axis:

    N_Ed/(χ_y·N_Rk/γ_M1) + k_yy·M_y,Ed/(χ_LT·M_y,Rk/γ_M1) + k_yz·M_z,Ed/(M_z,Rk/γ_M1) ≤ 1,00
    N_Ed/(χ_z·N_Rk/γ_M1) + k_zy·M_y,Ed/(χ_LT·M_y,Rk/γ_M1) + k_zz·M_z,Ed/(M_z,Rk/γ_M1) ≤ 1,00

(Eqs. 6.61 and 6.62; the source's 1.71 and 1.72.) Everything in them except the four
**interaction factors** comes from the sibling modules — χ_y and χ_z from
:mod:`~anvilate.analysis.en1993_buckling`, χ_LT from the same, N_Rk and M_Rk from the
section and grade. The interaction factors are the whole difficulty, and EN 1993-1-1 gives
**two alternative methods** for them: Annex A (Method 1) and Annex B (Method 2).

**Which method is a declaration, never a default.** The two were developed by different
groups — Method 1 by French and Belgian researchers, Method 2 by Austrian and German ones —
and they do not agree: on the source's own rectangular-hollow-section example Method 2 is
the less conservative of the two. A member checked by an unstated method has been checked
against nothing in particular, so :class:`InteractionMethod` is a required argument.

**Only Method 2 is implemented here.** Method 1's factors run to a page of auxiliary terms
that the source does not reproduce in full, so calling for it refuses and says so rather
than quietly substituting the other method's answer.

**What Method 2 needs, and what it turns on.** Whether the member is *susceptible to
torsional deformation* — roughly, whether lateral-torsional buckling is the relevant mode.
A circular hollow section is not; an unrestrained open I or H section is. The two cases read
different tables (B.1 and B.2), and this is also a declaration: the source gives the
criteria in prose, keyed on restraint conditions that a cross-section alone does not state.

    C_my, C_mLT = 0,60 + 0,4·ψ,  ≥ 0,40        Table B.3, **linear moment diagram only**
    n_y         = N_Ed/(χ_y·N_Rk/γ_M1)         the axial term of the first inequality
    k_yy        = C_my·[1 + (λ̄_y − 0,2)·n_y],  ≤ C_my·(1 + 0,8·n_y)      class 1 and 2
    k_zy        = 1 − (0,1·λ̄_z)/(C_mLT − 0,25)·n_z,  ≥ 1 − 0,1/(C_mLT − 0,25)·n_z

**The bound on k_zy is a floor, not a ceiling,** which is the opposite of k_yy's, and it is
the one that governs on the source's own example: the unbounded expression gives 0,9646 and
the floor 0,9660, so the floor wins. A reading that took it as a ceiling would return
0,9646, be wrong by a sixth of a percent, and look entirely plausible.

**What is deliberately not here**, because the source does not state it and this package does
not ship a clause it has not read:

* **k_yz and k_zz**, so only bending about the major axis is screened. A non-zero M_z,Ed
  refuses rather than being dropped from the inequality, because dropping a term makes a
  member look safer.
* **Classes 3 and 4**, which take different expressions in both tables.
* **k_zy below λ̄_z = 0,4**, where Table B.2 has a separate branch the source never prints.
* **k_zy for a member not susceptible to torsional deformation** in general. The source
  works only the allowance that a rectangular hollow section in compression and uniaxial
  major-axis bending may take k_zy = 0, which is :func:`hollow_section_kzy_allowance`.

**Source, read rather than recalled.** EN 1993-1-1 is copyrighted and is not bundled. The
equations, Table 6.7, the Table B.3 factor and both interaction factors are read from
[*Eurocodes: Background and Applications — Design of Steel Buildings*](https://orbi.uliege.be/bitstream/2268/194798/1/Eurocodes%20Background&applications%20design%20of%20steel%20buildings.pdf),
the European Commission JRC report, §1.3.5.1 and the two worked examples in §1.3.5.2. The
pages were read as images: the text layer turns every χ, λ̄ and ψ into punctuation and loses
the direction of every inequality.

**What the arithmetic is checked against.** Both of the source's worked beam-columns, each
replayed end to end. An IPE 360 column susceptible to torsional deformation, where ψ = 0,0
gives C_my = 0,60 and ψ = 0,5 gives C_mLT = 0,80, k_yy = 0,624 against its cap of 0,658,
k_zy = 0,966, and the two inequalities close at 0,56 and 0,88. And an RHS 200x150x8 **not**
susceptible, where ψ = −0,50 puts C_my exactly on its 0,40 floor, k_yy = 0,53 against a cap
of 0,60, k_zy is taken as zero, and the inequalities close at 0,90 and 0,72. The pair is the
useful part: one member on each table, and one C_m on the floor and one above it.

**One figure in the source does not reproduce, and it is recorded rather than matched.** For
the IPE 360 the report prints k_zy's unbounded value as 0,966 and its floor as 0,947. From
the inputs it prints on the same page those are 0,9646 and 0,9660 — the floor, not the
unbounded value, is the 0,966. The *governing* k_zy is 0,966 either way, which is why the
example's conclusion stands and is still worth anchoring on; the two intermediates are not,
and are not asserted anywhere here.

**The edition** is the 2005 generation with its 2014 amendment, as in the sibling modules.
γ_M1 is a nationally determined parameter and, like every partial factor in this pack, is an
argument with no default.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite

from ..refusal import RefusalError, Remedy
from ..units import Quantity
from .en1993_classification import SectionClass

__all__ = [
    "InteractionMethod",
    "TorsionalSusceptibility",
    "equivalent_uniform_moment_factor",
    "axial_utilisation",
    "interaction_factor_kyy",
    "interaction_factor_kzy",
    "hollow_section_kzy_allowance",
    "beam_column_utilisations",
]

_METHOD_SOURCE = "the design basis, which states which of EN 1993-1-1's two methods applies"
_RESTRAINT_SOURCE = "the member's torsional and lateral restraint conditions"
_DIAGRAM_SOURCE = "the bending moment diagram between the braced sections"
_SECTION_SOURCE = "the section table or the measured cross-section"
_MEMBER_SOURCE = "the member's buckling lengths and the analysis that produced its forces"
_ANNEX_SOURCE = "the National Annex, or EN 1993-1-1's recommended value where it defers"

#: Table B.3's floor on an equivalent uniform moment factor.
_MOMENT_FACTOR_FLOOR = 0.40
#: Table B.3's two coefficients for a linear moment diagram.
_MOMENT_FACTOR_BASE, _MOMENT_FACTOR_SLOPE = 0.60, 0.40
#: The plateau subtracted inside k_yy, the same 0,2 the buckling curves use.
_PLATEAU = 0.2
#: k_yy's cap coefficient, and k_zy's two.
_KYY_CAP_COEFFICIENT = 0.8
_KZY_NUMERATOR = 0.1
_KZY_OFFSET = 0.25
#: Below this λ̄_z, Table B.2 takes a separate branch the source does not print.
_KZY_SLENDERNESS_FLOOR = 0.4
#: The classes whose Table B.1 and B.2 expressions this module carries.
_PLASTIC_CLASSES = (SectionClass.CLASS_1, SectionClass.CLASS_2)


class _En1993InteractionInputError(RefusalError, ValueError):
    """An EN 1993 §6.3.3 input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str) -> _En1993InteractionInputError:
    return _En1993InteractionInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class InteractionMethod(StrEnum):
    """Which of EN 1993-1-1's two alternative sets of interaction factors applies.

    They are alternatives, not refinements of each other, and they disagree. Only
    :attr:`METHOD_2` is implemented; :attr:`METHOD_1` is named so a caller can state it and
    be refused, rather than have the other method's answer returned under its name.
    """

    METHOD_1 = "method 1"
    METHOD_2 = "method 2"


class TorsionalSusceptibility(StrEnum):
    """Whether lateral-torsional buckling is the relevant mode (EN 1993-1-1 §6.3.3).

    Not derivable from the cross-section alone: an open I section restrained torsionally and
    laterally along its length may be taken as not susceptible, and the same section
    unrestrained may not. The restraint conditions are the caller's to state.
    """

    SUSCEPTIBLE = "susceptible"
    NOT_SUSCEPTIBLE = "not susceptible"


def _finite(value: object, name: str, *, source: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _refuse(f"{name} must be a number; got {value!r}", subject=name, source=source)
    number = float(value)
    if not isfinite(number):
        raise _refuse(f"{name} must be finite; got {number}", subject=name, source=source)
    return number


def _method(method: object) -> InteractionMethod:
    """``method`` as Method 2, or a refusal naming what was asked for."""
    if not isinstance(method, InteractionMethod):
        raise _refuse(
            f"method must be an InteractionMethod; got {method!r}",
            subject="method",
            source=_METHOD_SOURCE,
        )
    if method is InteractionMethod.METHOD_1:
        raise _refuse(
            "the interaction factors of EN 1993-1-1 Annex A (Method 1) are not implemented; "
            "this module carries Annex B (Method 2) only. The two are alternatives and they "
            "disagree, so Method 2's factors are not returned under Method 1's name",
            subject="method",
            source=_METHOD_SOURCE,
        )
    return method


def equivalent_uniform_moment_factor(*, moment_ratio: float) -> float:
    """C_m for a **linear** bending moment diagram (EN 1993-1-1 Table B.3).

        C_m = 0,60 + 0,4·ψ,  ≥ 0,40

    ``moment_ratio`` is ψ, the ratio of the end moments taken over the length between the
    sections braced in the relevant direction, signed so that a double-curvature diagram is
    negative. The same expression serves C_my and C_mLT; what differs is the length it is
    read over, which is why they are different numbers on the same member — the source's own
    column has C_my = 0,60 from ψ = 0,0 over one length and C_mLT = 0,80 from ψ = 0,5 over
    another.

    **Linear diagrams only.** Table B.3 gives other rows for a diagram with a transverse
    load, and they are not carried here, so a caller with a parabolic or stepped diagram must
    not reduce it to its end moments and call this: ψ would not describe it.

    The floor of 0,40 is reached exactly on the source's second example, where ψ = −0,50
    gives 0,60 − 0,20 = 0,40.
    """
    psi = _finite(moment_ratio, "moment_ratio", source=_DIAGRAM_SOURCE)
    if not -1.0 <= psi <= 1.0:
        raise _refuse(
            f"moment_ratio is the ratio of the smaller end moment to the larger, so it lies "
            f"in [-1, 1]; got {psi}. A value outside it means the two were divided the other "
            "way up",
            subject="moment_ratio",
            source=_DIAGRAM_SOURCE,
        )
    return max(_MOMENT_FACTOR_BASE + _MOMENT_FACTOR_SLOPE * psi, _MOMENT_FACTOR_FLOOR)


def axial_utilisation(
    *,
    axial_force: Quantity,
    reduction: float,
    characteristic_axial_resistance: Quantity,
    partial_factor_m1: float,
) -> float:
    """N_Ed/(χ·N_Rk/γ_M1): the axial term of one of EN 1993-1-1 §6.3.3's two inequalities.

    It appears three times — as the first term of its own inequality and inside both
    interaction factors — so it is computed once and passed, rather than rebuilt at each use
    where the three could drift apart.

    ``reduction`` is χ_y for the first inequality and χ_z for the second. ``N_Rk`` is
    ``f_y·A`` for a class 1, 2 or 3 section and ``f_y·A_eff`` for a class 4 one
    (EN 1993-1-1 Table 6.7); this takes it as a force rather than computing it, so the
    effective area of a class 4 section is the caller's, as it is everywhere else here.
    """
    for name, value in (
        ("axial_force", axial_force),
        ("characteristic_axial_resistance", characteristic_axial_resistance),
    ):
        if not isinstance(value, Quantity) or not value.has_dimension("[force]"):
            raise _refuse(
                f"{name} must be a [force] quantity; got {value!r}",
                subject=name,
                source=_SECTION_SOURCE if "resistance" in name else _MEMBER_SOURCE,
            )
        if not isfinite(value.magnitude):
            raise _refuse(f"{name} must be finite; got {value}", subject=name,
                          source=_MEMBER_SOURCE)  # fmt: skip
    chi = _finite(reduction, "reduction", source=_MEMBER_SOURCE)
    gamma = _finite(partial_factor_m1, "partial_factor_m1", source=_ANNEX_SOURCE)
    if not 0.0 < chi <= 1.0:
        raise _refuse(
            f"reduction is a buckling reduction factor, so it lies in (0, 1]; got {chi}",
            subject="reduction",
            source=_MEMBER_SOURCE,
        )
    if gamma < 1.0:
        raise _refuse(
            f"partial_factor_m1 must be at least 1; got {gamma}. A factor below 1 raises a "
            "resistance above its characteristic value",
            subject="partial_factor_m1",
            source=_ANNEX_SOURCE,
        )
    applied = axial_force.to("N").magnitude
    if applied < 0:
        raise _refuse(
            f"axial_force is the design compression N_Ed and is positive in compression; got "
            f"{axial_force}. A member in tension is not a §6.3.3 beam-column",
            subject="axial_force",
            source=_MEMBER_SOURCE,
        )
    resistance = characteristic_axial_resistance.to("N").magnitude
    if resistance <= 0:
        raise _refuse(
            f"characteristic_axial_resistance must be positive; got "
            f"{characteristic_axial_resistance}",
            subject="characteristic_axial_resistance",
            source=_SECTION_SOURCE,
        )
    return applied / (chi * resistance / gamma)


def _plastic_class(section_class: object, factor: str) -> SectionClass:
    if not isinstance(section_class, SectionClass):
        raise _refuse(
            f"section_class must be a SectionClass; got {section_class!r}",
            subject="section_class",
            source=_SECTION_SOURCE,
        )
    if section_class not in _PLASTIC_CLASSES:
        raise _refuse(
            f"{factor} is carried here for class 1 and class 2 sections only; got "
            f"{section_class.name.replace('_', ' ').lower()}. Tables B.1 and B.2 give "
            "different expressions for classes 3 and 4, and this module has not read them",
            subject="section_class",
            source=_SECTION_SOURCE,
        )
    return section_class


def interaction_factor_kyy(
    *,
    moment_factor: float,
    slenderness: float,
    axial_term: float,
    section_class: SectionClass,
    method: InteractionMethod,
) -> float:
    """k_yy by Method 2, for a class 1 or 2 section (Tables B.1 and B.2).

        k_yy = C_my·[1 + (λ̄_y − 0,2)·n_y],  but ≤ C_my·(1 + 0,8·n_y)

    Both of EN 1993-1-1's Annex B tables give k_yy this same form for a class 1 or 2
    section, so a member's torsional susceptibility does not change it — it changes k_zy.
    That is why this takes no :class:`TorsionalSusceptibility`, and it was checked on the
    source's two worked examples, one from each table.

    The cap is a **ceiling**, unlike k_zy's bound. It binds when λ̄_y exceeds 1,0, and on
    neither worked example does it: 0,624 against 0,658, and 0,53 against 0,60.

    ``axial_term`` is :func:`axial_utilisation` computed with χ_y.
    """
    _method(method)
    _plastic_class(section_class, "k_yy")
    c_my = _finite(moment_factor, "moment_factor", source=_DIAGRAM_SOURCE)
    lambda_y = _finite(slenderness, "slenderness", source=_MEMBER_SOURCE)
    n_y = _finite(axial_term, "axial_term", source=_MEMBER_SOURCE)
    if c_my < _MOMENT_FACTOR_FLOOR:
        raise _refuse(
            f"moment_factor is an equivalent uniform moment factor and Table B.3 floors it "
            f"at {_MOMENT_FACTOR_FLOOR}; got {c_my}",
            subject="moment_factor",
            source=_DIAGRAM_SOURCE,
        )
    if lambda_y < 0 or n_y < 0:
        raise _refuse(
            f"slenderness and axial_term are both non-negative; got {lambda_y} and {n_y}",
            subject="slenderness and axial_term",
            source=_MEMBER_SOURCE,
        )
    unbounded = c_my * (1.0 + (lambda_y - _PLATEAU) * n_y)
    cap = c_my * (1.0 + _KYY_CAP_COEFFICIENT * n_y)
    return min(unbounded, cap)


def interaction_factor_kzy(
    *,
    moment_factor_lt: float,
    slenderness: float,
    axial_term: float,
    section_class: SectionClass,
    susceptibility: TorsionalSusceptibility,
    method: InteractionMethod,
) -> float:
    """k_zy by Method 2, member **susceptible** to torsion (EN 1993-1-1 Table B.2).

        k_zy = 1 − (0,1·λ̄_z)/(C_mLT − 0,25)·n_z,  but ≥ 1 − 0,1/(C_mLT − 0,25)·n_z

    **The bound is a floor.** It is the larger of the two that governs, which is the reverse
    of k_yy's cap and is easy to get backwards: on the source's worked column the unbounded
    expression gives 0,9646 and the floor 0,9660, so the floor wins by a sixth of a percent
    and a reading that took it as a ceiling would look right.

    The floor is the same expression with λ̄_z removed from the numerator, so the two
    coincide at λ̄_z = 1 and the floor governs whenever λ̄_z > 1 — that is, whenever the
    member is slender about z, which is when k_zy matters.

    ``axial_term`` is :func:`axial_utilisation` computed with χ_z, not χ_y.

    A member that is **not** susceptible reads Table B.1 instead, which this module does not
    carry except for the hollow-section allowance in
    :func:`hollow_section_kzy_allowance` — so it refuses here rather than returning the
    susceptible member's factor, which would be the conservative answer under one reading and
    simply the wrong table under another.
    """
    _method(method)
    _plastic_class(section_class, "k_zy")
    if not isinstance(susceptibility, TorsionalSusceptibility):
        raise _refuse(
            f"susceptibility must be a TorsionalSusceptibility; got {susceptibility!r}",
            subject="susceptibility",
            source=_RESTRAINT_SOURCE,
        )
    if susceptibility is TorsionalSusceptibility.NOT_SUSCEPTIBLE:
        raise _refuse(
            "this is EN 1993-1-1 Table B.2's k_zy, for a member susceptible to torsional "
            "deformation; a member that is not susceptible reads Table B.1, which is not "
            "carried here. A rectangular hollow section in compression and uniaxial "
            "major-axis bending takes hollow_section_kzy_allowance instead",
            subject="susceptibility",
            source=_RESTRAINT_SOURCE,
        )
    c_mlt = _finite(moment_factor_lt, "moment_factor_lt", source=_DIAGRAM_SOURCE)
    lambda_z = _finite(slenderness, "slenderness", source=_MEMBER_SOURCE)
    n_z = _finite(axial_term, "axial_term", source=_MEMBER_SOURCE)
    if c_mlt < _MOMENT_FACTOR_FLOOR:
        raise _refuse(
            f"moment_factor_lt is an equivalent uniform moment factor and Table B.3 floors "
            f"it at {_MOMENT_FACTOR_FLOOR}; got {c_mlt}",
            subject="moment_factor_lt",
            source=_DIAGRAM_SOURCE,
        )
    if n_z < 0:
        raise _refuse(
            f"axial_term is non-negative; got {n_z}", subject="axial_term",
            source=_MEMBER_SOURCE,
        )  # fmt: skip
    if lambda_z < _KZY_SLENDERNESS_FLOOR:
        raise _refuse(
            f"slenderness is {lambda_z}, below {_KZY_SLENDERNESS_FLOOR}, where Table B.2 "
            "takes a separate branch for k_zy. The source this module is read from does not "
            "print that branch, so it is not carried and is not guessed at",
            subject="slenderness",
            source=_MEMBER_SOURCE,
        )
    divisor = c_mlt - _KZY_OFFSET
    unbounded = 1.0 - (_KZY_NUMERATOR * lambda_z) / divisor * n_z
    floor = 1.0 - _KZY_NUMERATOR / divisor * n_z
    return max(unbounded, floor)


def hollow_section_kzy_allowance(
    *,
    susceptibility: TorsionalSusceptibility,
    method: InteractionMethod,
) -> float:
    """k_zy = 0 for a rectangular hollow section (EN 1993-1-1 Annex B, Method 2).

    Method 2's allowance, stated in the source and used in its second worked example: a
    rectangular hollow section carrying compression and bending about y only may take
    k_zy = 0, which drops the moment term from the second inequality entirely and leaves it
    a pure flexural-buckling check about z.

    It is a function rather than the bare constant so that the two conditions it rests on —
    Method 2, and a member not susceptible to torsional deformation — are *checked* rather
    than left to a comment next to a zero. A zero returned under the wrong conditions deletes
    a term from a safety check.

    Whether the section really is a rectangular hollow one, and the bending really uniaxial,
    the caller states by choosing this function: neither is derivable from the arguments, and
    inventing a section-shape argument to re-assert what the call already says would not make
    it any more checked.
    """
    _method(method)
    if susceptibility is not TorsionalSusceptibility.NOT_SUSCEPTIBLE:
        raise _refuse(
            "this allowance is for a member not susceptible to torsional deformation; a "
            "susceptible member's k_zy is interaction_factor_kzy and is not zero",
            subject="susceptibility",
            source=_RESTRAINT_SOURCE,
        )
    return 0.0


def beam_column_utilisations(
    *,
    axial_term_y: float,
    axial_term_z: float,
    major_moment: Quantity,
    characteristic_major_moment: Quantity,
    lateral_torsional_reduction: float,
    partial_factor_m1: float,
    factor_kyy: float,
    factor_kzy: float,
    minor_moment: Quantity | None = None,
) -> tuple[float, float]:
    """Both of §6.3.3's inequalities (EN 1993-1-1 Eqs. 6.61 and 6.62), as left-hand sides.

    Returns ``(about_y, about_z)``; the member is verified when both are at most 1,00. They
    are returned rather than reduced to a verdict because they are different questions — a
    member can be governed about either axis — and because the margin on each is what a
    designer changes the section for.

    ``axial_term_y`` and ``axial_term_z`` are :func:`axial_utilisation` with χ_y and χ_z.
    ``lateral_torsional_reduction`` is χ_LT, and is 1,0 for a member not susceptible to
    torsional deformation — which is the source's own treatment of its hollow section.

    **A minor-axis moment refuses.** k_yz and k_zz are not carried, so there is no honest
    coefficient to put on an M_z term. Silently omitting it would subtract a positive
    quantity from both left-hand sides and report a member as verified that has not been.
    """
    for name, value in (
        ("major_moment", major_moment),
        ("characteristic_major_moment", characteristic_major_moment),
    ):
        if not isinstance(value, Quantity) or not value.has_dimension("[force] * [length]"):
            raise _refuse(
                f"{name} must be a moment quantity; got {value!r}",
                subject=name,
                source=_MEMBER_SOURCE,
            )
        if not isfinite(value.magnitude):
            raise _refuse(f"{name} must be finite; got {value}", subject=name,
                          source=_MEMBER_SOURCE)  # fmt: skip
    if minor_moment is not None and (
        not isinstance(minor_moment, Quantity) or minor_moment.to("N*m").magnitude != 0.0
    ):
        raise _refuse(
            f"a minor-axis moment of {minor_moment} cannot be screened: the interaction "
            "factors k_yz and k_zz are not carried here, so there is no coefficient for its "
            "term. Omitting the term would make both inequalities smaller and report the "
            "member as verified on a load case it was not checked for",
            subject="minor_moment",
            source=_MEMBER_SOURCE,
        )
    n_y = _finite(axial_term_y, "axial_term_y", source=_MEMBER_SOURCE)
    n_z = _finite(axial_term_z, "axial_term_z", source=_MEMBER_SOURCE)
    chi_lt = _finite(lateral_torsional_reduction, "lateral_torsional_reduction",
                     source=_MEMBER_SOURCE)  # fmt: skip
    gamma = _finite(partial_factor_m1, "partial_factor_m1", source=_ANNEX_SOURCE)
    k_yy = _finite(factor_kyy, "factor_kyy", source=_MEMBER_SOURCE)
    k_zy = _finite(factor_kzy, "factor_kzy", source=_MEMBER_SOURCE)
    if not 0.0 < chi_lt <= 1.0:
        raise _refuse(
            f"lateral_torsional_reduction is a reduction factor, so it lies in (0, 1]; got "
            f"{chi_lt}. A member not susceptible to torsional deformation takes 1,0",
            subject="lateral_torsional_reduction",
            source=_MEMBER_SOURCE,
        )
    if gamma < 1.0:
        raise _refuse(
            f"partial_factor_m1 must be at least 1; got {gamma}",
            subject="partial_factor_m1",
            source=_ANNEX_SOURCE,
        )
    for name, value in (("factor_kyy", k_yy), ("factor_kzy", k_zy), ("axial_term_y", n_y),
                        ("axial_term_z", n_z)):  # fmt: skip
        if value < 0:
            raise _refuse(
                f"{name} is non-negative; got {value}", subject=name, source=_MEMBER_SOURCE
            )
    applied = major_moment.to("N*m").magnitude
    resistance = characteristic_major_moment.to("N*m").magnitude
    if resistance <= 0:
        raise _refuse(
            f"characteristic_major_moment must be positive; got {characteristic_major_moment}",
            subject="characteristic_major_moment",
            source=_SECTION_SOURCE,
        )
    moment_term = abs(applied) / (chi_lt * resistance / gamma)
    return (n_y + k_yy * moment_term, n_z + k_zy * moment_term)
