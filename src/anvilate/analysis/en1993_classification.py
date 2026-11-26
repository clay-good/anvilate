"""T1 Eurocode 3 cross-section classification: EN 1993-1-1 §5.5 and Table 5.2.

Before any resistance of a steel member can be found, its plate elements have to be
classified, because the class decides which resistance applies: a **class 1** section forms
a plastic hinge with the rotation capacity plastic analysis needs, a **class 2** one
develops its plastic moment with limited rotation, a **class 3** one reaches yield in the
extreme compression fibre elastically, and a **class 4** one buckles locally before yield
and is designed on an effective cross-section (clause 5.5.2(1)).

The test is a width-to-thickness ratio c/t against a limit that scales with

    ε = √(235/f_y)       f_y in N/mm²

so a stronger steel has tighter limits — an element that is class 1 in S235 can be class 3
in S460. Table 5.2's limits are in three groups, and which group applies is a question
about the element, not about the section: an **internal** compression part is supported on
both edges (an I-section's web, either wall of a box), an **outstand flange** is supported
on one (an I-section's flange, a channel's), and angles and tubular sections have their own
sheet. A section is classified by the **highest, least favourable class of its compressed
parts** (clause 5.5.2(6)), and one that fails even the class 3 limits is class 4
(clause 5.5.2(8)).

The limits this module applies, exactly as the table states them:

| Class | Internal, bending | Internal, compression | Outstand, compression | CHS |
| --- | --- | --- | --- | --- |
| 1 | c/t ≤ 72ε | c/t ≤ 33ε | c/t ≤ 9ε | d/t ≤ 50ε² |
| 2 | c/t ≤ 83ε | c/t ≤ 38ε | c/t ≤ 10ε | d/t ≤ 70ε² |
| 3 | c/t ≤ 124ε | c/t ≤ 42ε | c/t ≤ 14ε | d/t ≤ 90ε² |

Under combined bending and compression the limit depends on where the neutral axis sits,
which the table carries as α (the compressed share of c, for classes 1 and 2) and ψ (the
end-stress ratio, for class 3). An internal part takes 396ε/(13α−1) and 456ε/(13α−1) above
α = 0,5 and 36ε/α and 41,5ε/α at or below it; a class 3 internal part takes
42ε/(0,67+0,33ψ) above ψ = −1 and 62ε(1−ψ)√(−ψ) at or below it. An outstand flange takes
9ε/α and 10ε/α with its tip in compression, 9ε/(α√α) and 10ε/(α√α) with its tip in tension,
and for class 3 the single limit 21ε√k_σ, whose buckling factor comes from EN 1993-1-5 and
is the caller's.

**What this module does not decide.** α, ψ and k_σ are the caller's, and so is the choice
of simplification: the standard's own commentary says classifying for the combined case
needs the neutral-axis position and that designers often substitute the compression-only
classification, which is conservative. This computes limits from the values it is given and
never guesses at a stress distribution. The two exceptions of clauses 5.5.2(11) and
5.5.2(12) — a class 3 web with class 1 or 2 flanges treated as class 2 with an effective
web, and a web taken to resist shear only — are design decisions about a section, not
properties of an element, and are not applied here.

**Source, read rather than recalled.** EN 1993-1-1 is copyrighted and is not bundled. The
limits above are read from
[*Eurocodes: Background and Applications — Design of Steel Buildings*](https://orbi.uliege.be/bitstream/2268/194798/1/Eurocodes%20Background&applications%20design%20of%20steel%20buildings.pdf),
the European Commission's Joint Research Centre report from its 2014 Brussels workshop
(Simões da Silva and Simões, §1.2.2.4), whose Tables 1.1, 1.2 and 1.3 state that they
reproduce Table 5.2 of EN 1993-1-1, and whose clause numbers are quoted above as it gives
them. The table pages were read as images rather than as extracted text, because the
extraction drops every ε, α and ψ and every ≤ — a limit of "72" with its ε lost is a
plausible number and a wrong one.

**What the arithmetic is checked against.** The same report works two classifications in
full, and both are replayed in the tests: an HEB 340 in S355 under pure compression
(§1.3.1, web c/t = 20,25 against 33ε = 26,73 and flange c/t = 5,44 against 9ε = 7,29,
class 1) and an IPE 400 in S355 in pure bending (§1.3.2, web c/t = 38,49 against
72ε = 58,32 and flange c/t = 4,79 against 9ε = 7,29, class 1). Those also pin how c is
measured on a rolled I-section, which the table states only as a figure: the web's
c = h − 2t_f − 2r and the flange's c = (b − t_w)/2 − r, the root radius taken out of both.

**The edition.** This is the 2005 generation with its 2014 amendment, which is what the
report applies. EN 1993-1-1:2022 renumbered and rewrote parts of §5.5, and it could not be
read from here, so nothing in this module claims to be the 2022 edition; a design basis
pinning it is not answered by these limits.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "SectionClass",
    "PartStress",
    "FlangeTip",
    "en1993_epsilon",
    "internal_part_class",
    "outstand_flange_class",
    "angle_in_compression_class",
    "tubular_section_class",
    "rolled_i_section_class",
]

_STEEL_SOURCE = "the steel grade's product standard, by the thickness the element is at"
_SECTION_SOURCE = "the section table or the measured cross-section the element is taken from"
_DISTRIBUTION_SOURCE = "the elastic stress distribution the design forces put on the element"

#: ε is referred to 235 N/mm², the nominal yield of S235 (Table 5.2's own definition).
_REFERENCE_YIELD_MPA = 235.0

# Table 5.2, internal compression parts: (class 1, class 2, class 3) coefficients on ε.
_INTERNAL_BENDING = (72.0, 83.0, 124.0)
_INTERNAL_COMPRESSION = (33.0, 38.0, 42.0)
# Combined, above α = 0,5: numerator over (13α − 1), classes 1 and 2.
_INTERNAL_COMBINED_HIGH = (396.0, 456.0)
# Combined, at or below α = 0,5: numerator over α, classes 1 and 2.
_INTERNAL_COMBINED_LOW = (36.0, 41.5)
_ALPHA_BREAK = 0.5
_PSI_BREAK = -1.0
_CLASS_3_COMBINED = 42.0
_CLASS_3_PSI_OFFSET = 0.67
_CLASS_3_PSI_SLOPE = 0.33
_CLASS_3_DEEP = 62.0

# Table 5.2, outstand flanges: (class 1, class 2, class 3) coefficients on ε.
_OUTSTAND_COMPRESSION = (9.0, 10.0, 14.0)
_OUTSTAND_COMBINED = (9.0, 10.0)
_OUTSTAND_CLASS_3_COMBINED = 21.0

# Table 5.2, angles in compression: h/t and (b + h)/2t, both for class 3.
_ANGLE_LEG = 15.0
_ANGLE_MEAN = 11.5

# Table 5.2, tubular sections: coefficients on ε², for d/t.
_TUBULAR = (50.0, 70.0, 90.0)


class _En1993ClassificationInputError(RefusalError, ValueError):
    """An EN 1993 classification input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str) -> _En1993ClassificationInputError:
    return _En1993ClassificationInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class SectionClass(IntEnum):
    """A cross-section or element class, 1 to 4 (EN 1993-1-1 clause 5.5.2(1)).

    An ``IntEnum`` because the class is a number in the standard and because the rule that
    combines elements is an ordering: a section takes the **highest** class of its
    compressed parts, which is ``max`` over these and would be a string comparison on
    anything else.
    """

    CLASS_1 = 1
    CLASS_2 = 2
    CLASS_3 = 3
    CLASS_4 = 4


