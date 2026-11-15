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
