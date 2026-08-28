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

from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .spec import DesignSpec, ValidationTier
from .tolerance.general import ToleranceRangeError
from .tolerance.process import tolerance_is_achievable

__all__ = ["screen_spec"]

# Why T1 cannot run from a spec alone. Written once because it is quoted in the scorecard
# entry, in the docs page, and in the test that pins it — three places that must not drift.
_NO_ELEMENT_REASON = (
    "the Design Spec declares no structural element type, so no discipline-pack screen can "
    "be selected from it; build the pack's element and screen that"
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


def screen_spec(spec: DesignSpec) -> Scorecard:
    """Screen ``spec`` on the tiers its acceptance criteria demand.

    Returns a :class:`~anvilate.scorecard.Scorecard` carrying one entry per check the
    document supports, and one ``NOT_EVALUATED`` entry per demanded tier this screen cannot
    run. The card is never empty: every spec declares at least one tier, and every tier
    produces at least one entry.

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
        entries.append(
            ScorecardEntry(
                name="T1 analytical",
                status=CheckStatus.NOT_EVALUATED,
                detail=_NO_ELEMENT_REASON,
            )
        )
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

    # Not gated on a tier: a chain and a load case are things the *document* declares, and
    # a spec that declares them has asked for them to be looked at whatever tiers it names.
    entries.extend(_chain_entries(spec))
    load = _load_entry(spec)
    if load is not None:
        entries.append(load)
    return Scorecard(entries=tuple(entries))