class PartStress(StrEnum):
    """Which column of EN 1993-1-1 Table 5.2 an element's stress distribution puts it in."""

    BENDING = "bending"
    COMPRESSION = "compression"
    BENDING_AND_COMPRESSION = "bending_and_compression"


class FlangeTip(StrEnum):
    """For an outstand flange under combined stress: which end of it is in compression.

    EN 1993-1-1 Table 5.2 splits the combined case for an outstand because the two are not the same
    element: a tip in tension is held by the part of the flange that yields last, so its
    limit carries an extra √α.
    """

    IN_COMPRESSION = "in_compression"
    IN_TENSION = "in_tension"


def en1993_epsilon(*, yield_strength: Quantity) -> float:
    """EN 1993-1-1 Table 5.2's material factor ε = √(235/f_y), from ``yield_strength``.

    Every limit in Table 5.2 is a multiple of this (or, for a tubular section, of ε²), so a
    stronger steel has proportionally tighter limits: ε is 1,00 at S235, 0,92 at S275, 0,81
    at S355, 0,75 at S420 and 0,71 at S460, as the table tabulates it.

    Computed from the definition rather than read off that tabulation. The table's figures
    are rounded to two decimals as a reading aid — √(235/355) is 0,8137, which the table
    prints as 0,81 — and rounding a limit down by a part in a hundred before comparing is
    not a conservatism the standard asks for.

    ``yield_strength`` is the nominal yield of the grade **at the element's thickness**,
    which is the part a thickness range changes; the grade alone does not state it.
    """
    if not isinstance(yield_strength, Quantity):
        raise _refuse(
            f"yield_strength must be a [pressure] quantity; got {yield_strength!r}",
            subject="yield_strength",
            source=_STEEL_SOURCE,
        )
    if not yield_strength.has_dimension("[pressure]"):
        raise _refuse(
            f"yield_strength must be a [pressure] quantity; got {yield_strength.dimensionality}",
            subject="yield_strength",
            source=_STEEL_SOURCE,
        )
    fy = require_finite(yield_strength.to("MPa"), name="yield_strength")
    if fy <= 0:
        raise _refuse(
            f"yield_strength must be positive; got {yield_strength}",
            subject="yield_strength",
            source=_STEEL_SOURCE,
        )
    return sqrt(_REFERENCE_YIELD_MPA / fy)


