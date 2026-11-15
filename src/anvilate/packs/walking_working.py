"""Walking-working surfaces: guardrails, stairs, fixed ladders and platform edges.

The most-built small structures in industry, and the ones governed by a regulation that
is both public domain and numeric. 29 CFR 1910 Subpart D says a guardrail withstands
200 lbf at any point on its top rail and must not deflect below 39 inches under it; that
a standard stair runs 30 to 50 degrees with risers at most 9.5 inches; that a fixed
ladder's rungs are 10 to 14 inches apart. Those are checks, and until now an engineer
sizing a mezzanine guardrail had every piece of this library *except* the clauses that
decide whether the thing is legal.

Every number in this module was read off the eCFR text on 2026-11-15 and carries its
paragraph. The whole of Subpart D is a work of the United States government, so unlike
the IBC, ASCE 7 or NDS numbers this library refuses to bundle, these ship.

**The regime is declared and never assumed.** 29 CFR 1926 Subpart M governs construction
and says different numbers for several of the same things; a document that declares
construction is refused here rather than screened against the general-industry ones,
because a guardrail passing the wrong regulation is worse than one nobody checked. A
document under a code this library does not carry declares
:attr:`Regime.USER_DECLARED` and supplies its own limits with their source.

What this pack does **not** do: decide whether fall protection is required as a matter of
law, design a fall arrest system, or stand in for the competent person 1910.28 names. It
screens a declared geometry and a declared load against clauses it cites, which is the
same thing the rest of this library does and the same place it stops.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ConfigDict, model_validator

from ..analysis import bending_stress
from ..derivation import Derivation, DerivationAbsence, SymbolValue, Underived
from ..refusal import RefusalError, Remedy
from ..scorecard import (
    CheckStatus,
    Comparison,
    Direction,
    LimitSense,
    RepairHint,
    Scorecard,
    ScorecardEntry,
)
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "SUBPART_D_EDITION",
    "Regime",
    "GuardrailSystem",
    "screen_guardrail",
    "STAIR_ANGLE_RANGE",
    "SHIP_STAIR_ANGLE_RANGE",
    "MAX_RISER",
    "SHIP_RISER_RANGE",
    "MIN_TREAD_DEPTH",
    "SHIP_MIN_TREAD_DEPTH",
    "MIN_STAIR_WIDTH",
    "SHIP_MIN_TREAD_WIDTH",
    "MIN_HEADROOM",
    "MIN_LANDING_DEPTH",
    "LIVE_LOAD_FACTOR",
    "MIN_CONCENTRATED_LOAD",
    "StairKind",
    "StairSystem",
    "screen_stair",
    "RUNG_SPACING_RANGE",
    "MIN_RUNG_CLEAR_WIDTH",
    "MIN_CLEARANCE_BEHIND",
    "MIN_RAIL_EXTENSION",
    "MIN_SIDE_CLEARANCE",
    "MIN_CLIMBING_SIDE_CLEARANCE",
    "FALL_PROTECTION_LADDER_HEIGHT",
    "FALL_PROTECTION_EDGE_HEIGHT",
    "EdgeProtection",
    "LadderFallProtection",
    "FixedLadder",
    "screen_fixed_ladder",
    "PlatformEdge",
    "screen_platform_edge",
]

#: The edition of Subpart D these numbers were read from, as the text states it. Printed
#: in every citation: a clause with no edition is a number somebody will still be reading
#: after it changes.
SUBPART_D_EDITION = "29 CFR 1910 Subpart D (81 FR 82981, as amended 84 FR 68795/68796)"

# --- the numbers, each with the paragraph it came from -------------------------------
#
# Read from https://www.law.cornell.edu/cfr/text/29/1910.29 on 2026-11-15. Written as the
# text writes them — inches and pounds-force — because that is how a reader checks them
# against the regulation, and converted at the point of comparison rather than here.

#: 1910.29(b)(1): top edge height 42 in ± 3 in above the walking-working surface.
TOP_RAIL_HEIGHT = Quantity(magnitude=42.0, unit="inch")
TOP_RAIL_TOLERANCE = Quantity(magnitude=3.0, unit="inch")
#: 1910.29(b)(3): 200 lbf downward or outward within 2 in of the top edge, at any point.
TOP_RAIL_FORCE = Quantity(magnitude=200.0, unit="lbf")
#: 1910.29(b)(4): under that load the top rail may not deflect below 39 in.
DEFLECTED_HEIGHT_FLOOR = Quantity(magnitude=39.0, unit="inch")
#: 1910.29(b)(5): 150 lbf on a midrail or other intermediate member, any direction, any point.
MIDRAIL_FORCE = Quantity(magnitude=150.0, unit="lbf")
#: 1910.29(k)(1)(ii): toeboards at least 3.5 in high from their top edge to the surface.
TOEBOARD_HEIGHT = Quantity(magnitude=3.5, unit="inch")
#: 1910.29(k)(1)(vi): 50 lbf on a toeboard, any downward or outward direction, any point.
TOEBOARD_FORCE = Quantity(magnitude=50.0, unit="lbf")

_GUARDRAIL_SOURCE = "the guardrail as declared: its heights, its post spacing and its section"


class _WalkingWorkingInputError(RefusalError, ValueError):
    """A walking-working-surface input that cannot be used without correction.

    A ``ValueError`` as well as a refusal, which is the convention every other pack
    keeps: raised inside a pydantic validator a bare ``RefusalError`` is a
    ``RuntimeError`` and propagates past the handler a document reader has for a bad
    field, so the document gets an internal error where it should get a refusal naming
    the field.
    """


def _refuse(
    message: str, *, subject: str, source: str = _GUARDRAIL_SOURCE
) -> _WalkingWorkingInputError:
    return _WalkingWorkingInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class Regime(StrEnum):
    """Which regulation a walking-working surface is screened against.

    Declared, never inferred. The three are not interchangeable: 1926 Subpart M says
    different numbers for several of the same things, and a guardrail that passes the
    wrong regulation is worse than one nobody checked.
    """

    #: 29 CFR 1910 Subpart D. The numbers in this module.
    GENERAL_INDUSTRY = "us_general_industry"
    #: 29 CFR 1926 Subparts M and X. Public domain and not read into this library yet, so
    #: a document declaring it is refused rather than screened against 1910's numbers.
    CONSTRUCTION = "us_construction"
    #: Any other code — a building code, another jurisdiction. The document supplies its
    #: own limits with their source, and this pack checks nothing it was not given.
    USER_DECLARED = "user_declared"


def _general_industry(regime: Regime, element: str) -> None:
    """Refuse a regime whose numbers this module does not carry."""
    if regime is Regime.GENERAL_INDUSTRY:
        return
    if regime is Regime.CONSTRUCTION:
        raise _refuse(
            f"this {element} declares the US construction regime, and the numbers in this "
            f"module are 29 CFR 1910 Subpart D's — general industry. 1926 Subparts M and X "
            f"say different numbers for several of the same things, and screening a "
            f"construction guardrail against general-industry limits would pass it under a "
            f"regulation that does not govern it",
            subject="regime",
            source="29 CFR 1926 Subpart M, read and anchored, or the general-industry regime",
        )
    raise _refuse(
        f"this {element} declares a user-declared regime, so there is no bundled limit to "
        f"screen it against. Supply the code's own limits with their source, or declare "
        f"the general-industry regime to be screened against 29 CFR 1910 Subpart D",
        subject="regime",
        source="the code the document is designed to, with its clause",
    )


class GuardrailSystem(GuardedInputs):
    """A guardrail run, and what its 1910.29 criteria need.

    ``post_spacing`` is the distance between posts, which is what turns the regulation's
    "at any point along the top rail" into a worst case: the 200 lbf lands mid-span
    between two posts, where the rail is weakest, and at the top of a post, where the
    post is. Both are screened.

    ``post_height`` is the top rail's height above the walking-working surface, which is
    both the geometry 1910.29(b)(1) limits and the lever arm the 200 lbf acts on.

    ``toeboard_height`` is ``None`` on a run with no toeboard, and the toeboard entries
    are then absent rather than passing: a check that did not apply and a check that
    passed are different facts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    regime: Regime
    post_height: Quantity
    post_spacing: Quantity
    post_section_modulus: Quantity
    post_second_moment: Quantity
    yield_strength: Quantity
    elastic_modulus: Quantity
    rail_section_modulus: Quantity
    midrail_height: Quantity | None = None
    toeboard_height: Quantity | None = None
    toeboard_section_modulus: Quantity | None = None

    @model_validator(mode="after")
    def _dimensions_are_what_they_say(self) -> GuardrailSystem:
        for value, name, dimension in (
            (self.post_height, "post_height", "[length]"),
            (self.post_spacing, "post_spacing", "[length]"),
            (self.post_section_modulus, "post_section_modulus", "[length] ** 3"),
            (self.post_second_moment, "post_second_moment", "[length] ** 4"),
            (self.yield_strength, "yield_strength", "[pressure]"),
            (self.elastic_modulus, "elastic_modulus", "[pressure]"),
            (self.rail_section_modulus, "rail_section_modulus", "[length] ** 3"),
            (self.midrail_height, "midrail_height", "[length]"),
            (self.toeboard_height, "toeboard_height", "[length]"),
            (self.toeboard_section_modulus, "toeboard_section_modulus", "[length] ** 3"),
        ):
            if value is None:
                continue
            if not value.has_dimension(dimension):
                raise _refuse(f"{name} is a {dimension}; got {value.dimensionality}", subject=name)
            if value.magnitude <= 0:
                raise _refuse(f"{name} is positive; got {value}", subject=name)
        if (
            self.midrail_height is not None
            and self.midrail_height.to("mm").magnitude >= self.post_height.to("mm").magnitude
        ):
            raise _refuse(
                f"the midrail is at {self.midrail_height} and the top rail at "
                f"{self.post_height}; a midrail at or above the top rail is not an "
                f"intermediate member",
                subject="midrail_height",
            )
        if self.toeboard_section_modulus is not None and self.toeboard_height is None:
            raise _refuse(
                "the guardrail states a toeboard section and no toeboard height, so there "
                "is no toeboard to screen and the section would be checked against nothing",
                subject="toeboard_height",
            )
        return self


