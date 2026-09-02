"""A Design Spec screened on its own terms: the checks the document itself supports.

Every discipline pack screens a *typed element* — a :class:`~anvilate.packs.structural.LiftingLug`,
a ``PipeRun``, a ``ShallowFooting`` — built by hand. Nothing screened a
:class:`~anvilate.spec.DesignSpec`, so the pipeline the specs describe had a hole in the
middle of it: a spec document compiled to the IR and stopped there, and the scorecard came
from a separate object a caller assembled themselves.

This closes the part of that hole the IR can support today, and is explicit about the part
it cannot.

**What the spec carries, this screens.** Explicit tolerances against the declared
manufacturing process's achievable floor; every declared stack-up chain against its own
required clearance band; and the load cases against the classification the ASCE 7
combination generators need. All three are already implemented elsewhere — this is the
dispatcher, not new analysis.

**A reference the databases do not carry is a verdict, not an exception.** A spec names its
material and its standard components as *identifiers* — `AA-6061-T6`, `NEMA23` — and the
whole retrieval doctrine rests on those resolving to a record with a citation behind it.
`anvilate.spec.validate_references` has always been able to check that, and nothing on any
shipped path called it: a spec naming `NOT-A-REAL-ALLOY` screened exactly like one naming
`AA-6061-T6`, because the two halves of the resolution — the spec layer's
`ReferenceResolver` protocol and `anvilate.standards.StandardsResolver`, which satisfies it
— were built to meet and never wired together. They are wired here, and the answer is a
scorecard entry rather than a raised exception, because "this document names a material the
library cannot retrieve" is a fact about the part, and the card is where facts about the
part go. The refusal names the near misses, which is the whole of the retrieval rule.

Pass ``resolver=`` to screen against extended databases — a team's own alloy is a
`MaterialsDatabase.extended` overlay, not a reason to skip the check.

**What the spec does not carry is named, not skipped.** A ``DesignSpec`` states a
material, a process, interfaces, dimensions, tolerances and loads. It does *not* state what
kind of structural element the part is, so no pack screen can be selected from it, and the
T1 analytical tier is reported ``NOT_EVALUATED`` with that reason on every spec. That is a
gap in the IR rather than in this module, and giving the IR an element declaration is a
change to a published schema — so it is stated here rather than guessed at by matching on a
part's name.

**A demanded tier always produces an entry.** If ``acceptance.tiers`` names a tier, this
returns a verdict for it — including ``NOT_EVALUATED`` when the tier was demanded and there
was nothing in the document to run it against. A tier that produced no entries at all would
be a tier the caller asked for and the scorecard silently dropped, and
:attr:`~anvilate.scorecard.Scorecard.passed` would go green on the strength of the checks
that happened to exist.
"""

from __future__ import annotations

import difflib
import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable, Mapping
from functools import cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ._models import EMPTY_MAP, FrozenMap, rebuilt_quantities
from .derivation import DerivationAbsence, Underived
from .loads import combination_derivation
from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .spec import DesignSpec, ReferenceResolver, ValidationTier
from .standards import default_standards_resolver
from .tolerance.general import ToleranceClass, ToleranceRangeError, resolve_class
from .tolerance.process import tolerance_is_achievable

__all__ = [
    "Structure",
    "StructureMember",
    "element_registry",
    "screen_spec",
    "screen_structure_element",
]

# Why T1 cannot run when a spec declares no element. Written once because it is quoted in
# the scorecard entry, in the docs page, and in the test that pins it — three places that
# must not drift.
_NO_ELEMENT_REASON = (
    "the Design Spec declares no structural element type, so no discipline-pack screen can "
    "be selected from it; declare element_type and element_params, or build the pack's "
    "element and screen that"
)