def _ratio(value: float, name: str) -> float:
    """A width-to-thickness ratio: finite and positive, or a refusal naming it."""
    require_finite(value, name=name)
    if value <= 0:
        raise _refuse(
            f"{name} is a width over a thickness and must be positive; got {value}",
            subject=name,
            source=_SECTION_SOURCE,
        )
    return float(value)


def _epsilon(value: float) -> float:
    require_finite(value, name="epsilon")
    if value <= 0:
        raise _refuse(
            f"epsilon must be positive; got {value}. It is √(235/f_y) — see en1993_epsilon",
            subject="epsilon",
            source=_STEEL_SOURCE,
        )
    return float(value)


def _alpha(value: float | None) -> float:
    """α, the compressed share of the part's depth: in (0, 1]."""
    if value is None:
        raise _refuse(
            "alpha is required under bending and compression for classes 1 and 2: it is the "
            "compressed share of the part's depth, which fixes where the neutral axis sits",
            subject="alpha",
            source=_DISTRIBUTION_SOURCE,
        )
    require_finite(value, name="alpha")
    if not 0.0 < value <= 1.0:
        raise _refuse(
            f"alpha is the compressed share of the part's depth and lies in (0, 1]; got {value}. "
            "A part wholly in compression is alpha = 1 and the compression column of Table 5.2",
            subject="alpha",
            source=_DISTRIBUTION_SOURCE,
        )
    return float(value)


def _psi(value: float | None) -> float:
    """ψ, the ratio of the part's end stresses: in [-1 is not a bound, but finite]."""
    if value is None:
        raise _refuse(
            "psi is required under bending and compression for class 3: it is the ratio of "
            "the stresses at the part's two edges, compression positive",
            subject="psi",
            source=_DISTRIBUTION_SOURCE,
        )
    require_finite(value, name="psi")
    if value > 1.0:
        raise _refuse(
            f"psi is a ratio of end stresses and cannot exceed 1; got {value}. A uniform "
            "compression is psi = 1, which is the compression column of Table 5.2",
            subject="psi",
            source=_DISTRIBUTION_SOURCE,
        )
    return float(value)