def _clause(paragraph: str, what: str) -> str:
    return f"29 CFR 1910.{paragraph} ({what}) — {SUBPART_D_EDITION}"


def _underived(reason: str) -> Underived:
    return Underived(kind=DerivationAbsence.LOOKUP, reason=reason)


def _height_entry(guardrail: GuardrailSystem) -> ScorecardEntry:
    """1910.29(b)(1): 42 in ± 3 in, and over 45 in allowed only on every other criterion."""
    height = guardrail.post_height.to("inch").magnitude
    nominal = TOP_RAIL_HEIGHT.to("inch").magnitude
    tolerance = TOP_RAIL_TOLERANCE.to("inch").magnitude
    low, high = nominal - tolerance, nominal + tolerance
    if height < low:
        status, said = CheckStatus.FAIL, f"below the {low:g} in floor"
    elif height > high:
        # The text allows it, and only if everything else in (b) is met — which this card
        # is in the middle of deciding. A warning and not a pass: the permission is real
        # and it is conditional on a verdict nobody has reached yet.
        status, said = (
            CheckStatus.WARNING,
            (
                f"above the {high:g} in that (b)(1) states, which the clause permits only if "
                f"every other criterion of paragraph (b) is met"
            ),
        )
    else:
        status, said = CheckStatus.PASS, f"within {nominal:g} in ± {tolerance:g} in"
    return ScorecardEntry(
        name="guardrail top rail height",
        status=status,
        detail=f"top rail at {guardrail.post_height}, {said}",
        reference=_clause("29(b)(1)", "top rail height"),
        comparison=Comparison(
            measured=guardrail.post_height,
            limit=Quantity(magnitude=high, unit="inch"),
            sense=LimitSense.AT_MOST,
            measured_label="top rail height",
            limit_label="the top of the band the clause states",
        ),
        underived=_underived(
            "the clause states a height band and the check is the comparison; there is no "
            "arithmetic between the two numbers"
        ),
    )


#: What a repair hint on one of these says it came from. A noun phrase: the renderer
#: prints it after "— from the ", and a semicolon there would join two clauses into a
#: sentence the surrounding line is not.
PROVENANCE = (
    "section modulus that puts the clause's force at the required margin, where the "
    "stress is linear in 1/Z"
)


def _eighth_span(guardrail: GuardrailSystem) -> Quantity:
    """One eighth of the post spacing: the lever a rail continuous over its posts has."""
    return Quantity(magnitude=guardrail.post_spacing.to("mm").magnitude / 8.0, unit="mm")