class StructureMember(BaseModel):
    """One member of a structure, named the same way a spec names a single element.

    The nesting is deliberate rather than a second vocabulary: a member is written with the
    ``element_type``/``element_params`` pair a reader already knows from the document's top
    level, so moving a part into a structure is a change of indentation rather than a
    rewrite.
    """

    model_config = ConfigDict(frozen=True)

    element_type: str
    element_params: FrozenMap[str, Any] = Field(default_factory=lambda: EMPTY_MAP)

    _a_quantity_survives_a_round_trip = field_validator("element_params", mode="before")(
        # A member's parameters are the same `Any`-typed map a top-level element declares,
        # and `DesignSpec`'s own repair does not reach them: it rebuilds the two-key shape
        # one level down, and a member's quantities are two levels down, inside a list. So a
        # structure written to disk came back with every member's dimensions as mappings and
        # every member refused by its own pack model.
        staticmethod(rebuilt_quantities)
    )


class Structure(BaseModel):
    """Several elements screened into one card, so a document can describe a whole assembly.

    `screen_structure` in the structural pack takes a *list* of members, so no single tag
    addressed it and a spec describing a frame could name only one of its members. This is
    the element that closes that: ``element_type: structure`` with the members underneath.

    Each member is dispatched through the same registry a top-level element goes through, so
    a member reaches exactly the screen it would have reached on its own — including the
    refusals. A member that cannot be screened is NOT_EVALUATED naming itself, and the
    other members still run: a frame is not un-screened because one brace was misspelt.
    """

    model_config = ConfigDict(frozen=True)

    members: list[StructureMember] = Field(min_length=1)