def internal_part_class(
    *,
    ratio: float,
    epsilon: float,
    stress: PartStress = PartStress.COMPRESSION,
    alpha: float | None = None,
    psi: float | None = None,
) -> SectionClass:
    """An internal compression part's class from its c/t (EN 1993-1-1 Table 5.2, sheet 1).

    An internal part is supported along both its edges — an I-section's web, either wall of
    a rectangular hollow section — which is why its limits are several times an outstand's.
    ``ratio`` is c/t, ``epsilon`` is :func:`en1993_epsilon`, and ``stress`` says which
    column of the table applies. Under ``BENDING_AND_COMPRESSION`` the limits depend on the
    neutral axis: ``alpha`` for classes 1 and 2 and ``psi`` for class 3, each required and
    refused rather than assumed.

    Returns the class; a part outside even the class 3 limit is ``CLASS_4``
    (clause 5.5.2(8)) rather than a refusal, because class 4 is an answer the standard has
    and an effective cross-section is what follows from it.
    """
    c_over_t = _ratio(ratio, "ratio")
    e = _epsilon(epsilon)
    if stress is PartStress.BENDING:
        limits = tuple(coefficient * e for coefficient in _INTERNAL_BENDING)
    elif stress is PartStress.COMPRESSION:
        limits = tuple(coefficient * e for coefficient in _INTERNAL_COMPRESSION)
    else:
        a = _alpha(alpha)
        if a > _ALPHA_BREAK:
            plastic = tuple(n * e / (13.0 * a - 1.0) for n in _INTERNAL_COMBINED_HIGH)
        else:
            plastic = tuple(n * e / a for n in _INTERNAL_COMBINED_LOW)
        p = _psi(psi)
        if p > _PSI_BREAK:
            elastic = _CLASS_3_COMBINED * e / (_CLASS_3_PSI_OFFSET + _CLASS_3_PSI_SLOPE * p)
        else:
            elastic = _CLASS_3_DEEP * e * (1.0 - p) * sqrt(-p)
        limits = (*plastic, elastic)
    return _first_class_met(c_over_t, limits)


def outstand_flange_class(
    *,
    ratio: float,
    epsilon: float,
    stress: PartStress = PartStress.COMPRESSION,
    alpha: float | None = None,
    tip: FlangeTip = FlangeTip.IN_COMPRESSION,
    buckling_factor: float | None = None,
) -> SectionClass:
    """An outstand flange's class from its c/t (EN 1993-1-1 Table 5.2, sheet 2).

    An outstand is supported along one edge only and free along the other, so it buckles at
    roughly a seventh of an internal part's ratio: 9ε, 10ε and 14ε against 33ε, 38ε and 42ε
    in uniform compression. ``ratio`` is c/t and ``epsilon`` is :func:`en1993_epsilon`.

    Under ``BENDING_AND_COMPRESSION``, ``alpha`` is required and ``tip`` says which end is
    in compression: a tip in tension carries an extra √α in the denominator, because the
    edge that yields last is the one holding the flange. Class 3 in that case is the single
    limit 21ε√k_σ, and ``buckling_factor`` k_σ comes from EN 1993-1-5 — it is not derived
    here and is refused when the combined case is asked for without it, since the table
    gives no default and assuming the uniform-compression k_σ would report a flange as
    class 3 that is class 4.

    Table 5.2 has **no bending-only column for an outstand**, and this follows it: an
    outstand in bending alone is a part with a tension edge and a compression edge, which
    is the combined case with its own α and ψ. Asking for ``BENDING`` here is refused
    naming the column it would have to invent.
    """
    c_over_t = _ratio(ratio, "ratio")
    e = _epsilon(epsilon)
    if stress is PartStress.BENDING:
        raise _refuse(
            "Table 5.2 gives an outstand flange a compression column and a combined column "
            "and no bending-only column; an outstand with a tension edge is the combined "
            "case, so pass BENDING_AND_COMPRESSION with its alpha and buckling_factor",
            subject="stress",
            source=_DISTRIBUTION_SOURCE,
        )
    if stress is PartStress.COMPRESSION:
        limits = tuple(coefficient * e for coefficient in _OUTSTAND_COMPRESSION)
    else:
        a = _alpha(alpha)
        divisor = a if tip is FlangeTip.IN_COMPRESSION else a * sqrt(a)
        plastic = tuple(coefficient * e / divisor for coefficient in _OUTSTAND_COMBINED)
        if buckling_factor is None:
            raise _refuse(
                "buckling_factor k_sigma is required for a class 3 outstand under bending "
                "and compression: Table 5.2's limit is 21ε√k_σ and EN 1993-1-5 is where "
                "k_σ comes from. Table 5.2 gives it no default",
                subject="buckling_factor",
                source="EN 1993-1-5 Table 4.2, for this flange's stress distribution",
            )
        require_finite(buckling_factor, name="buckling_factor")
        if buckling_factor <= 0:
            raise _refuse(
                f"buckling_factor must be positive; got {buckling_factor}",
                subject="buckling_factor",
                source="EN 1993-1-5 Table 4.2, for this flange's stress distribution",
            )
        limits = (*plastic, _OUTSTAND_CLASS_3_COMBINED * e * sqrt(buckling_factor))
    return _first_class_met(c_over_t, limits)