def _repaired(
    entry: ScorecardEntry,
    *,
    hint: RepairHint,
) -> ScorecardEntry:
    """Attach a repair hint to a failing entry, and leave a passing one alone."""
    if entry.status is not CheckStatus.FAIL:
        return entry
    return entry.model_copy(update={"repair_hint": hint})


def _section_for(section_modulus: Quantity, computed: float, required: float) -> float:
    """The section modulus that puts a failing bending check at the required margin.

    Exact: the stress is linear in 1/Z, so the factor scales with Z.
    """
    return section_modulus.to("mm**3").magnitude * required / computed


def _strength_entry(
    name: str,
    *,
    force: Quantity,
    lever: Quantity,
    section_modulus: Quantity,
    yield_strength: Quantity,
    paragraph: str,
    what: str,
    required_safety_factor: float,
    lever_description: str,
) -> ScorecardEntry:
    """One member's bending check under a stated regulation force at a stated lever arm."""
    moment = Quantity(magnitude=force.to("N").magnitude * lever.to("m").magnitude, unit="N*m")
    stress = bending_stress(moment=moment, section_modulus=section_modulus)
    computed = yield_strength.to("MPa").magnitude / stress.to("MPa").magnitude
    reference = _clause(paragraph, what)
    entry = ScorecardEntry.from_safety_factor(
        name, computed=computed, required=required_safety_factor
    ).model_copy(
        update={
            "reference": reference,
            "detail": (
                f"{stress.to('MPa').magnitude:.1f} MPa from the clause's "
                f"{force.to('lbf').magnitude:g} lbf at {lever}, against "
                f"{yield_strength} yield"
            ),
            "derivation": Derivation(
                symbolic="U = F_y/(P·L/Z)",
                inputs=(
                    SymbolValue(
                        symbol="P",
                        description=f"the force 1910.{paragraph} states",
                        value=force,
                        unit="N",
                    ),
                    SymbolValue(
                        symbol="L",
                        description=lever_description,
                        value=lever,
                        unit="mm",
                    ),
                    SymbolValue(
                        symbol="Z",
                        description="elastic section modulus of the member in bending",
                        value=section_modulus,
                        unit="mm**3",
                    ),
                    SymbolValue(
                        symbol="F_y",
                        description="specified minimum yield strength",
                        value=yield_strength,
                        unit="MPa",
                    ),
                ),
                result=SymbolValue(
                    symbol="U",
                    description="yield strength as a multiple of the bending stress",
                    value=computed,
                ),
                citation=reference,
            ),
        }
    )
    return entry


def _deflection_entry(guardrail: GuardrailSystem, force: Quantity) -> ScorecardEntry:
    """1910.29(b)(4): under the 200 lbf the top rail may not drop below 39 in.

    The post as a cantilever, δ = P·h³/3EI, which is the deflection the clause's own test
    would measure at the top of a post. The rail's own sag between posts adds to it and is
    not in this number; a run whose posts alone eat the allowance has already failed, and
    one that passes on the posts is told what was and was not included.
    """
    height = guardrail.post_height
    deflection = Quantity(
        magnitude=(
            force.to("N").magnitude
            * height.to("m").magnitude ** 3
            / (
                3.0
                * guardrail.elastic_modulus.to("Pa").magnitude
                * guardrail.post_second_moment.to("m**4").magnitude
            )
        ),
        unit="m",
    )
    remaining = Quantity(
        magnitude=height.to("mm").magnitude - deflection.to("mm").magnitude, unit="mm"
    )
    reference = _clause("29(b)(4)", "deflected height under the 200 lbf load")
    comparison = Comparison(
        measured=remaining,
        limit=DEFLECTED_HEIGHT_FLOOR,
        sense=LimitSense.AT_LEAST,
        measured_label="deflected top rail height",
        limit_label="the deflected-height floor the clause states",
    )
    return ScorecardEntry(
        name="guardrail deflected height",
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=(
            f"{comparison.sentence()}; the post deflects "
            f"{deflection.to('mm').magnitude:.1f} mm under the clause's "
            f"{force.to('lbf').magnitude:g} lbf. The rail's own sag between posts is not "
            f"in this number"
        ),
        reference=reference,
        comparison=comparison,
        derivation=Derivation(
            symbolic="h_def = h − P·h³/(3·E·I)",
            inputs=(
                SymbolValue(symbol="P", description="the 200 lbf of (b)(3)", value=force, unit="N"),
                SymbolValue(symbol="h", description="top rail height", value=height, unit="mm"),
                SymbolValue(
                    symbol="E",
                    description="elastic modulus of the post",
                    value=guardrail.elastic_modulus,
                    unit="MPa",
                ),
                SymbolValue(
                    symbol="I",
                    description="second moment of area of the post",
                    value=guardrail.post_second_moment,
                    unit="mm**4",
                ),
            ),
            result=SymbolValue(
                symbol="h_def",
                description="top rail height under the load",
                value=remaining,
                unit="mm",
            ),
            citation=reference,
        ),
    )