def _tag(name: str) -> str:
    """``LiftingLug`` as ``lifting_lug`` — the tag a document writes."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


@cache
def element_registry() -> Mapping[str, tuple[type[BaseModel], Callable[..., Scorecard]]]:
    """Every pack element a spec can name, mapped to its model and its screen.

    **Derived from the packs, not typed here.** Each `anvilate.packs.*` module exports its
    screens as ``screen_*``, and each takes the element it screens as its first parameter;
    the tag is that model's own name in snake case. So a pack that ships a new element
    registers it by existing, and a registry written as a list would be a list that goes
    stale silently — which is the failure mode this module already documents for the tier
    it could not run.

    `screen_structure` in the structural pack takes a *list* of members rather than one
    element, so it is skipped by the same rule that selects the others rather than by name.
    What a document needs from it is here instead, as the one entry this function adds to
    what the packs give it: :class:`Structure`, under the tag ``structure``, which dispatches
    each member back through this same registry. It is registered here rather than in a pack
    because it belongs to no discipline — a structure's members can come from any of them.
    """
    from . import packs

    found: dict[str, tuple[type[BaseModel], Callable[..., Scorecard]]] = {}
    for info in pkgutil.iter_modules(packs.__path__, "anvilate.packs."):
        module = importlib.import_module(info.name)
        for name in sorted(getattr(module, "__all__", ())):
            if not name.startswith("screen_"):
                continue
            screen = getattr(module, name)
            first = next(iter(inspect.signature(screen).parameters.values()), None)
            annotation = first.annotation if first is not None else None
            if isinstance(annotation, str):
                annotation = getattr(module, annotation, None)
            if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
                continue
            tag = _tag(annotation.__name__)
            if tag in found:  # pragma: no cover - the pack tags are distinct today
                raise RuntimeError(
                    f"two pack elements answer to {tag!r}: {found[tag][0].__name__} and "
                    f"{annotation.__name__}; a document naming it would screen the wrong one"
                )
            found[tag] = (annotation, screen)
    found[_tag(Structure.__name__)] = (Structure, screen_structure_element)
    return found


def _screen_element(
    tag: str,
    params: Mapping[str, Any],
    min_safety_factor: float | None,
    max_safety_factor: float | None = None,
) -> list[ScorecardEntry]:
    """The entries one declared element produces, or one saying why there are none.

    Every failure to reach the pack is reported as NOT_EVALUATED naming what went wrong: an
    unknown tag, or parameters the element's own model refuses. A screen that could not be
    selected is not a screen that passed, and this is the tier where that matters most.

    Taken as a tag and a parameter map rather than as a spec, because a structure's members
    are declared the same way and must reach the packs down the same path. A second dispatch
    written beside this one would be a second set of refusals to keep in step.
    """
    registry = element_registry()
    entry = registry.get(tag)
    if entry is None:
        near = difflib.get_close_matches(tag, sorted(registry), n=1)
        suggestion = f"; did you mean {near[0]!r}?" if near else ""
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"element_type {tag!r} is not one of the "
                    f"{len(registry)} elements this library screens{suggestion}"
                ),
            )
        ]
    model, screen = entry
    try:
        element = model.model_validate(dict(params))
    except ValidationError as refused:
        reasons = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '<element>'}: {error['msg']}"
            for error in refused.errors()
        )
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"element_params do not build a {model.__name__} for element_type "
                    f"{tag!r} — {reasons}"
                ),
            )
        ]
    # Every pack screen takes the element and, for thirteen of the twenty-four, a required
    # safety factor. That is the one thing outside the element the document already states,
    # so it comes from `constraints.min_safety_factor` -- and when the screen requires one
    # and the spec declares none, the tier is NOT_EVALUATED rather than screened against a
    # number this library made up. A safety factor nobody stated is the assumption most
    # worth refusing to make.
    parameters = inspect.signature(screen).parameters
    wanted = parameters.get("required_safety_factor")
    keywords: dict[str, object] = {}
    if wanted is not None:
        if min_safety_factor is not None:
            keywords["required_safety_factor"] = min_safety_factor
        elif wanted.default is inspect.Parameter.empty:
            return [
                ScorecardEntry(
                    name="T1 analytical",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"the {tag} screen is judged against a required safety "
                        "factor and the spec states none; declare "
                        "constraints.min_safety_factor"
                    ),
                )
            ]
    # The band's top, where the screen takes one. `OVER_MARGIN` has been first-class in the
    # scorecard, the exit codes and the QIF export since they were written, and reachable
    # only from a `target_safety_factor` argument no document could set. A spec that states
    # the band and an element whose screen cannot use it is the silent-drop shape this module
    # spends its length refusing, so it is an entry rather than a quietly ignored field.
    if max_safety_factor is not None and "target_safety_factor" in parameters:
        keywords["target_safety_factor"] = max_safety_factor
    try:
        card = screen(element, **keywords)
    except (ValueError, LookupError) as refused:
        # A pack screen's own refusals are facts about the document: an identifier the
        # databases do not carry, a quantity outside the standard's range, a guard the
        # element trips. They were uncaught, so `element_params` naming an alloy the
        # database does not have raised out of `screen_spec` and `anvilate check` printed a
        # traceback where it owed a card — the material entry that says exactly what is
        # wrong was two lines further down the same call.
        #
        # `ValueError` and `LookupError` only: a TypeError or an AttributeError out of a
        # screen is this library's bug, not the document's, and must not be reported as a
        # tri-state result.
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"the {tag} screen refused the element it was given — "
                    f"{type(refused).__name__}: {refused}"
                ),
            )
        ]
    if not card.entries:  # pragma: no cover - every pack screen returns at least one check
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=f"the {tag} screen produced no checks",
            )
        ]
    entries = list(card.entries)
    if max_safety_factor is not None:
        # Every safety-factor check is judged against the band the document declared, not
        # only the checks whose screen happens to take a `target_safety_factor` argument.
        # One of the twenty-four did when the field shipped, and a spec asking to be told
        # where it is over-engineered was answered "this screen cannot" for the other
        # twenty-three. The entry carries both numbers the judgement needs, so the band is
        # applied there — and a screen that took the argument itself has already produced
        # the same verdict, which re-judging leaves untouched.
        entries = [entry.with_upper_band(max_safety_factor) for entry in entries]
    return entries


def screen_structure_element(structure: Structure, *, required_safety_factor: float) -> Scorecard:
    """Screen every member of a declared structure into one card.

    The members go back through the same dispatch a top-level element goes through, so a
    member is screened by exactly the screen it would have reached on its own, refusals
    included. Each entry is prefixed with the member that produced it, because two beams in
    one frame otherwise contribute two checks called the same thing and a reader cannot tell
    which one failed.

    **A member that cannot be screened does not stop the others.** It contributes its own
    NOT_EVALUATED entry, which the roll-up already refuses to treat as a pass, and the rest
    of the frame is still screened — a report naming one bad member and nine good ones is
    worth more than one naming nothing.
    """
    entries: list[ScorecardEntry] = []
    for index, member in enumerate(structure.members, start=1):
        label = f"member {index} ({member.element_type})"
        if member.element_type == _tag(Structure.__name__):
            # Not a depth limit dressed up as a rule: a structure inside a structure has no
            # meaning the flat list does not already carry, and allowing it would make this
            # loop reachable from itself.
            produced = [
                ScorecardEntry(
                    name="T1 analytical",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        "a structure cannot be a member of a structure; list its members "
                        "alongside the others"
                    ),
                )
            ]
        else:
            produced = _screen_element(
                member.element_type, member.element_params, required_safety_factor
            )
        entries.extend(
            entry.model_copy(update={"name": f"{label}: {entry.name}"}) for entry in produced
        )
    return Scorecard(entries=tuple(entries))


def _element_entries(spec: DesignSpec) -> list[ScorecardEntry]:
    """The T1 entries for the element a spec declares, or one saying why there are none."""
    if spec.element_type is None:
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=_NO_ELEMENT_REASON,
            )
        ]
    stated = spec.constraints.min_safety_factor
    band = spec.constraints.max_safety_factor
    return _screen_element(
        spec.element_type,
        spec.element_params,
        None if stated is None else stated.value,
        None if band is None else band.value,
    )


def _dfm_entries(spec: DesignSpec) -> list[ScorecardEntry]:
    """One entry per explicitly toleranced dimension, plus the empty case.

    The process floor is a screening estimate that varies by machine and setup, which the
    capability record says in its own note — so a demanded band tighter than the floor is a
    FAIL that carries the source, never a hard limit stated without one.
    """
    process = spec.manufacturing.process.value
    if not spec.dimensions:
        return [
            ScorecardEntry(
                name="tolerance achievability",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"T2 was demanded and the spec declares no explicitly toleranced "
                    f"dimension, so there is nothing to screen against the {process} floor"
                ),
            )
        ]
    entries: list[ScorecardEntry] = []
    for dimension in spec.dimensions:
        try:
            # Resolving is where a fit designation is looked up, and it was outside the
            # try below — so a dimension declaring `H77` raised out of `screen_spec` and
            # took the whole card with it, including the checks that had nothing to do
            # with tolerances. A designation the table does not carry is a fact about the
            # document, which is an entry.
            band = dimension.resolve().width
        except ToleranceRangeError as unknown:
            entries.append(
                ScorecardEntry(
                    name=f"tolerance achievability: {dimension.tag}",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=f"the declared tolerance does not resolve — {unknown}",
                )
            )
            continue
        try:
            check = tolerance_is_achievable(process, band)
        except ToleranceRangeError as unknown:
            # A process the capability table has no record for is a gap, not a pass. The
            # message names the process rather than the table, because the spec is what a
            # caller can change.
            entries.append(
                ScorecardEntry(
                    name=f"tolerance achievability: {dimension.tag}",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=str(unknown),
                )
            )
            continue
        entries.append(
            ScorecardEntry(
                name=f"tolerance achievability: {dimension.tag}",
                status=CheckStatus.PASS if check.achievable else CheckStatus.FAIL,
                detail=str(check),
                reference=check.source,
                underived=Underived(
                    kind=DerivationAbsence.LOOKUP,
                    reason=(
                        "the demanded tolerance band is compared with the floor the "
                        "process-capability table records for this process. The table is "
                        "the whole check; there is no formula between the two numbers"
                    ),
                ),
            )
        )
    return entries


def _chain_entries(spec: DesignSpec) -> list[ScorecardEntry]:
    """One entry per declared stack-up chain, judged on its worst case.

    The worst case is the gate rather than the RSS spread, which is the chain analysis's
    own rule: a statistical range that fits while the worst case does not is a part that
    can be built out of tolerance.
    """
    if not spec.chains:
        return []
    try:
        analyses = spec.analyze_chains()
    except KeyError as unknown:
        # A chain naming a dimension the spec does not declare. Refusing the whole screen
        # would lose the tolerance and load verdicts with it; this is a gap in one layer.
        return [
            ScorecardEntry(
                name="stack-up chains",
                status=CheckStatus.NOT_EVALUATED,
                detail=f"a declared chain references an undeclared dimension tag: {unknown}",
            )
        ]
    except ToleranceRangeError as unresolved:
        # The same reasoning one layer along: analysing a chain resolves the dimensions it
        # links, so a fit designation the table does not carry raised out of here too.
        return [
            ScorecardEntry(
                name="stack-up chains",
                status=CheckStatus.NOT_EVALUATED,
                detail=f"a linked dimension's tolerance does not resolve — {unresolved}",
            )
        ]
    return [
        ScorecardEntry(
            name=f"stack-up: {analysis.name}",
            status=CheckStatus.PASS if analysis.passes else CheckStatus.FAIL,
            detail=str(analysis),
        )
        for analysis in analyses
    ]


# What a declared bound would take to check, said once because the entry quotes it and the
# test pins it. `min_safety_factor` is absent on purpose: it is the one constraint this
# module already consumes, and it is consumed by the pack screen the element selects.
_UNSCREENED_CONSTRAINTS = {
    "max_mass": (
        "a mass is a property of a built solid, and no geometry is generated from a spec today"
    ),
    "envelope": (
        "an envelope is checked against a built solid's bounding box, and no geometry is "
        "generated from a spec today"
    ),
    "max_cost": (
        "a cost needs a cost model — process, setup, material and quantity — and this "
        "library ships none"
    ),
}


def _constraint_entries(spec: DesignSpec) -> list[ScorecardEntry]:
    """One entry per bound the document declares and nothing screens.

    A constraint is the plainest declaration a spec makes: it is the requirement, written
    down by the person the card is for. `max_mass`, `envelope` and `max_cost` were read by
    nothing anywhere in the library — a spec stating `max_mass: 150 g` screened to PASS with
    the mass never computed and never mentioned, which is the same silence the tier gaps
    above exist to break. (Named rather than counted, because the count moved the moment
    `max_safety_factor` was added.)

    They are NOT_EVALUATED rather than absent, and each says what checking it would take.
    """
    entries = []
    for field, reason in _UNSCREENED_CONSTRAINTS.items():
        declared = getattr(spec.constraints, field)
        if declared is None:
            continue
        stated = getattr(declared, "value", declared)
        entries.append(
            ScorecardEntry(
                name=f"constraint {field}",
                status=CheckStatus.NOT_EVALUATED,
                detail=f"the spec declares {field} {stated}, and nothing screened it: {reason}",
            )
        )
    return entries


def _combination_entry(spec: DesignSpec) -> ScorecardEntry | None:
    """The combination the declared basis makes govern, or why none can be named.

    ``None`` when the spec declares no ``combination_basis`` — there is nothing to resolve.

    The machinery for this was complete and joined to nothing: `DesignSpec.combination_set`
    resolves the basis, `DesignSpec.combination_evidence` selects the governing combination
    with the same rule `combination_scorecard` screens by, and both were reachable only from
    a caller who already knew to call them. A document declaring `asce7_lrfd` screened as
    though it had said nothing.

    A seismic basis needs S_DS and refuses without it. That refusal is a fact about the
    document, so it lands on the card rather than out of the call: a spec that asks for the
    seismic set and does not say what to factor it against is not a spec that screened.
    """
    if spec.combination_basis is None:
        return None
    try:
        evidence = spec.combination_evidence()
    except ValueError as refused:
        return ScorecardEntry(
            name="load combination",
            status=CheckStatus.NOT_EVALUATED,
            detail=f"the {spec.combination_basis} basis could not be resolved — {refused}",
        )
    if evidence is None:  # pragma: no cover - a declared basis always resolves to a set
        return None
    if evidence.status is not CheckStatus.PASS:
        return ScorecardEntry(
            name="load combination",
            status=evidence.status,
            detail=evidence.detail(),
        )
    # The factored sum behind the name. Without it this entry cited §2.3.1 and showed a
    # combination's title with no arithmetic under it, while `combination_scorecard` — the
    # other check on the same clause — wrote the sum out in full. One clause rendered two
    # ways, and the half that named the combination was the half a reviewer would have
    # asked to see worked.
    combinations = spec.combination_set()
    assert combinations is not None  # a basis that resolved to evidence resolves to a set
    return ScorecardEntry(
        name="load combination",
        status=evidence.status,
        detail=evidence.detail(),
        reference=evidence.citation,
        derivation=combination_derivation(combinations, spec.combination_loads()),
    )


def _geometric_tolerance_entry(spec: DesignSpec) -> ScorecardEntry | None:
    """The declared GD&T frames, and the fact that nothing screens them yet.

    ``None`` when the spec declares none. Otherwise NOT_EVALUATED: a spec's
    `GeometricTolerance` is a different type from the semantic layer's
    `anvilate.gdt.FeatureControlFrame` that could check it, and nothing converts one to the
    other, so a declared position control is carried into the evidence record and screened by
    nothing. Counting them in the provenance roll-up is not looking at them.
    """
    if not spec.geometric_tolerances:
        return None
    controls = ", ".join(
        sorted({control.characteristic.value for control in spec.geometric_tolerances})
    )
    return ScorecardEntry(
        name="geometric tolerance",
        status=CheckStatus.NOT_EVALUATED,
        detail=(
            f"the spec declares {len(spec.geometric_tolerances)} geometric tolerance(s) "
            f"({controls}), and nothing screened them: a declared control is not bound to "
            "the semantic GD&T layer that could check it, and a zone is checked against "
            "built geometry this package does not generate"
        ),
    )


def _declared_bound_entries(spec: DesignSpec) -> list[ScorecardEntry]:
    """The bounds a document states outside `constraints`, and what answers them.

    Its docstring said exactly that and neither field was read on any screening path.

    ``tolerance_class`` is a *reference*: the general-tolerance class the drawing states, and
    `anvilate.tolerance.resolve_class` — whose own docstring says it resolves "a spec's
    optional tolerance_class" — was called only when the evidence bundle was assembled. So a
    document writing the class the way a drawing writes it, ``ISO2768-m``, screened to PASS
    and then raised `'iso2768-m' is not a valid ToleranceClass` out of `anvilate export`. It
    is a verdict here, with the near misses named, for the same reason an unknown material
    is.

    ``min_wall`` and ``acceptance.max_displacement`` are bounds nothing screens, so they are
    reported unscreened rather than dropped, like the bounds in `constraints`. The
    displacement one says where the limit does belong: the pack screens take it from the
    element (`BeamMember.deflection_limit`), which is why the one on the acceptance criteria
    was reaching nothing.
    """
    entries: list[ScorecardEntry] = []
    declared = spec.manufacturing.tolerance_class
    if declared is not None:
        try:
            resolved = resolve_class(declared)
        except ValueError:
            known = [member.value for member in ToleranceClass]
            entries.append(
                ScorecardEntry(
                    name="general tolerance class",
                    status=CheckStatus.FAIL,
                    detail=(
                        f"unknown general tolerance class {declared!r} — "
                        f"{_near_misses(declared, known)} The class governs every dimension "
                        "the drawing does not tolerance individually."
                    ),
                )
            )
        else:
            entries.append(
                ScorecardEntry(
                    name="general tolerance class",
                    status=CheckStatus.PASS,
                    detail=(
                        f"{declared!r} resolves to ISO 2768 {resolved.value}, the class "
                        "governing every dimension not toleranced individually"
                    ),
                )
            )
    if spec.acceptance.max_displacement is not None:
        entries.append(
            ScorecardEntry(
                name="displacement limit",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"the spec declares acceptance.max_displacement "
                    f"{spec.acceptance.max_displacement}, and nothing screened it: a "
                    "displacement limit is judged against a deflection the element screen "
                    "computes, and the screens take their limit from the element itself "
                    "(a beam member's `deflection_limit`), not from the acceptance criteria"
                ),
            )
        )
    if spec.manufacturing.min_wall is not None:
        entries.append(
            ScorecardEntry(
                name="minimum wall",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"the spec declares min_wall {spec.manufacturing.min_wall}, and nothing "
                    "screened it: a wall thickness is measured on a built solid, and no "
                    "geometry is generated from a spec today"
                ),
            )
        )
    return entries


def _load_entry(spec: DesignSpec) -> ScorecardEntry | None:
    """Whether every force-carrying load case declares the nature a combination needs.

    ``None`` when the spec declares no load cases at all — there is nothing to classify,
    and an entry saying so would be noise rather than a gap. An *unclassified* case is a
    different matter: a combination generator treats a nature nobody supplied as zero, so
    the demand silently omits the load.
    """
    if not spec.load_cases:
        return None
    unclassified = spec.unclassified_force_cases()
    if unclassified:
        return ScorecardEntry(
            name="load classification",
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"{len(unclassified)} of {len(spec.load_cases)} load cases carry a force "
                f"and no declared nature ({', '.join(unclassified)}); a combination treats "
                f"an unsupplied nature as zero, so the demand would never see them"
            ),
        )
    return ScorecardEntry(
        name="load classification",
        status=CheckStatus.PASS,
        detail=f"{len(spec.load_cases)} load cases, every force-carrying one classified",
    )


_DEFAULT_RESOLVER: ReferenceResolver | None = None


def _default_resolver() -> ReferenceResolver:
    """The standards-backed resolver, built once.

    Building it reads nine bundled tables. A repo-wide ``anvilate check`` screens every spec
    it finds, and rebuilding the databases per document is work nobody asked for.
    """
    global _DEFAULT_RESOLVER
    if _DEFAULT_RESOLVER is None:
        _DEFAULT_RESOLVER = default_standards_resolver()
    return _DEFAULT_RESOLVER


def _near_misses(ref: str, known: list[str]) -> str:
    """The closest identifiers to ``ref``, said the way the retrieval rule requires.

    A refusal that only says "unknown" invites the reader to supply a remembered number
    instead, which is the one thing this library is built to stop.
    """
    close = difflib.get_close_matches(ref, known, n=3)
    if close:
        return f"did you mean {', '.join(close)}?"
    return f"nothing among the {len(known)} known identifiers is close to it."


def _reference_entries(spec: DesignSpec, resolver: ReferenceResolver) -> list[ScorecardEntry]:
    """One entry for the material, one per declared interface.

    A spec with no interfaces gets no interface entry — there is nothing to resolve, and an
    entry saying so would read as a check that ran. The material is different: every spec
    declares one, so its entry is always present.

    An *imported* interface is NOT_EVALUATED rather than skipped: resolving it needs the
    document it names, which a screen of one spec does not have.
    """
    entries = [
        ScorecardEntry(
            name="material resolution",
            status=CheckStatus.PASS,
            detail=f"{spec.material.ref} resolves in the bundled materials database",
        )
        if resolver.has_material(spec.material.ref)
        else ScorecardEntry(
            name="material resolution",
            status=CheckStatus.FAIL,
            detail=(
                f"unknown material {spec.material.ref!r} — "
                f"{_near_misses(spec.material.ref, resolver.known_materials())} "
                f"Every property the screens use is retrieved from this identifier, so "
                f"nothing downstream can run on it."
            ),
        )
    ]
    for interface in spec.interfaces:
        if interface.type == "imported":
            # An imported interface names another spec's published contract, and resolving
            # it needs that document — which a single-document screen does not have. It was
            # skipped silently, so a spec whose geometry is designed against a contract
            # nobody fetched screened exactly like one that imports nothing.
            entries.append(
                ScorecardEntry(
                    name=f"interface resolution: {interface.tag}",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"{interface.tag} imports contract {interface.contract!r} from spec "
                        f"{interface.source_spec!r}, and a screen of one document cannot "
                        "fetch another; the contract it designs against was not checked"
                    ),
                )
            )
            continue
        resolved = resolver.has_component(interface.ref)
        entries.append(
            ScorecardEntry(
                name=f"interface resolution: {interface.tag}",
                status=CheckStatus.PASS if resolved else CheckStatus.FAIL,
                detail=(
                    f"{interface.ref} resolves in the bundled component tables"
                    if resolved
                    else f"unknown standard component {interface.ref!r} — "
                    f"{_near_misses(interface.ref, resolver.known_components())}"
                ),
            )
        )
    return entries


def screen_spec(spec: DesignSpec, *, resolver: ReferenceResolver | None = None) -> Scorecard:
    """Screen ``spec`` on the tiers its acceptance criteria demand.

    Returns a :class:`~anvilate.scorecard.Scorecard` carrying one entry per check the
    document supports, and one ``NOT_EVALUATED`` entry per demanded tier this screen cannot
    run. The card is never empty: every spec declares at least one tier, and every tier
    produces at least one entry.

    **A declaration that no demanded tier screens is reported, not dropped.** A spec naming
    its element and demanding only T2 would otherwise pass on a tolerance band with nothing
    saying the part itself was never screened, and a spec declaring a tolerance band and
    demanding only T1 would pass with the band unlooked at.

    ``resolver`` is where the material and component identifiers are looked up; the default
    is the bundled standards databases. Pass one built from
    :meth:`~anvilate.standards.MaterialsDatabase.extended` to screen a spec that names a
    team-local alloy.

    See the module docstring for what is and is not screened, and why the T1 analytical
    tier reports a gap on every spec.
    """
    entries: list[ScorecardEntry] = []
    tiers = tuple(spec.acceptance.tiers)

    if ValidationTier.T0_GEOMETRY in tiers:
        entries.append(
            ScorecardEntry(
                name="T0 geometry",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    "T0 checks a built solid — watertightness, self-intersection, minimum "
                    "wall — and no geometry is generated from a spec today"
                ),
            )
        )
    if ValidationTier.T1_ANALYTICAL in tiers:
        entries.extend(_element_entries(spec))
    elif spec.element_type is not None:
        # An element is a declaration the *document* makes, like a reference or a chain, and
        # the note below says what this library does with those. Before the tag existed this
        # case could not arise; with it, a spec that states its element and its load and
        # demands only T2 screened to PASS on a tolerance band, with nothing anywhere saying
        # the lug had not been looked at. A part screened on none of the checks it asked for
        # must not be indistinguishable from a part that passed them.
        entries.append(
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"the spec declares element_type {spec.element_type!r} and "
                    f"acceptance.tiers does not demand {ValidationTier.T1_ANALYTICAL.value}, "
                    "so no pack screen ran against it"
                ),
            )
        )
    if ValidationTier.T2_DFM in tiers:
        entries.extend(_dfm_entries(spec))
    elif spec.dimensions:
        # The same shape as the element above, and it bites harder: a spec declaring a
        # ±0.0001 mm band — achievable on no process this library knows — and demanding only
        # T1 screened to PASS, because the band nobody asked to check is a band nobody
        # checked. The document states it; the card answers it or says it did not.
        entries.append(
            ScorecardEntry(
                name="tolerance achievability",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"the spec declares {len(spec.dimensions)} toleranced dimension(s) and "
                    f"acceptance.tiers does not demand {ValidationTier.T2_DFM.value}, so "
                    "none was screened against the process floor"
                ),
            )
        )
    if ValidationTier.T3_FEA in tiers:
        entries.append(
            ScorecardEntry(
                name="T3 FEA",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    "T3 is bounded by a convergence criterion rather than by the size of "
                    "the input; it is not part of a synchronous screen"
                ),
            )
        )

    # Not gated on a tier: a reference, a chain and a load case are things the *document*
    # declares, and a spec that declares them has asked for them to be looked at whatever
    # tiers it names.
    entries.extend(_reference_entries(spec, resolver or _default_resolver()))
    entries.extend(_constraint_entries(spec))
    entries.extend(_declared_bound_entries(spec))
    geometric = _geometric_tolerance_entry(spec)
    if geometric is not None:
        entries.append(geometric)
    entries.extend(_chain_entries(spec))
    load = _load_entry(spec)
    if load is not None:
        entries.append(load)
    combination = _combination_entry(spec)
    if combination is not None:
        entries.append(combination)
    return Scorecard(entries=tuple(entries))