def angle_in_compression_class(
    *,
    leg_ratio: float,
    mean_ratio: float,
    epsilon: float,
) -> SectionClass:
    """An angle in compression: class 3 when it meets **both** limits (EN 1993-1-1 Table 5.2).

    ``leg_ratio`` is h/t and ``mean_ratio`` is (b + h)/2t; the table requires h/t ≤ 15ε and
    (b + h)/2t ≤ 11,5ε together, so the governing one of the two decides. The sheet offers
    no class 1 or class 2 for an angle in compression, which is the answer and not a gap:
    the best an angle gets here is class 3, and failing either limit makes it class 4.

    The table's own note is a precondition this cannot check: the sheet **does not apply to
    angles in continuous contact with other components**, where the attached leg is not an
    outstand at all. Whether the angle is continuously attached is a fact about the joint,
    not about the section, so it stays with the caller — see also
    :func:`outstand_flange_class`, which the sheet points to as well.
    """
    leg = _ratio(leg_ratio, "leg_ratio")
    mean = _ratio(mean_ratio, "mean_ratio")
    e = _epsilon(epsilon)
    if leg <= _ANGLE_LEG * e and mean <= _ANGLE_MEAN * e:
        return SectionClass.CLASS_3
    return SectionClass.CLASS_4


def tubular_section_class(*, diameter_ratio: float, epsilon: float) -> SectionClass:
    """A circular hollow section's class from d/t (EN 1993-1-1 Table 5.2, sheet 3).

    The limits go as **ε², not ε** — 50ε², 70ε², 90ε² — because a tube's local buckling
    stress scales with t/d rather than with (t/c)². That squaring is the thing to get right,
    and it is not a rounding: at S355 ε² is 0,662 against ε of 0,814, so the class 3 limit
    is d/t ≤ 59,6 and not ≤ 73,2. A d/t of 60 is **class 4** — an effective cross-section,
    or EN 1993-1-6 — where the mistake reads it as class 3, and a d/t of 50 is class 3
    where the mistake reads it as class 2. The error runs one class optimistic across the
    whole range.

    One sheet covers bending, compression and the two together, so there is no stress
    argument. Beyond 90ε² the section is class 4 here; the table's note sends that case to
    EN 1993-1-6, whose shell rules are not in this module.
    """
    d_over_t = _ratio(diameter_ratio, "diameter_ratio")
    e = _epsilon(epsilon)
    return _first_class_met(d_over_t, tuple(coefficient * e * e for coefficient in _TUBULAR))