def screen_guardrail(
    guardrail: GuardrailSystem, *, required_safety_factor: float = 1.0
) -> Scorecard:
    """Screen a :class:`GuardrailSystem` against 29 CFR 1910.29 and return its card.

    Five criteria where the run has the members for them: the top rail's height, its
    strength under 200 lbf at the worst point, the deflected height under that load, the
    midrail under 150 lbf, and the toeboard's height and 50 lbf. A run with no midrail or
    no toeboard gets no entry for it — a check that did not apply and a check that passed
    are different facts, and the card should not say the second when it means the first.

    ``required_safety_factor`` is 1.0 by default and that is deliberate: 1910.29 states a
    force the system must withstand *without failure*, not a load to be factored. A
    designer wanting margin on top of the regulation passes it here, and the card says so.
    """
    _general_industry(guardrail.regime, "guardrail")
    entries = [_height_entry(guardrail)]
    post = _strength_entry(
        "guardrail post under the top rail load",
        force=TOP_RAIL_FORCE,
        lever=guardrail.post_height,
        section_modulus=guardrail.post_section_modulus,
        yield_strength=guardrail.yield_strength,
        paragraph="29(b)(3)",
        what="200 lbf at the top rail",
        required_safety_factor=required_safety_factor,
        lever_description="post height, the lever the top rail load acts on",
    )
    entries.append(
        _repaired(
            post,
            hint=RepairHint.solved(
                "post_section_modulus",
                direction=Direction.INCREASE,
                value=_section_for(
                    guardrail.post_section_modulus,
                    post.safety_factor or 1.0,
                    required_safety_factor,
                ),
                unit="mm**3",
                provenance=PROVENANCE,
            ),
        )
    )
    rail = _strength_entry(
        "guardrail top rail between posts",
        force=TOP_RAIL_FORCE,
        # A rail continuous over its posts, loaded at mid-span: M = P·L/8 rather than
        # P·L/4. The quarter is the simply supported case, and a run whose rail is a
        # single simply supported span between two posts is not what (b)(3) is written
        # against; the lever below carries the eighth.
        lever=_eighth_span(guardrail),
        section_modulus=guardrail.rail_section_modulus,
        yield_strength=guardrail.yield_strength,
        paragraph="29(b)(3)",
        what="200 lbf at any point along the top rail",
        required_safety_factor=required_safety_factor,
        lever_description=(
            "one eighth of the post spacing: the mid-span moment of a rail continuous "
            "over its posts under a point load"
        ),
    )
    entries.append(
        _repaired(
            rail,
            hint=RepairHint.solved(
                "rail_section_modulus",
                direction=Direction.INCREASE,
                value=_section_for(
                    guardrail.rail_section_modulus,
                    rail.safety_factor or 1.0,
                    required_safety_factor,
                ),
                unit="mm**3",
                provenance=PROVENANCE,
            ),
        )
    )
    entries.append(_deflection_entry(guardrail, TOP_RAIL_FORCE))
    if guardrail.midrail_height is not None:
        midrail = _strength_entry(
            "guardrail midrail",
            force=MIDRAIL_FORCE,
            lever=_eighth_span(guardrail),
            section_modulus=guardrail.rail_section_modulus,
            yield_strength=guardrail.yield_strength,
            paragraph="29(b)(5)",
            what="150 lbf on an intermediate member",
            required_safety_factor=required_safety_factor,
            lever_description=(
                "one eighth of the post spacing, as for the top rail: the midrail runs "
                "over the same posts"
            ),
        )
        entries.append(
            _repaired(
                midrail,
                hint=RepairHint.solved(
                    "rail_section_modulus",
                    direction=Direction.INCREASE,
                    value=_section_for(
                        guardrail.rail_section_modulus,
                        midrail.safety_factor or 1.0,
                        required_safety_factor,
                    ),
                    unit="mm**3",
                    provenance=PROVENANCE,
                ),
            )
        )
    if guardrail.toeboard_height is not None:
        entries.append(_toeboard_height_entry(guardrail))
        if guardrail.toeboard_section_modulus is not None:
            toeboard = _strength_entry(
                "guardrail toeboard",
                force=TOEBOARD_FORCE,
                lever=_eighth_span(guardrail),
                section_modulus=guardrail.toeboard_section_modulus,
                yield_strength=guardrail.yield_strength,
                paragraph="29(k)(1)(vi)",
                what="50 lbf on a toeboard",
                required_safety_factor=required_safety_factor,
                lever_description="one eighth of the post spacing",
            )
            entries.append(
                _repaired(
                    toeboard,
                    hint=RepairHint.solved(
                        "toeboard_section_modulus",
                        direction=Direction.INCREASE,
                        value=_section_for(
                            guardrail.toeboard_section_modulus,
                            toeboard.safety_factor or 1.0,
                            required_safety_factor,
                        ),
                        unit="mm**3",
                        provenance=PROVENANCE,
                    ),
                )
            )
    return Scorecard(entries=tuple(entries))


def _toeboard_height_entry(guardrail: GuardrailSystem) -> ScorecardEntry:
    """1910.29(k)(1)(ii): at least 3.5 in from the toeboard's top edge to the surface."""
    assert guardrail.toeboard_height is not None
    comparison = Comparison(
        measured=guardrail.toeboard_height,
        limit=TOEBOARD_HEIGHT,
        sense=LimitSense.AT_LEAST,
        measured_label="toeboard height",
        limit_label="the height the clause states",
    )
    return ScorecardEntry(
        name="guardrail toeboard height",
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=(
            f"{comparison.sentence()}. A lower figure applies around vehicle repair, "
            f"service or assembly pits, which this card does not know it is"
        ),
        reference=_clause("29(k)(1)(ii)", "toeboard height"),
        comparison=comparison,
        underived=_underived(
            "the clause states a height and the check is the comparison; there is no "
            "arithmetic between the two numbers"
        ),
    )


# --- stairways, 29 CFR 1910.25 --------------------------------------------------------
#
# Read from https://www.law.cornell.edu/cfr/text/29/1910.25 on 2026-11-15.

#: 1910.25(c)(1): standard stairs are installed at 30 to 50 degrees from the horizontal.
STAIR_ANGLE_RANGE = (30.0, 50.0)
#: 1910.25(e)(1): ship stairs, 50 to 70 degrees.
SHIP_STAIR_ANGLE_RANGE = (50.0, 70.0)
#: 1910.25(c)(2): maximum riser height 9.5 in on a standard stair.
MAX_RISER = Quantity(magnitude=9.5, unit="inch")
#: 1910.25(e)(2): a ship stair has **open** risers with a vertical rise between tread
#: surfaces of 6.5 to 12 in — a band, and a wider one at the top than a standard stair's
#: limit. Applying (c)(2)'s 9.5 in to a ship stair fails a riser the clause allows.
SHIP_RISER_RANGE = (
    Quantity(magnitude=6.5, unit="inch"),
    Quantity(magnitude=12.0, unit="inch"),
)
#: 1910.25(c)(3): minimum tread depth 9.5 in.
MIN_TREAD_DEPTH = Quantity(magnitude=9.5, unit="inch")
#: 1910.25(e)(3): a ship stair's minimum tread depth is 4 in.
SHIP_MIN_TREAD_DEPTH = Quantity(magnitude=4.0, unit="inch")
#: 1910.25(c)(4): minimum width 22 in between vertical barriers.
MIN_STAIR_WIDTH = Quantity(magnitude=22.0, unit="inch")
#: 1910.25(e)(4): a ship stair's minimum tread width is 18 in.
SHIP_MIN_TREAD_WIDTH = Quantity(magnitude=18.0, unit="inch")
#: 1910.25(b)(2): vertical clearance above any tread, at least 6 ft 8 in.
MIN_HEADROOM = Quantity(magnitude=80.0, unit="inch")
#: 1910.25(b)(4): landings at least the stair's width and at least 30 in deep.
MIN_LANDING_DEPTH = Quantity(magnitude=30.0, unit="inch")
#: 1910.25(b)(6): at least five times the anticipated live load, and never less than a
#: 1,000 lb concentrated load at any point. Both halves, because the clause is both.
LIVE_LOAD_FACTOR = 5.0
MIN_CONCENTRATED_LOAD = Quantity(magnitude=1000.0, unit="lbf")

