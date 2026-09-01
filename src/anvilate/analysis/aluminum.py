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
stress), and C (the intersection slenderness) belong to the alloy-temper and the
buckling mode. Aluminum's low modulus (about a third of steel's) makes these
members buckling-governed far sooner than a steel one of the same slenderness.
Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.

Two ways in. :func:`aluminum_buckling_stress` takes B, D and C directly, for a
caller who has them. The ADM 2020 screens below instead *compute* them from the
alloy's own F_cy and E by the §B.4 formulas — no bundled copy of the standard's
tables — and run the member through yielding, local buckling (§B.5.4), member
buckling (§E.3), lateral-torsional buckling (§F.4.2) and the §H.1 interaction,
naming which limit state governed.

Welding is the discipline's signature trap and is first-class here. A 6061-T6
extrusion loses more than half its compressive yield within an inch of the arc,
permanently, and a member declared welded is screened on both property sets with
both reported. A declared weld with no weld-affected properties supplied is
``NOT_EVALUATED``, never a check quietly run on parent-metal strength.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite, pi, sqrt

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import Named, RevalidatedModel, cited
from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity, require_finite

__all__ = [
    "aluminum_buckling_stress",
    "aluminum_tension_stress",
    "TemperGroup",
    "EdgeSupport",
    "AluminumLimitState",
    "AlloyProperties",
    "BucklingConstants",
    "AluminumCompressionStrength",
    "aluminum_buckling_constants",
    "aluminum_member_buckling_stress",
    "aluminum_local_buckling_stress",
    "aluminum_elastic_local_buckling_stress",
    "aluminum_lateral_torsional_moment",
    "aluminum_combined_interaction",
    "aluminum_compression_strength",
    "aluminum_compression_scorecard",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


def aluminum_buckling_stress(
    *,
    slenderness: float,
    intercept: Quantity,
    slope: Quantity,
    intersection_slenderness: float,
    elastic_modulus: Quantity,
) -> Quantity:
    """The bare Aluminum Design Manual straight-line/Euler form, for caller-supplied B, D, C.

    F = B − D·λ below the intersection slenderness C, and π²·E/λ² above it. ``intercept``
    B and ``slope`` D are stresses, ``intersection_slenderness`` C a slenderness, and
    ``elastic_modulus`` E ≈ 69 GPa for aluminum. Returns F in MPa.

    **This is the raw shape, not any one of the ADM's member checks**, and it is not
    interchangeable with them. It does not cap the result at F_cy, so at a low slenderness
    it returns a "buckling stress" above the alloy's own yield; and its elastic branch is
    π²E/λ², without the 0.85 out-of-straightness knockdown §E.3 applies to a *column*.
    Feeding it column constants therefore overstates a column by 17.6% on the elastic
    branch — use :func:`aluminum_member_buckling_stress`, which computes B_c, D_c and C_c
    from the alloy and applies both. This function is for a caller who has a set of
    constants for some other mode and wants the curve evaluated, nothing more.
    """
    _require(intercept, "[pressure]", "intercept")
    _require(slope, "[pressure]", "slope")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    b = intercept.to("MPa").magnitude
    d = slope.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    # A NaN intersection makes `slenderness <= intersection_slenderness` False, so the
    # function silently takes the *elastic* Euler branch instead of the inelastic line and
    # returned 2.13x the correct stress — above any aluminum yield strength. The branch is
    # the answer here, so a non-finite comparand is not a detail.
    require_finite(slenderness, name="slenderness")
    require_finite(intersection_slenderness, name="intersection_slenderness")
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
    # NaN passes `< 1.0` and `min(fty, ftu/k_t)` then drops net-section rupture entirely:
    # 240 MPa returned where the answer is 208, a 15.4% overstatement. k_t = 0.5 was already
    # refused, which is the tell — the guard caught the wrong kind of bad value.
    require_finite(tension_coefficient, name="tension_coefficient")
    if tension_coefficient < 1.0:
        raise ValueError(f"tension_coefficient must be at least 1.0; got {tension_coefficient}")
    return Quantity(magnitude=min(fty, ftu / tension_coefficient), unit="MPa")


# --- ADM 2020 member screens ------------------------------------------------
#
# Sources: Aluminum Design Manual 2020, Part I (Specification for Aluminum
# Structures) §B.4 buckling constants, §B.5.4 local buckling of flat elements,
# §E.3 member buckling, §F.4.2 lateral-torsional buckling, and §H.1 combined
# forces. Every constant below was checked against the allowable stresses the
# Aluminum Design Manual publishes for 6061-T6 in Part VI Table 2-19; the anchors
# are in the tests, so the agreement is asserted rather than asserted-about.
#
# The buckling constants are COMPUTED from the §B.4 formulas as functions of the
# alloy's own F_cy and E. They are never read out of a bundled copy of the
# standard's tables, which is both a licensing matter and a correctness one: a
# tabulated constant silently stops applying the moment a caller supplies a
# tested or certified strength that is not the table's.

# ADM Table B.4.2, artificially aged (-T5 through -T9) tempers. Both denominators
# are stresses in ksi, the unit the ADM writes them in, so F_cy enters these two
# expressions in ksi and nothing else in the module carries a hidden unit.
_BC_DENOMINATOR_KSI = 2250.0  # B_c = F_cy[1 + (F_cy/2250)^(1/2)]
_BP_DENOMINATOR_KSI = 1500.0  # B_p = F_cy[1 + (F_cy/1500)^(1/3)]
# ADM Table B.4.3 postbuckling constants, artificially aged tempers.
_K1_AGED = 0.35  # where the postbuckling branch of a both-edges element starts
_K2_AGED = 2.27  # the coefficient of that branch
# The slenderness at which an inelastic straight line meets its Euler curve, as a
# fraction of B/D. The ADM's straight-line fit makes this 0.41·B/D for an
# artificially aged temper (and 2/3·B/D for the others, which this module does
# not implement).
_INTERSECTION_FRACTION_AGED = 0.41
# ADM §E.3: the factor by which member buckling is knocked down for the
# out-of-straightness a real column is fabricated with. Local and lateral-
# torsional buckling carry no such factor — they are not member-length effects.
_OUT_OF_STRAIGHTNESS = 0.85
# ADM §B.5.4.1/§B.5.4.2 edge-support coefficients on b/t.
_K_BOTH_EDGES = 1.6
_K_ONE_EDGE = 5.0

_CLAUSE_ADM = "Aluminum Design Manual 2020 Part I §B.4/§B.5.4/§E.3/§F.4.2"


class TemperGroup(StrEnum):
    """Which Aluminum Design Manual buckling-constant table an alloy-temper uses.

    The ADM splits the buckling constants in two, because the two families of temper
    have genuinely different inelastic curves: an artificially aged temper (-T5 through
    -T9) has a sharper knee than an annealed, strain-hardened or naturally aged one.
    Getting the group wrong is not a rounding error — it changes both the intercept and
    the slenderness at which the curve hands over to Euler.

    Only :attr:`ARTIFICIALLY_AGED` is implemented. The :attr:`NON_AGED` group is a
    declaration this module accepts and refuses to screen, which is the point: a caller
    who names an -H32 sheet gets a ``NOT_EVALUATED`` naming ADM Table B.4.1, not a
    number computed off the wrong table.
    """

    ARTIFICIALLY_AGED = "artificially_aged"  # -T5 .. -T9, ADM Table B.4.2
    NON_AGED = "non_aged"  # -O, -H, -T1 .. -T4, ADM Table B.4.1 (not implemented)


class EdgeSupport(StrEnum):
    """How a flat compression element is held along its edges (Aluminum Design Manual §B.5.4).

    The difference is a factor of about three in the effective slenderness — an element
    held on both edges (a tube wall, an I-beam web) buckles into a much stiffer shape
    than one held on one edge with the other free (an outstanding flange, an angle leg).
    The two also end differently: a both-edges element has real postbuckling strength
    the ADM lets you use, while a one-edge element is cut off at the elastic curve.
    """

    BOTH_EDGES = "both_edges"  # k = 1.6, postbuckling permitted (ADM §B.5.4.1)
    ONE_EDGE = "one_edge"  # k = 5.0, elastic cutoff (ADM §B.5.4.2)


class AluminumLimitState(StrEnum):
    """Which Aluminum Design Manual limit state governed an aluminum member check.

    Reported because the repair differs by state and two of them respond to opposite
    changes: local buckling wants thicker material or a narrower flat, member buckling
    wants a shorter unbraced length or a fatter radius of gyration, and yielding wants a
    stronger temper — which is the one repair a weld undoes.
    """

    YIELDING = "yielding"
    LOCAL_BUCKLING = "local buckling"
    MEMBER_BUCKLING = "member buckling"
    LATERAL_TORSIONAL_BUCKLING = "lateral-torsional buckling"


class AlloyProperties(RevalidatedModel):
    """An alloy-temper's mechanical properties, and where they came from.

    Following the library's user-supplied-allowables doctrine: Anvilate ships no alloy
    database and reproduces none of the Aluminum Design Manual's property tables.
    ``source`` records where the numbers came from — the mill certificate, the ADM
    table the user read, the project specification — so a report cites the caller's
    authority rather than presenting the values as Anvilate's own. It may not be blank.

    ``weld_affected`` carries the same properties for the heat-affected zone. Welding
    aluminum is not a detail: a 6061-T6 extrusion loses over half its compressive yield
    within an inch of the arc, and the loss is permanent unless the part is re-heat-
    treated. When it is ``None`` a member declared welded reports ``NOT_EVALUATED``
    naming what is missing — never a check quietly run on parent-metal strength.
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    compressive_yield: Quantity  # F_cy
    tensile_yield: Quantity  # F_ty
    tensile_ultimate: Quantity  # F_tu
    elastic_modulus: Quantity  # E
    temper_group: TemperGroup
    source: cited(
        "where these properties came from — the mill certificate, the ADM table read, or "
        "the project specification"
    )
    tension_coefficient: float = 1.0  # k_t, ADM Table A.3.3
    weld_affected: AlloyProperties | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> AlloyProperties:
        for value, name in (
            (self.compressive_yield, "compressive_yield"),
            (self.tensile_yield, "tensile_yield"),
            (self.tensile_ultimate, "tensile_ultimate"),
            (self.elastic_modulus, "elastic_modulus"),
        ):
            if not value.has_dimension("[pressure]"):
                raise ValueError(f"{name} must be a [pressure] quantity; got {value}")
            if value.magnitude <= 0:
                raise ValueError(f"{name} must be positive; got {value}")
        if self.tension_coefficient < 1.0:
            raise ValueError(
                f"tension_coefficient k_t must be at least 1.0; got {self.tension_coefficient}"
            )
        if self.weld_affected is not None and self.weld_affected.weld_affected is not None:
            raise ValueError(
                "a weld-affected property set has no weld-affected set of its own; the "
                "heat-affected zone is already the reduced material"
            )
        return self


class BucklingConstants(BaseModel):
    """The Aluminum Design Manual §B.4 buckling constants for one alloy-temper, from F_cy and E.

    ``intercept_member`` B_c and ``slope_member`` D_c define the straight inelastic line
    for member (column, flange) buckling, meeting the Euler curve at
    ``intersection_member`` C_c. ``intercept_plate`` B_p, ``slope_plate`` D_p and
    ``intersection_plate`` C_p do the same for a flat element buckling locally. B and D
    are stresses; C is a slenderness and dimensionless.
    """

    model_config = ConfigDict(frozen=True)

    intercept_member: Quantity  # B_c
    slope_member: Quantity  # D_c
    intersection_member: float  # C_c
    intercept_plate: Quantity  # B_p
    slope_plate: Quantity  # D_p
    intersection_plate: float  # C_p


def aluminum_buckling_constants(
    *,
    compressive_yield: Quantity,
    elastic_modulus: Quantity,
    temper_group: TemperGroup = TemperGroup.ARTIFICIALLY_AGED,
) -> BucklingConstants:
    """The ADM §B.4 buckling constants, computed from the alloy's F_cy and E.

    Aluminum Design Manual 2020 Table B.4.2, for the artificially aged tempers
    (-T5 through -T9), which is where the structural workhorses live:

    * B_c = F_cy[1 + (F_cy/2250)^(1/2)],  D_c = (B_c/10)(B_c/E)^(1/2),  C_c = 0.41·B_c/D_c
    * B_p = F_cy[1 + (F_cy/1500)^(1/3)],  D_p = (B_p/10)(B_p/E)^(1/2),  C_p = 0.41·B_p/D_p

    The 2250 and 1500 are stresses in ksi, the unit the ADM writes them in, so F_cy
    enters those two terms in ksi; everything else is a ratio and carries no unit. The
    two D expressions read as slopes because they are: dividing by E is what makes an
    inelastic line steeper for a strong, low-modulus alloy than for a mild one.

    ``temper_group`` of :attr:`TemperGroup.NON_AGED` raises. Those tempers take ADM
    Table B.4.1, whose constants have a different form, and evaluating Table B.4.2 on an
    -H34 sheet would produce a plausible number off the wrong curve. Callers that want a
    verdict rather than an exception should route through
    :func:`aluminum_compression_strength`, which reports it as not evaluated.

    Returns a :class:`BucklingConstants` with B and D in MPa.
    """
    if not isinstance(compressive_yield, Quantity):
        raise ValueError(
            f"compressive_yield must be a [pressure] quantity; got {compressive_yield!r}"
        )
    if not compressive_yield.has_dimension("[pressure]"):
        raise ValueError(
            f"compressive_yield must be a [pressure] quantity; got {compressive_yield}"
        )
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    if temper_group is not TemperGroup.ARTIFICIALLY_AGED:
        raise ValueError(
            "only the artificially aged tempers (-T5 through -T9, ADM Table B.4.2) are "
            "implemented; an -O, -H, -T1 through -T4 temper takes ADM Table B.4.1, whose "
            "constants have a different form and are not evaluated here"
        )
    fcy_ksi = compressive_yield.to("ksi").magnitude
    e_ksi = elastic_modulus.to("ksi").magnitude
    if fcy_ksi <= 0 or e_ksi <= 0:
        raise ValueError("compressive_yield and elastic_modulus must be positive")
    bc = fcy_ksi * (1.0 + sqrt(fcy_ksi / _BC_DENOMINATOR_KSI))
    dc = (bc / 10.0) * sqrt(bc / e_ksi)
    bp = fcy_ksi * (1.0 + (fcy_ksi / _BP_DENOMINATOR_KSI) ** (1.0 / 3.0))
    dp = (bp / 10.0) * sqrt(bp / e_ksi)
    return BucklingConstants(
        intercept_member=Quantity(magnitude=bc, unit="ksi").to("MPa"),
        slope_member=Quantity(magnitude=dc, unit="ksi").to("MPa"),
        intersection_member=_INTERSECTION_FRACTION_AGED * bc / dc,
        intercept_plate=Quantity(magnitude=bp, unit="ksi").to("MPa"),
        slope_plate=Quantity(magnitude=dp, unit="ksi").to("MPa"),
        intersection_plate=_INTERSECTION_FRACTION_AGED * bp / dp,
    )


def aluminum_member_buckling_stress(
    *,
    slenderness: float,
    compressive_yield: Quantity,
    elastic_modulus: Quantity,
    constants: BucklingConstants,
) -> Quantity:
    """The Aluminum Design Manual §E.3 member buckling stress F_c of a column, in MPa.

    Three branches on the slenderness λ = kL/r, with λ_1 = (B_c − F_cy)/D_c the
    slenderness at which the inelastic line has fallen to yield:

    * λ ≤ λ_1 — **yielding**, F_c = F_cy. The column is too stocky to buckle.
    * λ_1 < λ ≤ C_c — **inelastic buckling**,
      F_c = (B_c − D_c·λ)[0.85 + 0.15(C_c − λ)/(C_c − λ_1)]. The bracket eases the
      0.85 out-of-straightness knockdown in as the column lengthens: it is 1.0 at λ_1,
      where the column squashes and straightness cannot matter, and 0.85 at C_c.
    * λ > C_c — **elastic buckling**, F_c = 0.85·π²E/λ², the Euler curve with the
      knockdown fully applied.

    ``constants`` comes from :func:`aluminum_buckling_constants` for the same alloy.
    Aluminum's modulus is about a third of steel's, so the handover to Euler happens at
    a slenderness a steel designer would still think of as stocky — C_c is 66 for
    6061-T6, against about 113 for A992 steel.
    """
    if slenderness <= 0:
        raise ValueError(f"slenderness must be positive; got {slenderness}")
    if not isinstance(compressive_yield, Quantity):
        raise ValueError(
            f"compressive_yield must be a [pressure] quantity; got {compressive_yield!r}"
        )
    if not compressive_yield.has_dimension("[pressure]"):
        raise ValueError(
            f"compressive_yield must be a [pressure] quantity; got {compressive_yield}"
        )
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    fcy = compressive_yield.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    bc = constants.intercept_member.to("MPa").magnitude
    dc = constants.slope_member.to("MPa").magnitude
    cc = constants.intersection_member
    if fcy <= 0 or e <= 0:
        raise ValueError("compressive_yield and elastic_modulus must be positive")
    lambda_1 = (bc - fcy) / dc
    if slenderness <= lambda_1:
        stress = fcy
    elif slenderness <= cc:
        eased = _OUT_OF_STRAIGHTNESS + 0.15 * (cc - slenderness) / (cc - lambda_1)
        stress = (bc - dc * slenderness) * eased
    else:
        stress = _OUT_OF_STRAIGHTNESS * pi**2 * e / slenderness**2
    return Quantity(magnitude=stress, unit="MPa")


def aluminum_local_buckling_stress(
    *,
    flat_width: Quantity,
    thickness: Quantity,
    compressive_yield: Quantity,
    elastic_modulus: Quantity,
    constants: BucklingConstants,
    edge_support: EdgeSupport = EdgeSupport.BOTH_EDGES,
) -> Quantity:
    """The Aluminum Design Manual §B.5.4 local buckling stress of a flat element, in MPa.

    On the element slenderness b/t, where b is the *flat* width — the ADM lets you
    deduct the fillet radius when R < 4t, and neglecting it is conservative. The
    edge-support coefficient k multiplies b/t: k = 1.6 for an element held on both edges
    (§B.5.4.1), k = 5.0 for one held on one edge with the other free (§B.5.4.2).

    Three branches, the same shape for either support condition — only k changes:

    * b/t ≤ λ_1 = (B_p − F_cy)/(k·D_p) — **yielding**, F_c = F_cy.
    * λ_1 < b/t < λ_2 = 0.35·B_p/(k·D_p) — **inelastic**, F_c = B_p − k·D_p·(b/t).
    * b/t ≥ λ_2 — **postbuckling**, F_c = 2.27·√(B_p·E)/(k·b/t). A buckled flat element
      keeps carrying load by shedding stress to its stiffer edges, and the ADM lets you
      use that reserve. Note the 1/(b/t), not 1/(b/t)²: it decays far more slowly than
      the elastic plate curve, which is the whole point of the postbuckling branch.

    The elastic plate curve π²E/(k·b/t)² is a *different* quantity, not a branch of this
    one — it is the §B.5.6 elastic local buckling stress F_e, and it is used to decide
    whether member buckling has to be knocked down for interaction. See
    :func:`aluminum_elastic_local_buckling_stress`.

    ``constants`` comes from :func:`aluminum_buckling_constants` for the same alloy.
    """
    if not isinstance(flat_width, Quantity):
        raise ValueError(f"flat_width must be a [length] quantity; got {flat_width!r}")
    if not flat_width.has_dimension("[length]"):
        raise ValueError(f"flat_width must be a [length] quantity; got {flat_width}")
    if not isinstance(thickness, Quantity):
        raise ValueError(f"thickness must be a [length] quantity; got {thickness!r}")
    if not thickness.has_dimension("[length]"):
        raise ValueError(f"thickness must be a [length] quantity; got {thickness}")
    if not isinstance(compressive_yield, Quantity):
        raise ValueError(
            f"compressive_yield must be a [pressure] quantity; got {compressive_yield!r}"
        )
    if not compressive_yield.has_dimension("[pressure]"):
        raise ValueError(
            f"compressive_yield must be a [pressure] quantity; got {compressive_yield}"
        )
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    b = flat_width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    if b <= 0 or t <= 0:
        raise ValueError("flat_width and thickness must be positive")
    fcy = compressive_yield.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if fcy <= 0 or e <= 0:
        raise ValueError("compressive_yield and elastic_modulus must be positive")
    bp = constants.intercept_plate.to("MPa").magnitude
    dp = constants.slope_plate.to("MPa").magnitude
    k = _K_BOTH_EDGES if edge_support is EdgeSupport.BOTH_EDGES else _K_ONE_EDGE
    ratio = b / t
    lambda_1 = (bp - fcy) / (k * dp)
    lambda_2 = _K1_AGED * bp / (k * dp)
    if ratio <= lambda_1:
        stress = fcy
    elif ratio < lambda_2:
        stress = bp - k * dp * ratio
    else:
        stress = _K2_AGED * sqrt(bp * e) / (k * ratio)
    return Quantity(magnitude=stress, unit="MPa")


def aluminum_elastic_local_buckling_stress(
    *,
    flat_width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    edge_support: EdgeSupport = EdgeSupport.BOTH_EDGES,
) -> Quantity:
    """The Aluminum Design Manual §B.5.6 elastic local buckling stress F_e, in MPa.

    The plain elastic plate curve F_e = π²E/(k·b/t)², with the same edge-support
    coefficient k as :func:`aluminum_local_buckling_stress`. This is not the element's
    strength — the element carries more than this, on postbuckling reserve. It is the
    stress at which the element *first* buckles, and its job is the §E.4 question:
    when an element buckles elastically below the stress at which the whole member
    would buckle, the member no longer has the stiffness the column curve assumed, and
    its buckling stress must be knocked down to F_rc = F_c^(1/3)·F_e^(2/3).

    Notice F_cy does not appear. Elastic buckling is a stiffness event, not a strength
    one — a stronger temper does not delay it at all.
    """
    if not isinstance(flat_width, Quantity):
        raise ValueError(f"flat_width must be a [length] quantity; got {flat_width!r}")
    if not flat_width.has_dimension("[length]"):
        raise ValueError(f"flat_width must be a [length] quantity; got {flat_width}")
    if not isinstance(thickness, Quantity):
        raise ValueError(f"thickness must be a [length] quantity; got {thickness!r}")
    if not thickness.has_dimension("[length]"):
        raise ValueError(f"thickness must be a [length] quantity; got {thickness}")
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    b = flat_width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if b <= 0 or t <= 0 or e <= 0:
        raise ValueError("flat_width, thickness and elastic_modulus must be positive")
    k = _K_BOTH_EDGES if edge_support is EdgeSupport.BOTH_EDGES else _K_ONE_EDGE
    return Quantity(magnitude=pi**2 * e / (k * b / t) ** 2, unit="MPa")


def aluminum_lateral_torsional_moment(
    *,
    plastic_moment: Quantity,
    section_modulus: Quantity,
    slenderness: float,
    elastic_modulus: Quantity,
    constants: BucklingConstants,
) -> Quantity:
    """The Aluminum Design Manual §F.4.2 lateral-torsional buckling moment, in kN·m.

    Two branches on the LTB slenderness λ = L_b/r_ye, sharing the same C_c the column
    curve uses:

    * λ ≤ C_c — M_nMB = M_np(1 − λ/C_c) + π²·E·λ·S_c/C_c³, a straight fall from the
      plastic moment M_np at λ = 0 to the elastic curve at C_c, plus the term that lifts
      it back toward the elastic value.
    * λ > C_c — M_nMB = π²·E·S_c/λ², the elastic curve.

    Note the missing 0.85: unlike :func:`aluminum_member_buckling_stress`, the ADM
    applies no out-of-straightness knockdown here. Lateral-torsional buckling is not a
    member-straightness effect, and carrying the 0.85 across from the column curve — the
    obvious mistake, since the two share C_c — would make every beam 15% conservative.

    ``plastic_moment`` M_np and ``section_modulus`` S_c to the compression flange are the
    caller's section properties; ``slenderness`` is L_b/r_ye with r_ye the effective
    radius of gyration from §F.4.2.
    """
    if not isinstance(plastic_moment, Quantity):
        raise ValueError(
            f"plastic_moment must be a [force] * [length] quantity; got {plastic_moment!r}"
        )
    if not plastic_moment.has_dimension("[force] * [length]"):
        raise ValueError(f"plastic_moment must be a moment quantity; got {plastic_moment}")
    if not isinstance(section_modulus, Quantity):
        raise ValueError(
            f"section_modulus must be a [length] ** 3 quantity; got {section_modulus!r}"
        )
    if not section_modulus.has_dimension("[length] ** 3"):
        raise ValueError(f"section_modulus must be a [length]**3 quantity; got {section_modulus}")
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    if slenderness <= 0:
        raise ValueError(f"slenderness must be positive; got {slenderness}")
    mnp = plastic_moment.to("kN*m").magnitude
    sc = section_modulus.to("m**3").magnitude
    e = elastic_modulus.to("kPa").magnitude  # kPa * m^3 = kN*m
    cc = constants.intersection_member
    if mnp <= 0 or sc <= 0 or e <= 0:
        raise ValueError("plastic_moment, section_modulus and elastic_modulus must be positive")
    if slenderness <= cc:
        moment = mnp * (1.0 - slenderness / cc) + pi**2 * e * slenderness * sc / cc**3
    else:
        moment = pi**2 * e * sc / slenderness**2
    return Quantity(magnitude=moment, unit="kN*m")


def aluminum_combined_interaction(
    *,
    axial_ratio: float,
    major_moment_ratio: float,
    minor_moment_ratio: float = 0.0,
) -> float:
    """The Aluminum Design Manual §H.1 interaction value, P/P_c + M_x/M_cx + M_y/M_cy.

    Each argument is a demand over its own available strength, computed on the same
    basis (all three allowable, or all three factored — mixing them is the one way to
    get a wrong answer from a right formula). The ADM's interaction is a plain linear
    sum with no bilinear branch and no second-order magnifier folded in: the member is
    adequate at 1.0 or below, and the value doubles as the utilization.

    That linearity is a real difference from AISC 360's H1-1a/H1-1b pair, which halves
    the axial term in the low-axial region. Aluminum gets no such relief, so a section
    that would pass a steel interaction can fail this one on the same ratios. Returns
    the dimensionless sum.
    """
    for value, name in (
        (axial_ratio, "axial_ratio"),
        (major_moment_ratio, "major_moment_ratio"),
        (minor_moment_ratio, "minor_moment_ratio"),
    ):
        if value < 0:
            raise ValueError(
                f"{name} must be non-negative; got {value}. Interaction ratios are "
                f"magnitudes — a sign-reversed demand still consumes capacity."
            )
    return axial_ratio + major_moment_ratio + minor_moment_ratio


class AluminumCompressionStrength(BaseModel):
    """An Aluminum Design Manual compression screen: what each state allows, and which governs.

    ``yielding``, ``local_buckling`` and ``member_buckling`` are the three §B.5.4/§E.3
    limit-state stresses; ``nominal`` is the smallest and ``governing`` names it.

    ``parent_nominal`` and ``weld_affected_nominal`` carry the same screen run on each
    property set, so a report can show both rather than a single number whose provenance
    the reader has to take on trust. ``weld_affected_governs`` is True when the
    heat-affected zone is what set ``nominal`` — the answer to the question a welded
    aluminum design actually turns on. ``weld_affected_nominal`` is ``None`` for a member
    with no declared welds.

    ``elastic_local_buckling`` is the §B.5.6 stress F_e at which the checked element first
    buckles, and ``local_member_interaction`` is True when it falls below the elastic
    member buckling strength. That is the §E.4 trigger, and when it is up the reduction
    F_rc = F_c^(1/3)·F_e^(2/3) **has been applied** to ``member_buckling`` — the flag says
    the check was made, not that it was skipped. Omitting it would be unconservative in
    exactly the slender-element case where the postbuckling branch is leaned on hardest.
    """

    model_config = ConfigDict(frozen=True)

    yielding: Quantity
    local_buckling: Quantity
    member_buckling: Quantity
    nominal: Quantity
    governing: AluminumLimitState
    parent_nominal: Quantity
    elastic_local_buckling: Quantity
    local_member_interaction: bool = False
    weld_affected_governs: bool = False
    weld_affected_nominal: Quantity | None = None

    def __str__(self) -> str:
        where = " in the weld-affected zone" if self.weld_affected_governs else ""
        return f"ADM nominal {self.nominal} governed by {self.governing.value}{where}"


def _compression_limit_states(
    properties: AlloyProperties,
    *,
    slenderness: float,
    flat_width: Quantity,
    thickness: Quantity,
    edge_support: EdgeSupport,
) -> dict[AluminumLimitState, Quantity]:
    """The three §B.5.4/§E.3 limit-state stresses for one set, with §E.4 applied.

    §E.4: when the element's elastic local buckling stress F_e falls below the member
    buckling strength F_c, the member no longer has the stiffness the column curve
    assumed, and its buckling strength drops to F_rc = F_c^(1/3)·F_e^(2/3).

    F_c here is the §E.3 member buckling *strength*, not the elastic member buckling
    stress. Those coincide above C_c, which is why the ADM's own worked example does not
    distinguish them — but below C_c the elastic stress runs away as 1/λ², so comparing
    against it makes the condition fire on essentially every stocky member and says
    nothing. The strength is bounded by F_cy and the comparison stays meaningful.
    """
    constants = aluminum_buckling_constants(
        compressive_yield=properties.compressive_yield,
        elastic_modulus=properties.elastic_modulus,
        temper_group=properties.temper_group,
    )
    member = aluminum_member_buckling_stress(
        slenderness=slenderness,
        compressive_yield=properties.compressive_yield,
        elastic_modulus=properties.elastic_modulus,
        constants=constants,
    )
    fe = aluminum_elastic_local_buckling_stress(
        flat_width=flat_width,
        thickness=thickness,
        elastic_modulus=properties.elastic_modulus,
        edge_support=edge_support,
    ).magnitude
    fc = member.magnitude
    if fe < fc:
        member = Quantity(magnitude=fc ** (1.0 / 3.0) * fe ** (2.0 / 3.0), unit="MPa")
    return {
        AluminumLimitState.YIELDING: properties.compressive_yield.to("MPa"),
        AluminumLimitState.LOCAL_BUCKLING: aluminum_local_buckling_stress(
            flat_width=flat_width,
            thickness=thickness,
            compressive_yield=properties.compressive_yield,
            elastic_modulus=properties.elastic_modulus,
            constants=constants,
            edge_support=edge_support,
        ),
        AluminumLimitState.MEMBER_BUCKLING: member,
    }


def aluminum_compression_strength(
    *,
    properties: AlloyProperties,
    slenderness: float,
    flat_width: Quantity,
    thickness: Quantity,
    edge_support: EdgeSupport = EdgeSupport.BOTH_EDGES,
    welded: bool = False,
) -> AluminumCompressionStrength | None:
    """Screen a compression member against all three Aluminum Design Manual limit states.

    Runs yielding, local buckling (§B.5.4) and member buckling (§E.3) and returns the
    smallest with its name. ``slenderness`` is the column's kL/r; ``flat_width`` and
    ``thickness`` describe the element whose local buckling is being checked — the most
    slender one, or run the screen once per element and take the least.

    ``welded`` declares that some part of the checked region is within a weld-affected
    zone. When it is set, the screen runs a *second* time on
    ``properties.weld_affected`` and reports the lesser of the two, because the
    heat-affected material is what the member has where it is welded. A 6061-T6
    extrusion loses more than half its compressive yield there, so the weld almost always
    governs — which is exactly the trap this pack exists to make visible.

    Returns ``None``, meaning not evaluated, in the two cases where a number would be a
    lie: a temper this module does not have the buckling table for, and a member declared
    welded whose weld-affected properties were not supplied.
    """
    if not isinstance(properties, AlloyProperties):
        raise ValueError(f"properties must be an AlloyProperties; got {properties!r}")
    if not isinstance(edge_support, EdgeSupport):
        raise ValueError(f"edge_support must be an EdgeSupport; got {edge_support!r}")
    # `min(states, ...)` picks the governing limit state, and min() DROPS a NaN candidate
    # rather than propagating it: a non-finite kL/r poisoned only the member-buckling state
    # and the function reported yielding as governing -- turning a FAIL at 147.5 MPa into a
    # PASS at 241 MPa, 63% above the real capacity, with `member_buckling = nan` sitting in
    # the returned object.
    if not isfinite(slenderness):
        raise ValueError(
            f"slenderness (kL/r) must be finite; got {slenderness}. A non-finite slenderness "
            "poisons one limit state and is then dropped by the min() that picks the "
            "governing one, so a buckling-governed member reports as yielding-governed"
        )
    sets: list[tuple[bool, AlloyProperties]] = [(False, properties)]
    if welded:
        if properties.weld_affected is None:
            return None
        sets.append((True, properties.weld_affected))
    if any(p.temper_group is not TemperGroup.ARTIFICIALLY_AGED for _, p in sets):
        return None

    best: tuple[float, bool, AluminumLimitState, dict[AluminumLimitState, Quantity]] | None = None
    parent_nominal = None
    haz_nominal = None
    for is_haz, props in sets:
        states = _compression_limit_states(
            props,
            slenderness=slenderness,
            flat_width=flat_width,
            thickness=thickness,
            edge_support=edge_support,
        )
        state = min(states, key=lambda s: states[s].magnitude)
        value = states[state].magnitude
        if is_haz:
            haz_nominal = states[state]
        else:
            parent_nominal = states[state]
        if best is None or value < best[0]:
            best = (value, is_haz, state, states)
    assert best is not None and parent_nominal is not None  # noqa: S101 - the loop always runs
    _, governed_by_haz, governing, states = best
    # §E.4: F_e is a stiffness quantity — it has no F_cy in it — so it is the same for
    # the parent metal and the weld-affected zone, and only has to be computed once.
    elastic_local = aluminum_elastic_local_buckling_stress(
        flat_width=flat_width,
        thickness=thickness,
        elastic_modulus=properties.elastic_modulus,
        edge_support=edge_support,
    )
    unreduced = aluminum_member_buckling_stress(
        slenderness=slenderness,
        compressive_yield=properties.compressive_yield,
        elastic_modulus=properties.elastic_modulus,
        constants=aluminum_buckling_constants(
            compressive_yield=properties.compressive_yield,
            elastic_modulus=properties.elastic_modulus,
            temper_group=properties.temper_group,
        ),
    )
    return AluminumCompressionStrength(
        yielding=states[AluminumLimitState.YIELDING],
        local_buckling=states[AluminumLimitState.LOCAL_BUCKLING],
        member_buckling=states[AluminumLimitState.MEMBER_BUCKLING],
        nominal=states[governing],
        governing=governing,
        parent_nominal=parent_nominal,
        elastic_local_buckling=elastic_local,
        local_member_interaction=elastic_local.magnitude < unreduced.magnitude,
        weld_affected_governs=governed_by_haz,
        weld_affected_nominal=haz_nominal,
    )


def aluminum_compression_scorecard(
    name: str,
    *,
    demand_stress: Quantity,
    strength: AluminumCompressionStrength | None,
    required: float = 1.0,
    missing: str = "",
) -> ScorecardEntry:
    """Screen a compressive stress against an Aluminum Design Manual nominal strength.

    The safety factor is the nominal stress over ``demand_stress``, judged against
    ``required``. The detail names the governing limit state and, when the member is
    welded, both the parent and weld-affected nominal stresses with the one that
    governed marked — the two numbers a reviewer of a welded aluminum design wants side
    by side.

    ``strength`` of ``None`` is ``NOT_EVALUATED``, never a pass. ``missing`` says what
    was absent so the message names it; pass the weld-affected properties that were not
    supplied, or the temper whose buckling table is not implemented.
    """
    if strength is None:
        detail = "not evaluated"
        if missing.strip():
            detail = f"{detail} — {missing.strip()}"
        else:
            detail = (
                f"{detail} — the ADM screen could not run on the properties supplied "
                f"(a declared weld with no weld-affected values, or a temper outside "
                f"ADM Table B.4.2)"
            )
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=detail,
            reference=_CLAUSE_ADM,
        )
    if not isinstance(demand_stress, Quantity):
        raise ValueError(f"demand_stress must be a [pressure] quantity; got {demand_stress!r}")
    if not demand_stress.has_dimension("[pressure]"):
        raise ValueError(f"demand_stress must be a [pressure] quantity; got {demand_stress}")
    demand = abs(demand_stress.to("MPa").magnitude)
    nominal = strength.nominal.to("MPa").magnitude
    # Zero demand is a check with nothing to evaluate, not one that passed.
    computed = None if demand == 0 else nominal / demand
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    detail = (
        f"{strength.governing.value} governs: {nominal:.4g} MPa allowed against a "
        f"demand of {demand:.4g} MPa"
    )
    if strength.weld_affected_nominal is not None:
        parent = strength.parent_nominal.to("MPa").magnitude
        haz = strength.weld_affected_nominal.to("MPa").magnitude
        marker = "weld-affected" if strength.weld_affected_governs else "parent metal"
        detail = (
            f"{detail}; parent metal {parent:.4g} MPa, weld-affected {haz:.4g} MPa, "
            f"{marker} governs"
        )
    if strength.local_member_interaction:
        detail = (
            f"{detail}; the element buckles elastically at "
            f"{strength.elastic_local_buckling.to('MPa').magnitude:.4g} MPa, below the "
            f"member buckling strength, so the ADM §E.4 local/member interaction "
            f"reduction F_rc = F_c^(1/3)·F_e^(2/3) has been applied"
        )
    return entry.model_copy(update={"detail": detail, "reference": _CLAUSE_ADM})
