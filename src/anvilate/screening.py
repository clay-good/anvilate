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

from pydantic import BaseModel, ValidationError

from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .spec import DesignSpec, ReferenceResolver, ValidationTier
from .standards import default_standards_resolver
from .tolerance.general import ToleranceRangeError
from .tolerance.process import tolerance_is_achievable

__all__ = ["element_registry", "screen_spec"]

# Why T1 cannot run when a spec declares no element. Written once because it is quoted in
# the scorecard entry, in the docs page, and in the test that pins it — three places that
# must not drift.
_NO_ELEMENT_REASON = (
    "the Design Spec declares no structural element type, so no discipline-pack screen can "
    "be selected from it; declare element_type and element_params, or build the pack's "
    "element and screen that"
)


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

    `screen_structure` takes a *list* of members rather than one element and is therefore
    not addressable by a single tag; it is skipped by the same rule that selects the others
    rather than by name.
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
            if tag in found:  # pragma: no cover - the 23 tags are distinct today
                raise RuntimeError(
                    f"two pack elements answer to {tag!r}: {found[tag][0].__name__} and "
                    f"{annotation.__name__}; a document naming it would screen the wrong one"
                )
            found[tag] = (annotation, screen)
    return found


def _element_entries(spec: DesignSpec) -> list[ScorecardEntry]:
    """The T1 entries for the element a spec declares, or one saying why there are none.

    Every failure to reach the pack is reported as NOT_EVALUATED naming what went wrong: an
    unknown tag, or parameters the element's own model refuses. A screen that could not be
    selected is not a screen that passed, and this is the tier where that matters most.
    """
    if spec.element_type is None:
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=_NO_ELEMENT_REASON,
            )
        ]
    registry = element_registry()
    entry = registry.get(spec.element_type)
    if entry is None:
        near = difflib.get_close_matches(spec.element_type, sorted(registry), n=1)
        suggestion = f"; did you mean {near[0]!r}?" if near else ""
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"element_type {spec.element_type!r} is not one of the "
                    f"{len(registry)} elements the discipline packs screen{suggestion}"
                ),
            )
        ]
    model, screen = entry
    try:
        element = model.model_validate(dict(spec.element_params))
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
                    f"{spec.element_type!r} — {reasons}"
                ),
            )
        ]
    # Every pack screen takes the element and, for twelve of the twenty-three, a required
    # safety factor. That is the one thing outside the element the document already states,
    # so it comes from `constraints.min_safety_factor` -- and when the screen requires one
    # and the spec declares none, the tier is NOT_EVALUATED rather than screened against a
    # number this library made up. A safety factor nobody stated is the assumption most
    # worth refusing to make.
    parameters = inspect.signature(screen).parameters
    wanted = parameters.get("required_safety_factor")
    keywords: dict[str, object] = {}
    if wanted is not None:
        stated = spec.constraints.min_safety_factor
        if stated is not None:
            keywords["required_safety_factor"] = stated.value
        elif wanted.default is inspect.Parameter.empty:
            return [
                ScorecardEntry(
                    name="T1 analytical",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"the {spec.element_type} screen is judged against a required safety "
                        "factor and the spec states none; declare "
                        "constraints.min_safety_factor"
                    ),
                )
            ]
    card = screen(element, **keywords)
    if not card.entries:  # pragma: no cover - every pack screen returns at least one check
        return [
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=f"the {spec.element_type} screen produced no checks",
            )
        ]
    return list(card.entries)


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
        band = dimension.resolve().width
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
    return [
        ScorecardEntry(
            name=f"stack-up: {analysis.name}",
            status=CheckStatus.PASS if analysis.passes else CheckStatus.FAIL,
            detail=str(analysis),
        )
        for analysis in analyses
    ]


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
    """One entry for the material, one per standard-component interface.

    A spec with no standard-component interface gets no interface entry — there is nothing
    to resolve, and an entry saying so would read as a check that ran. The material is
    different: every spec declares one, so its entry is always present.
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
        if interface.type != "standard_component":
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
    if ValidationTier.T2_DFM in tiers:
        entries.extend(_dfm_entries(spec))
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
    entries.extend(_chain_entries(spec))
    load = _load_entry(spec)
    if load is not None:
        entries.append(load)
    return Scorecard(entries=tuple(entries))