_STAIR_SOURCE = "the stair as declared: its geometry, its loads and its kind"


class StairKind(StrEnum):
    """Which of 1910.25's stair paragraphs governs. The angles and treads differ."""

    #: (c) standard stairs — the default, and the one (b)(7) says to use.
    STANDARD = "standard"
    #: (e) ship stairs, permitted only where (b)(8) allows.
    SHIP = "ship"


class StairSystem(GuardedInputs):
    """A run of stairs, and what 1910.25 needs to judge it.

    ``anticipated_live_load`` is the load the stair is designed for, which is the
    document's to state: (b)(6) asks for five times it *and* never less than a 1,000 lb
    concentrated load, so the governing one of the two is found rather than assumed.
    ``tread_capacity`` is what one tread can actually carry, which is what both are
    screened against.

    ``landing_depth`` is ``None`` on a run with no landing, and the landing entries are
    then absent rather than passing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    regime: Regime
    kind: StairKind = StairKind.STANDARD
    angle: Quantity
    riser_height: Quantity
    tread_depth: Quantity
    width: Quantity
    headroom: Quantity
    tread_capacity: Quantity
    anticipated_live_load: Quantity
    landing_depth: Quantity | None = None

    @model_validator(mode="after")
    def _dimensions_are_what_they_say(self) -> StairSystem:
        for value, name, dimension in (
            (self.riser_height, "riser_height", "[length]"),
            (self.tread_depth, "tread_depth", "[length]"),
            (self.width, "width", "[length]"),
            (self.headroom, "headroom", "[length]"),
            (self.tread_capacity, "tread_capacity", "[force]"),
            (self.anticipated_live_load, "anticipated_live_load", "[force]"),
            (self.landing_depth, "landing_depth", "[length]"),
        ):
            if value is None:
                continue
            if not value.has_dimension(dimension):
                raise _refuse(
                    f"{name} is a {dimension}; got {value.dimensionality}",
                    subject=name,
                    source=_STAIR_SOURCE,
                )
            if value.magnitude <= 0:
                raise _refuse(
                    f"{name} is positive; got {value}", subject=name, source=_STAIR_SOURCE
                )
        if str(self.angle.pint.dimensionality) != "dimensionless":
            raise _refuse(
                f"angle is an angle; got {self.angle.dimensionality}",
                subject="angle",
                source=_STAIR_SOURCE,
            )
        degrees = self.angle.to("degree").magnitude
        if not 0.0 < degrees < 90.0:
            raise _refuse(
                f"a stair's angle from the horizontal is between 0 and 90 degrees; got "
                f"{degrees:g}. At 90 it is a ladder, and 1910.23 governs that",
                subject="angle",
                source=_STAIR_SOURCE,
            )
        return self


def _band_entry(
    name: str,
    measured: Quantity,
    *,
    low: float | None,
    high: float | None,
    unit: str,
    paragraph: str,
    what: str,
    label: str,
) -> ScorecardEntry:
    """One geometry rule: a measured dimension against the band the clause states.

    The comparison names **the bound the verdict turned on**, not an arbitrary one. A
    two-sided band — a stair's 30 to 50 degrees — reported against its upper bound alone
    would render a 25-degree stair as "25 deg vs at most 50 deg" beside a FAIL, which is
    a sentence that contradicts the verdict printed above it. Nothing in the library
    refuses that pair, so it is this function's job not to build one.
    """
    value = measured.to(unit).magnitude
    if low is not None and value < low:
        status, said = CheckStatus.FAIL, f"below the {low:g} {unit} the clause states"
        limit, sense = Quantity(magnitude=low, unit=unit), LimitSense.AT_LEAST
    elif high is not None and value > high:
        status, said = CheckStatus.FAIL, f"above the {high:g} {unit} the clause states"
        limit, sense = Quantity(magnitude=high, unit=unit), LimitSense.AT_MOST
    elif high is not None:
        status, said = CheckStatus.PASS, _within(low, high, unit)
        limit, sense = Quantity(magnitude=high, unit=unit), LimitSense.AT_MOST
    else:
        status, said = CheckStatus.PASS, _within(low, high, unit)
        limit, sense = Quantity(magnitude=low or 0.0, unit=unit), LimitSense.AT_LEAST
    return ScorecardEntry(
        name=name,
        status=status,
        detail=f"{label} {measured}, {said}",
        reference=_clause(paragraph, what),
        comparison=Comparison(
            # In the clause's own unit, the one the status above was decided in. Leaving
            # the measured value in the document's unit made `passes()` convert a second
            # time, and a landing exactly as deep as its stair is wide came out as a
            # passing entry whose own comparison said it failed.
            measured=Quantity(magnitude=value, unit=unit),
            limit=limit,
            sense=sense,
            measured_label=label,
            limit_label="the limit the clause states",
        ),
        underived=_underived(
            "the clause states a dimension and the check is the comparison; there is no "
            "arithmetic between the two numbers"
        ),
    )


def _within(low: float | None, high: float | None, unit: str) -> str:
    """What a passing dimension is inside, said as the clause says it."""
    if low is not None and high is not None:
        return f"inside the {low:g} to {high:g} {unit} the clause states"
    if high is not None:
        return f"at or under the {high:g} {unit} the clause states"
    return f"at or over the {low:g} {unit} the clause states"


def screen_stair(stair: StairSystem, *, required_safety_factor: float = 1.0) -> Scorecard:
    """Screen a :class:`StairSystem` against 29 CFR 1910.25 and return its card.

    The geometry rules of (b) and of the paragraph the stair's kind selects, then the
    load rule of (b)(6) — which is **two** requirements, not one: five times the
    anticipated live load, and never less than a 1,000 lb concentrated load. The
    governing one is found and named, because a stair sized on the five-times rule alone
    can still fail the floor, and a card reporting only one of the two has answered half
    the clause.
    """
    _general_industry(stair.regime, "stair")
    ship = stair.kind is StairKind.SHIP
    low, high = SHIP_STAIR_ANGLE_RANGE if ship else STAIR_ANGLE_RANGE
    entries = [
        _band_entry(
            "stair angle",
            stair.angle,
            low=low,
            high=high,
            unit="degree",
            paragraph="25(e)(1)" if ship else "25(c)(1)",
            what=f"{'ship' if ship else 'standard'} stair slope",
            label="slope from the horizontal",
        ),
        _band_entry(
            "stair riser height",
            stair.riser_height,
            low=SHIP_RISER_RANGE[0].to("inch").magnitude if ship else None,
            high=(SHIP_RISER_RANGE[1] if ship else MAX_RISER).to("inch").magnitude,
            unit="inch",
            paragraph="25(e)(2)" if ship else "25(c)(2)",
            what="rise between tread surfaces" if ship else "maximum riser height",
            label="riser height",
        ),
        _band_entry(
            "stair tread depth",
            stair.tread_depth,
            low=(SHIP_MIN_TREAD_DEPTH if ship else MIN_TREAD_DEPTH).to("inch").magnitude,
            high=None,
            unit="inch",
            paragraph="25(e)(3)" if ship else "25(c)(3)",
            what="minimum tread depth",
            label="tread depth",
        ),
        _band_entry(
            "stair width",
            stair.width,
            low=(SHIP_MIN_TREAD_WIDTH if ship else MIN_STAIR_WIDTH).to("inch").magnitude,
            high=None,
            unit="inch",
            paragraph="25(e)(4)" if ship else "25(c)(4)",
            # The two clauses measure different things and the card says which: (c)(4) is
            # the stair's width between vertical barriers, (e)(4) is the tread's own width.
            what="minimum tread width" if ship else "minimum width between vertical barriers",
            label="tread width" if ship else "width between vertical barriers",
        ),
        _band_entry(
            "stair headroom",
            stair.headroom,
            low=MIN_HEADROOM.to("inch").magnitude,
            high=None,
            unit="inch",
            paragraph="25(b)(2)",
            what="vertical clearance above any tread",
            label="vertical clearance above the tread",
        ),
    ]
    if stair.landing_depth is not None:
        entries.append(
            _band_entry(
                "stair landing depth",
                stair.landing_depth,
                low=MIN_LANDING_DEPTH.to("inch").magnitude,
                high=None,
                unit="inch",
                paragraph="25(b)(4)",
                what="landing depth in the direction of travel",
                label="landing depth",
            )
        )
        entries.append(
            _band_entry(
                "stair landing width",
                stair.landing_depth,
                low=stair.width.to("inch").magnitude,
                high=None,
                unit="inch",
                paragraph="25(b)(4)",
                what="landing at least the width of the stair",
                label="landing depth against the stair's own width",
            )
        )
    entries.append(_tread_load_entry(stair, required_safety_factor))
    return Scorecard(entries=tuple(entries))


def _tread_load_entry(stair: StairSystem, required_safety_factor: float) -> ScorecardEntry:
    """1910.25(b)(6): five times the live load, and never less than 1,000 lb.

    Two requirements in one sentence, and the governing one is whichever is larger. A
    card that screened only the five-times rule would pass a lightly loaded stair that
    cannot take the concentrated load the clause floors it at, which is exactly the case
    the floor was written for.
    """
    factored = Quantity(
        magnitude=stair.anticipated_live_load.to("N").magnitude * LIVE_LOAD_FACTOR, unit="N"
    )
    floor = MIN_CONCENTRATED_LOAD
    governing, why = (
        (factored, f"{LIVE_LOAD_FACTOR:g} times the declared live load")
        if factored.to("N").magnitude >= floor.to("N").magnitude
        else (floor, "the concentrated-load floor the clause states")
    )
    computed = stair.tread_capacity.to("N").magnitude / governing.to("N").magnitude
    reference = _clause("25(b)(6)", "five times the live load, never less than 1,000 lb")
    entry = ScorecardEntry.from_safety_factor(
        "stair tread load", computed=computed, required=required_safety_factor
    ).model_copy(
        update={
            "reference": reference,
            "detail": (
                f"tread capacity {stair.tread_capacity} against {governing}, which is "
                f"{why}; the other half of the clause asks for "
                f"{floor if governing is factored else factored}"
            ),
            "derivation": Derivation(
                symbolic="U = R/P_req",
                inputs=(
                    SymbolValue(
                        symbol="R",
                        description="what one tread can carry",
                        value=stair.tread_capacity,
                        unit="N",
                    ),
                    SymbolValue(
                        symbol="P_req",
                        description=f"the governing half of (b)(6): {why}",
                        value=governing,
                        unit="N",
                    ),
                ),
                result=SymbolValue(
                    symbol="U",
                    description="tread capacity as a multiple of what the clause requires",
                    value=computed,
                ),
                citation=reference,
            ),
        }
    )
    if entry.status is CheckStatus.FAIL:
        return entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "tread_capacity",
                    direction=Direction.INCREASE,
                    value=governing.to("N").magnitude * required_safety_factor,
                    unit="N",
                    provenance=(
                        "governing half of 1910.25(b)(6) at the required margin, which the "
                        "tread has to carry"
                    ),
                )
            }
        )
    return entry


# --- fixed ladders, 29 CFR 1910.23 and 1910.28(b)(9) ----------------------------------
#
# Read from https://www.law.cornell.edu/cfr/text/29/1910.23 on 2026-11-15.

#: 1910.23(b)(2): rungs spaced not less than 10 in and not more than 14 in on centres.
RUNG_SPACING_RANGE = (
    Quantity(magnitude=10.0, unit="inch"),
    Quantity(magnitude=14.0, unit="inch"),
)
#: 1910.23(b)(4): minimum clear width 16 in for a fixed ladder, before any safety system.
MIN_RUNG_CLEAR_WIDTH = Quantity(magnitude=16.0, unit="inch")
#: 1910.23(d)(2): at least 7 in perpendicular from the rung centreline to the nearest
#: permanent object behind the ladder.
MIN_CLEARANCE_BEHIND = Quantity(magnitude=7.0, unit="inch")
#: 1910.23(d)(4): side rails extend at least 42 in above the access level or landing.
MIN_RAIL_EXTENSION = Quantity(magnitude=42.0, unit="inch")
#: 1910.23(d)(13)(i) and (ii): without a cage or well, 15 in clear each side of the
#: centreline and 30 in perpendicular on the climbing side.
MIN_SIDE_CLEARANCE = Quantity(magnitude=15.0, unit="inch")
MIN_CLIMBING_SIDE_CLEARANCE = Quantity(magnitude=30.0, unit="inch")
#: 1910.28(b)(9): a fixed ladder extending **more than** 24 ft above a lower level needs
#: a personal fall arrest system, a ladder safety system, a cage or a well.
FALL_PROTECTION_LADDER_HEIGHT = Quantity(magnitude=24.0, unit="foot")
#: 1910.28(b)(1)(i): an unprotected side or edge 4 ft or more above a lower level needs
#: fall protection. **Or more**, where the ladder rule is *more than* — the two clauses
#: differ at the boundary and the code keeps them apart.
FALL_PROTECTION_EDGE_HEIGHT = Quantity(magnitude=4.0, unit="foot")

_LADDER_SOURCE = "the fixed ladder as declared: its rungs, its clearances and its height"


class EdgeProtection(StrEnum):
    """What an unprotected side or edge has, per 1910.28(b)(1)(i).

    ``GUARDRAIL`` is ``"guardrail"`` and not ``"guardrail_system"``, which is the
    clause's own phrase, because ``guardrail_system`` is already this pack's **element
    tag**: an edge whose protection read `guardrail_system` would look like it named the
    element rather than described itself, and the refusal that lists every element tag
    would then carry what looks like an enum value where English belongs. The suite's
    machine-spelling gate found that before a reader did.
    """

    NONE = "none"
    GUARDRAIL = "guardrail"
    SAFETY_NET = "safety_net_system"
    PERSONAL_FALL_PROTECTION = "personal_fall_protection_system"


class LadderFallProtection(StrEnum):
    """What a fixed ladder over 24 ft has, per 1910.28(b)(9)(i)."""

    NONE = "none"
    PERSONAL_FALL_ARREST = "personal_fall_arrest_system"
    LADDER_SAFETY_SYSTEM = "ladder_safety_system"
    CAGE_OR_WELL = "cage_or_well"


class FixedLadder(GuardedInputs):
    """A fixed ladder, and what 1910.23 and 1910.28(b)(9) need to judge it.

    ``climbing_side_clearance`` and ``side_clearance`` are only read where the ladder has
    no cage or well — 1910.23(d)(13) states them for exactly that case — so a caged
    ladder leaves them unset and gets no entry for them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    regime: Regime
    height: Quantity
    rung_spacing: Quantity
    rung_clear_width: Quantity
    clearance_behind: Quantity
    rail_extension: Quantity
    fall_protection: LadderFallProtection = LadderFallProtection.NONE
    side_clearance: Quantity | None = None
    climbing_side_clearance: Quantity | None = None

    @model_validator(mode="after")
    def _dimensions_are_what_they_say(self) -> FixedLadder:
        for value, name in (
            (self.height, "height"),
            (self.rung_spacing, "rung_spacing"),
            (self.rung_clear_width, "rung_clear_width"),
            (self.clearance_behind, "clearance_behind"),
            (self.rail_extension, "rail_extension"),
            (self.side_clearance, "side_clearance"),
            (self.climbing_side_clearance, "climbing_side_clearance"),
        ):
            if value is None:
                continue
            if not value.has_dimension("[length]"):
                raise _refuse(
                    f"{name} is a length; got {value.dimensionality}",
                    subject=name,
                    source=_LADDER_SOURCE,
                )
            if value.magnitude <= 0:
                raise _refuse(
                    f"{name} is positive; got {value}", subject=name, source=_LADDER_SOURCE
                )
        caged = self.fall_protection is LadderFallProtection.CAGE_OR_WELL
        if caged and (self.side_clearance is not None or self.climbing_side_clearance is not None):
            raise _refuse(
                "a caged ladder states the clearances 1910.23(d)(13) writes for a ladder "
                "*without* a cage or well; the clause does not apply to it, and screening "
                "it against them would be a verdict under a rule that does not govern",
                subject="side_clearance and climbing_side_clearance",
                source=_LADDER_SOURCE,
            )
        return self