def _first_class_met(ratio: float, limits: tuple[float, ...]) -> SectionClass:
    """The lowest class whose limit ``ratio`` meets, or class 4 when it meets none."""
    for number, limit in enumerate(limits, start=1):
        if ratio <= limit:
            return SectionClass(number)
    return SectionClass.CLASS_4


def rolled_i_section_class(
    *,
    height: Quantity,
    width: Quantity,
    web_thickness: Quantity,
    flange_thickness: Quantity,
    root_radius: Quantity,
    yield_strength: Quantity,
    stress: PartStress = PartStress.COMPRESSION,
    alpha: float | None = None,
    psi: float | None = None,
) -> tuple[SectionClass, SectionClass, SectionClass]:
    """A rolled I or H section's class, and its web's and flange's (EN 1993-1-1 5.5.2(6)).

    The section is classified by the **highest, least favourable** class of its compressed
    parts, which for a rolled I-shape are its web (an internal part) and its compression
    flange (an outstand). Returns ``(section, web, flange)``, so a caller can see which
    element governs rather than only what it was.

    ``stress`` describes the **web**: a section in uniform compression puts its flange in
    uniform compression too, and a section in bending has a flange that is wholly in
    compression on the compression side — which is the compression column of Table 5.2
    sheet 2 either way, and is how the source's own worked examples classify it. Under
    ``BENDING_AND_COMPRESSION`` the web takes ``alpha`` and ``psi``, and the flange is
    still taken as uniformly compressed; a flange with its own stress gradient (a
    mono-symmetric or welded section under biaxial bending) is
    :func:`outstand_flange_class` called directly.

    How c is measured is the part Table 5.2 states only as a figure, and both of the
    source's worked examples turn on it: the **root radius comes out of both elements**.
    The web's c is ``h − 2·t_f − 2·r`` and the flange's is ``(b − t_w)/2 − r``. Taking the
    web's c as the full depth instead would read an IPE 400's web as 46,5 rather than 38,49
    and still call it class 1, but at the class 3 boundary it is the difference between a
    section with a plastic moment and one on an effective cross-section.
    """
    dimensions = {
        "height": height,
        "width": width,
        "web_thickness": web_thickness,
        "flange_thickness": flange_thickness,
        "root_radius": root_radius,
    }
    values: dict[str, float] = {}
    for name, value in dimensions.items():
        if not isinstance(value, Quantity):
            raise _refuse(
                f"{name} must be a [length] quantity; got {value!r}",
                subject=name,
                source=_SECTION_SOURCE,
            )
        if not value.has_dimension("[length]"):
            raise _refuse(
                f"{name} must be a [length] quantity; got {value.dimensionality}",
                subject=name,
                source=_SECTION_SOURCE,
            )
        magnitude = require_finite(value.to("mm"), name=name)
        if magnitude < 0 or (magnitude == 0 and name != "root_radius"):
            raise _refuse(
                f"{name} must be positive; got {value}. A welded section has no root radius "
                f"and takes root_radius = 0",
                subject=name,
                source=_SECTION_SOURCE,
            )
        values[name] = magnitude

    web_c = values["height"] - 2.0 * values["flange_thickness"] - 2.0 * values["root_radius"]
    flange_c = (values["width"] - values["web_thickness"]) / 2.0 - values["root_radius"]
    for name, c in (("web", web_c), ("flange", flange_c)):
        if c <= 0:
            raise _refuse(
                f"the {name}'s flat width comes out {c:.4g} mm, so these dimensions are not a "
                f"rolled I-section: the flanges and root radii consume the whole of it",
                subject="height, width, flange_thickness and root_radius",
                source=_SECTION_SOURCE,
            )
    epsilon = en1993_epsilon(yield_strength=yield_strength)
    web = internal_part_class(
        ratio=web_c / values["web_thickness"],
        epsilon=epsilon,
        stress=stress,
        alpha=alpha,
        psi=psi,
    )
    flange = outstand_flange_class(
        ratio=flange_c / values["flange_thickness"],
        epsilon=epsilon,
        stress=PartStress.COMPRESSION,
    )
    return (max(web, flange), web, flange)