def screen_fixed_ladder(ladder: FixedLadder) -> Scorecard:
    """Screen a :class:`FixedLadder` against 29 CFR 1910.23 and 1910.28(b)(9).

    Geometry first, then the fall-protection trigger. A ladder at or under 24 ft gets an
    entry saying the trigger did not fire rather than no entry at all: "the rule does not
    apply here" is what a reader of a 23-foot ladder's card most needs to be told, and
    silence reads the same as an oversight.
    """
    _general_industry(ladder.regime, "fixed ladder")
    low, high = RUNG_SPACING_RANGE
    entries = [
        _band_entry(
            "ladder rung spacing",
            ladder.rung_spacing,
            low=low.to("inch").magnitude,
            high=high.to("inch").magnitude,
            unit="inch",
            paragraph="23(b)(2)",
            what="rung spacing between centrelines",
            label="rung spacing",
        ),
        _band_entry(
            "ladder rung clear width",
            ladder.rung_clear_width,
            low=MIN_RUNG_CLEAR_WIDTH.to("inch").magnitude,
            high=None,
            unit="inch",
            paragraph="23(b)(4)",
            what="clear width of a fixed ladder's rungs",
            label="clear width",
        ),
        _band_entry(
            "ladder clearance behind",
            ladder.clearance_behind,
            low=MIN_CLEARANCE_BEHIND.to("inch").magnitude,
            high=None,
            unit="inch",
            paragraph="23(d)(2)",
            what="perpendicular distance to the nearest object behind",
            label="clearance behind the rungs",
        ),
        _band_entry(
            "ladder side rail extension",
            ladder.rail_extension,
            low=MIN_RAIL_EXTENSION.to("inch").magnitude,
            high=None,
            unit="inch",
            paragraph="23(d)(4)",
            what="side rails above the access level",
            label="side rail extension",
        ),
    ]
    if ladder.side_clearance is not None:
        entries.append(
            _band_entry(
                "ladder side clearance",
                ladder.side_clearance,
                low=MIN_SIDE_CLEARANCE.to("inch").magnitude,
                high=None,
                unit="inch",
                paragraph="23(d)(13)(i)",
                what="clear width each side of the centreline, no cage or well",
                label="clearance each side of the centreline",
            )
        )
    if ladder.climbing_side_clearance is not None:
        entries.append(
            _band_entry(
                "ladder climbing side clearance",
                ladder.climbing_side_clearance,
                low=MIN_CLIMBING_SIDE_CLEARANCE.to("inch").magnitude,
                high=None,
                unit="inch",
                paragraph="23(d)(13)(ii)",
                what="perpendicular clearance on the climbing side, no cage or well",
                label="clearance on the climbing side",
            )
        )
    entries.append(_ladder_fall_protection_entry(ladder))
    return Scorecard(entries=tuple(entries))


def _ladder_fall_protection_entry(ladder: FixedLadder) -> ScorecardEntry:
    """1910.28(b)(9): more than 24 ft needs one of four systems."""
    height = ladder.height.to("foot").magnitude
    trigger = FALL_PROTECTION_LADDER_HEIGHT.to("foot").magnitude
    reference = _clause("28(b)(9)", "fall protection on a fixed ladder extending more than 24 feet")
    # **More than**, not "or more": 1910.28(b)(9) and (b)(1)(i) differ at their boundary
    # and a ladder at exactly 24 ft is below this one.
    if height <= trigger:
        return ScorecardEntry(
            name="ladder fall protection",
            status=CheckStatus.PASS,
            detail=(
                f"the ladder extends {ladder.height}, which is not more than the "
                f"{FALL_PROTECTION_LADDER_HEIGHT} the clause triggers at, so it requires "
                f"none of the four systems"
            ),
            reference=reference,
            underived=_underived(
                "the clause states a height at which a requirement starts; the check is "
                "the comparison"
            ),
        )
    if ladder.fall_protection is LadderFallProtection.NONE:
        return ScorecardEntry(
            name="ladder fall protection",
            status=CheckStatus.FAIL,
            detail=(
                f"the ladder extends {ladder.height}, more than the "
                f"{FALL_PROTECTION_LADDER_HEIGHT} the clause triggers at, and declares "
                f"none of a personal fall arrest system, a ladder safety system, a cage "
                f"or a well"
            ),
            reference=reference,
            repair_hint=RepairHint.directional(
                "fall_protection",
                direction=Direction.INCREASE,
                provenance=(
                    "four systems 1910.28(b)(9)(i) names, of which one is a "
                    "person's choice rather than a number"
                ),
            ),
            underived=_underived(
                "the clause names four acceptable systems and the check is which one is "
                "declared; there is nothing to compute"
            ),
        )
    return ScorecardEntry(
        name="ladder fall protection",
        status=CheckStatus.PASS,
        detail=(
            f"the ladder extends {ladder.height} and declares a "
            f"{ladder.fall_protection.value.replace('_', ' ')}, which is one of the four "
            f"the clause names"
        ),
        reference=reference,
        underived=_underived(
            "the clause names four acceptable systems and the check is which one is "
            "declared; there is nothing to compute"
        ),
    )


# --- platform edges, 29 CFR 1910.28(b)(1)(i) ------------------------------------------


class PlatformEdge(GuardedInputs):
    """An unprotected side or edge of a walking-working surface, and what is at it.

    ``protection`` is what the edge has: a guardrail, a safety net, a personal fall
    protection system, or nothing. 1910.28(b)(1)(i) requires one of the three at 4 ft or
    more above a lower level.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    regime: Regime
    height_above_lower_level: Quantity
    protection: EdgeProtection = EdgeProtection.NONE

    @model_validator(mode="after")
    def _is_an_edge(self) -> PlatformEdge:
        if not self.height_above_lower_level.has_dimension("[length]"):
            raise _refuse(
                f"height_above_lower_level is a length; got "
                f"{self.height_above_lower_level.dimensionality}",
                subject="height_above_lower_level",
                source="the platform edge as declared",
            )
        if self.height_above_lower_level.magnitude <= 0:
            raise _refuse(
                f"height_above_lower_level is positive; got "
                f"{self.height_above_lower_level}. An edge level with what is below it is "
                f"not an edge anybody falls from",
                subject="height_above_lower_level",
                source="the platform edge as declared",
            )
        return self


def screen_platform_edge(edge: PlatformEdge) -> Scorecard:
    """Screen a :class:`PlatformEdge` against 29 CFR 1910.28(b)(1)(i).

    **Four feet or more**, where the ladder trigger is *more than* 24 feet. The two
    clauses differ at their boundary and this pack keeps them apart: an edge at exactly
    4 ft needs protection and a ladder at exactly 24 ft does not.
    """
    _general_industry(edge.regime, "platform edge")
    height = edge.height_above_lower_level.to("foot").magnitude
    trigger = FALL_PROTECTION_EDGE_HEIGHT.to("foot").magnitude
    reference = _clause("28(b)(1)(i)", "fall protection at an unprotected side or edge")
    reason = _underived(
        "the clause states a height at which a requirement starts; the check is the "
        "comparison and which protection is declared"
    )
    if height < trigger:
        return Scorecard(
            entries=(
                ScorecardEntry(
                    name="platform edge fall protection",
                    status=CheckStatus.PASS,
                    detail=(
                        f"the edge is {edge.height_above_lower_level} above the lower "
                        f"level, below the {FALL_PROTECTION_EDGE_HEIGHT} the clause "
                        f"triggers at, so it requires no fall protection"
                    ),
                    reference=reference,
                    underived=reason,
                ),
            )
        )
    if edge.protection is EdgeProtection.NONE:
        return Scorecard(
            entries=(
                ScorecardEntry(
                    name="platform edge fall protection",
                    status=CheckStatus.FAIL,
                    detail=(
                        f"the edge is {edge.height_above_lower_level} above the lower "
                        f"level, at or above the {FALL_PROTECTION_EDGE_HEIGHT} the clause "
                        f"triggers at, and declares none of a guardrail system, a safety "
                        f"net system or a personal fall protection system"
                    ),
                    reference=reference,
                    repair_hint=RepairHint.directional(
                        "protection",
                        direction=Direction.INCREASE,
                        provenance=(
                            "three systems 1910.28(b)(1)(i) names, of which one is a "
                            "person's choice rather than a number"
                        ),
                    ),
                    underived=reason,
                ),
            )
        )
    return Scorecard(
        entries=(
            ScorecardEntry(
                name="platform edge fall protection",
                status=CheckStatus.PASS,
                detail=(
                    f"the edge is {edge.height_above_lower_level} above the lower level "
                    f"and declares a {edge.protection.value.replace('_', ' ')}, which is "
                    f"one of the three the clause names"
                ),
                reference=reference,
                underived=reason,
            ),
        )
    )
