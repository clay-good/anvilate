"""Design-space exploration: deterministic sweeps and honest Pareto fronts.

Anvilate answers "does this design pass?". This answers "what is the lightest one that
does?" — the question an engineer actually has. The pieces were already here: the checks
are closed-form and evaluate in microseconds, and mass, cost and embodied carbon are
already screening outputs. What was missing is the contract for sweeping a parameter and
reporting a front.

Because a closed-form evaluation is cheap, the right default is *not* Bayesian
optimisation. A seeded, exhaustive sweep with exact non-dominated sorting is faster,
fully reproducible, and small enough to put in an evidence bundle whole. Nothing here is
heuristic: the front is the exact non-dominated set of the points that were evaluated,
and the points that were evaluated are a deterministic function of the study.

Three rules do the load-bearing work, and all three exist because the failure mode of an
optimiser is a confident answer:

1. **A point that did not pass is never on the front.** Feasibility is decided by the
   scorecard, and ``NOT_EVALUATED`` is not feasible — a design whose governing check
   could not run has not been shown to work, so it cannot be the lightest thing that
   works. Infeasible points are *kept and labelled*, never dropped, because a front
   drawn over survivors alone looks like the whole space.
2. **A truncated sweep reports a provisional front.** If the budget cut the sweep short,
   the front is the best of what ran and says so. The word "optimal" appears nowhere in
   this module's output.
3. **Every objective value comes from the caller's deterministic evaluator.** A
   non-finite objective is refused rather than sorted, because comparisons against NaN
   are all False and a NaN point would silently dominate nothing and be dominated by
   nothing — it would sit on the front for a reason that is not a reason.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from enum import StrEnum
from itertools import product
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from ._models import FrozenMap, Named, RevalidatedModel
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard

_STUDY_SOURCE = "the study plan naming the swept parameters and the objectives"
_RANGE_SOURCE = "the design envelope bounding each swept parameter, in its unit"
_SAMPLING_SOURCE = "the study plan's sampling strategy, point budget, and seed"
_EVALUATOR_SOURCE = "the evaluator's value for every objective the study declares"


class _ExploreInputError(RefusalError, ValueError):
    """A design-space study input that cannot be used without correction."""


def _explore_refusal(message: str, *, subject: str, source: str) -> _ExploreInputError:
    return _ExploreInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "ObjectiveSense",
    "SamplingStrategy",
    "Parameter",
    "Objective",
    "Study",
    "StudyEvaluation",
    "tiered_evaluator",
    "EvaluationCache",
    "DesignPoint",
    "StudyResult",
    "run_study",
    "halton_sequence",
]

# Halton needs one prime per dimension and degrades as the dimension climbs: the
# high-dimension bases cycle in step with each other and the points fall into visible
# stripes rather than filling the space. Eight is the conventional line at which that
# starts to matter, and past it a grid is the honest choice.
_HALTON_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19)
_HALTON_MAX_DIMENSIONS = len(_HALTON_PRIMES)


class ObjectiveSense(StrEnum):
    """Whether an objective is better small or better large."""

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class SamplingStrategy(StrEnum):
    """How the study picks the points it evaluates.

    :attr:`GRID` is the full-factorial product of each parameter's steps — exhaustive,
    reproducible, and the right default when the space is small enough to sweep whole.
    :attr:`HALTON` is a deterministic low-discrepancy sequence for a space too large to
    grid: it fills the box more evenly than a coarse grid at the same budget and, unlike
    a random sample, is a pure function of the point index.

    **This is Halton, not Sobol.** Sobol needs published direction numbers per dimension;
    reproducing them from memory is exactly the guess this library's citation contract
    exists to prevent, and no anchor was available. Halton is elementary — the radical
    inverse of the index in one prime base per dimension — so it can be written down and
    checked by hand, which is why it is what ships.
    """

    GRID = "grid"
    HALTON = "halton"


def halton_sequence(*, dimensions: int, count: int, skip: int = 1) -> tuple[tuple[float, ...], ...]:
    """``count`` points of the Halton sequence in the unit box, deterministically.

    Each coordinate is the radical inverse of the point index in its own prime base: for
    index n in base b, write n in base b and mirror the digits about the point. The
    result is a pure function of ``dimensions``, ``count`` and ``skip`` — there is no
    random state anywhere in it, which is what makes a study reproducible from its
    declaration rather than from a saved sample.

    ``skip`` defaults to 1 because index 0 maps to the origin in every base, which is a
    corner rather than a sample. Raises above eight dimensions, where the sequence's
    correlation between high prime bases makes it worse than a grid rather than better.
    """
    if dimensions < 1:
        raise _explore_refusal(
            f"dimensions must be at least 1; got {dimensions}",
            subject="dimensions",
            source=_SAMPLING_SOURCE,
        )
    if dimensions > _HALTON_MAX_DIMENSIONS:
        raise _explore_refusal(
            f"the Halton sequence degrades past {_HALTON_MAX_DIMENSIONS} dimensions — the "
            f"high prime bases correlate and the points stripe rather than fill — and "
            f"{dimensions} were asked for. Use SamplingStrategy.GRID, or sweep fewer "
            f"parameters at once",
            subject="dimensions",
            source=_SAMPLING_SOURCE,
        )
    if count < 0:
        raise _explore_refusal(
            f"count must be non-negative; got {count}", subject="count", source=_SAMPLING_SOURCE
        )
    if skip < 0:
        raise _explore_refusal(
            f"skip must be non-negative; got {skip}", subject="skip", source=_SAMPLING_SOURCE
        )
    points = []
    for index in range(skip, skip + count):
        coordinates = []
        for base in _HALTON_PRIMES[:dimensions]:
            fraction, result, remaining = 1.0, 0.0, index
            while remaining > 0:
                fraction /= base
                result += fraction * (remaining % base)
                remaining //= base
            coordinates.append(result)
        points.append(tuple(coordinates))
    return tuple(points)


class Parameter(RevalidatedModel):
    """One swept design variable: its name, its bounds, its unit, and its resolution.

    ``steps`` is how many values a :attr:`SamplingStrategy.GRID` sweep takes across
    ``[low, high]`` inclusive, so 2 gives the two ends and 5 gives quarter points. It is
    ignored by a Halton sweep, which samples continuously.

    ``unit`` is recorded rather than applied: the evaluator receives plain floats and is
    responsible for reading them in the unit the parameter declares. Recording it means
    a front cannot be read back without knowing what its axes are in.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    low: float
    high: float
    unit: str
    steps: int = 5

    @model_validator(mode="after")
    def _well_formed(self) -> Parameter:
        if not self.name.strip():
            raise _explore_refusal("a parameter needs a name", subject="name", source=_STUDY_SOURCE)
        if not (isfinite(self.low) and isfinite(self.high)):
            raise _explore_refusal(
                f"{self.name}: bounds must be finite; got [{self.low}, {self.high}]",
                subject="low and high",
                source=_RANGE_SOURCE,
            )
        if self.low >= self.high:
            raise _explore_refusal(
                f"{self.name}: low ({self.low}) must be below high ({self.high}); a "
                f"collapsed range is a fixed value, not a swept parameter",
                subject="low and high",
                source=_RANGE_SOURCE,
            )
        if self.steps < 2:
            raise _explore_refusal(
                f"{self.name}: steps must be at least 2 so both bounds are sampled; "
                f"got {self.steps}",
                subject="steps",
                source=_SAMPLING_SOURCE,
            )
        return self

    def grid_values(self) -> tuple[float, ...]:
        """The ``steps`` values a grid sweep takes, both bounds included."""
        span = self.high - self.low
        return tuple(self.low + span * index / (self.steps - 1) for index in range(self.steps))


class Objective(RevalidatedModel):
    """One quantity the study ranks designs by, and which direction is better."""

    model_config = ConfigDict(frozen=True)

    name: Named
    sense: ObjectiveSense = ObjectiveSense.MINIMIZE


class Study(RevalidatedModel):
    """A declared design-space study: what to sweep, what to rank by, and how far to go.

    ``budget`` caps how many points are evaluated. A grid larger than the budget is
    *truncated*, not resampled, and the result says so — a front from a truncated sweep
    is provisional, and the distinction between "the lightest passing design" and "the
    lightest passing design we got to" is the whole reason the flag exists.

    ``seed`` is recorded for reproducibility even though nothing here is random: both
    strategies are pure functions of the study, so a study re-run returns the identical
    set in the identical order. The seed shifts the Halton start index, which is the one
    knob that changes which points a truncated sweep gets to.
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    parameters: tuple[Parameter, ...]
    objectives: tuple[Objective, ...]
    strategy: SamplingStrategy = SamplingStrategy.GRID
    budget: int | None = None
    seed: int = 0

    @model_validator(mode="after")
    def _well_formed(self) -> Study:
        if not self.parameters:
            raise _explore_refusal(
                "a study needs at least one parameter to sweep",
                subject="parameters",
                source=_STUDY_SOURCE,
            )
        if not self.objectives:
            raise _explore_refusal(
                "a study needs at least one objective; without one every feasible point "
                "is non-dominated and the front is just the feasible set",
                subject="objectives",
                source=_STUDY_SOURCE,
            )
        names = [p.name for p in self.parameters]
        if len(set(names)) != len(names):
            raise _explore_refusal(
                f"duplicate parameter names in {self.name}: {sorted(names)}",
                subject="parameters",
                source=_STUDY_SOURCE,
            )
        objective_names = [o.name for o in self.objectives]
        if len(set(objective_names)) != len(objective_names):
            raise _explore_refusal(
                f"duplicate objective names in {self.name}: {sorted(objective_names)}",
                subject="objectives",
                source=_STUDY_SOURCE,
            )
        if self.budget is not None and self.budget < 1:
            raise _explore_refusal(
                f"budget must be at least 1 when given; got {self.budget}",
                subject="budget",
                source=_SAMPLING_SOURCE,
            )
        if self.seed < 0:
            raise _explore_refusal(
                f"seed must be non-negative; got {self.seed}",
                subject="seed",
                source=_SAMPLING_SOURCE,
            )
        return self

    def grid_size(self) -> int:
        """How many points a full-factorial sweep of this study would evaluate."""
        size = 1
        for parameter in self.parameters:
            size *= parameter.steps
        return size

    def sample(self) -> tuple[dict[str, float], ...]:
        """The parameter sets this study evaluates, in order, truncated to its budget.

        Deterministic in both strategies: a grid walks the full-factorial product with
        the *first* parameter varying slowest, and Halton walks its sequence from an
        index the seed shifts. Re-running a study returns the identical tuple.
        """
        if self.strategy is SamplingStrategy.GRID:
            axes = [parameter.grid_values() for parameter in self.parameters]
            combinations = product(*axes)
            points = [
                {
                    parameter.name: value
                    for parameter, value in zip(self.parameters, combination, strict=True)
                }
                for combination in combinations
            ]
        else:
            count = self.budget if self.budget is not None else self.grid_size()
            unit_points = halton_sequence(
                dimensions=len(self.parameters), count=count, skip=1 + self.seed
            )
            points = [
                {
                    parameter.name: parameter.low + (parameter.high - parameter.low) * coordinate
                    for parameter, coordinate in zip(self.parameters, unit_point, strict=True)
                }
                for unit_point in unit_points
            ]
        if self.budget is not None:
            points = points[: self.budget]
        return tuple(points)


class StudyEvaluation(RevalidatedModel):
    """What the caller's evaluator returns for one design point: its numbers and its verdict.

    ``objectives`` must carry a finite value for every objective the study declares, and
    ``scorecard`` decides feasibility. Splitting them is deliberate: the objectives are
    what the point is *ranked* by and the scorecard is what makes it *admissible*, and
    conflating the two is how a lighter-but-failing design ends up on a front.

    ``tiers`` names the evaluation tiers that ran, in order, when the evaluator was built
    by :func:`tiered_evaluator`. Empty means the evaluator is a single undivided one, which
    is the ordinary case and not a missing record.
    """

    model_config = ConfigDict(frozen=True)

    objectives: FrozenMap[str, float]
    scorecard: Scorecard
    tiers: tuple[str, ...] = ()


def tiered_evaluator(
    tiers: Sequence[tuple[str, Callable[[Mapping[str, float]], StudyEvaluation]]],
) -> Callable[[Mapping[str, float]], StudyEvaluation]:
    """Several evaluators as one, run **cheapest first** and stopped at the first failure.

    A study spends almost all of its time in the evaluator, and most candidate designs are
    refuted by something cheap: a wall thinner than the process allows, a mass over budget,
    a bearing outside its rated life. Running an expensive check on a design a cheap one
    has already ruled out is the waste this removes.

    ``tiers`` is ``[(name, evaluate), ...]`` in the order they should run. Each one takes
    the design and returns a :class:`StudyEvaluation`, exactly as an undivided evaluator
    does. The combined evaluator runs them in order and **stops at the first whose
    scorecard does not pass**, returning what it has: the entries of every tier that ran,
    concatenated, and ``tiers`` naming them. A point refuted at the first tier therefore
    carries one tier's entries and one name, and a point that survives carries all of them.

    **The order is the caller's claim, not something this measures.** Nothing here knows
    what an evaluator costs; "cheapest first" is a property of the list as given, and a list
    in the wrong order still produces correct answers, just not quickly.

    **Every tier returns the objectives**, because the objectives are what a point is ranked
    by and a point refuted at tier one still has to be placed. That is the usual shape in
    any case: mass and cost are cheap, and it is the checks that are expensive. A later tier
    may **refine** an objective an earlier one estimated, and the later value wins — within
    one point's evaluation nothing has been ranked yet, so a refinement is not a result
    changing under a reader.

    The feasibility test is the scorecard's own ``passed``, so a tier that comes back
    ``NOT_EVALUATED`` stops the chain just as a ``FAIL`` does: a design whose cheap check
    could not run has not earned an expensive one.
    """
    ordered = list(tiers)
    if not ordered:
        raise _explore_refusal(
            "tiers is the evaluators to run in order, cheapest first, and it is empty",
            subject="tiers",
            source="the study's evaluators, ordered cheapest first by the caller",
        )
    names: list[str] = []
    for entry in ordered:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise _explore_refusal(
                f"each tier is a (name, evaluate) pair; got {entry!r}",
                subject="tiers",
                source="the study's evaluators, ordered cheapest first by the caller",
            )
        name, evaluate = entry
        if not isinstance(name, str) or not name.strip():
            raise _explore_refusal(
                f"a tier's name is what the per-point record shows; got {name!r}",
                subject="tiers",
                source="the study's evaluators, ordered cheapest first by the caller",
            )
        if not callable(evaluate):
            raise _explore_refusal(
                f"the tier {name!r} is not callable; each one takes a design and returns a "
                f"StudyEvaluation",
                subject="tiers",
                source="the study's evaluators, ordered cheapest first by the caller",
            )
        names.append(name)
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise _explore_refusal(
            f"these tier names are used twice: {repeated}; the per-point record names the "
            f"tiers that ran, and two with one name cannot be told apart in it",
            subject="tiers",
            source="the study's evaluators, ordered cheapest first by the caller",
        )

    def combined(design: Mapping[str, float]) -> StudyEvaluation:
        objectives: dict[str, float] = {}
        entries: list[Any] = []
        ran: list[str] = []
        for name, evaluate in ordered:
            result = evaluate(design)
            if not isinstance(result, StudyEvaluation):
                raise _explore_refusal(
                    f"the tier {name!r} returned a {type(result).__name__}, not a StudyEvaluation",
                    subject="tiers",
                    source="the study's evaluators, ordered cheapest first by the caller",
                )
            objectives.update(result.objectives)
            entries.extend(result.scorecard.entries)
            ran.append(name)
            if not result.scorecard.passed:
                break
        return StudyEvaluation(
            objectives=objectives,
            scorecard=Scorecard(entries=tuple(entries)),
            tiers=tuple(ran),
        )

    return combined


class EvaluationCache:
    """An evaluator that answers a design it has already seen from its own record.

    A search revisits designs. A pattern search steps back onto a point it came from, a
    local refinement shrinks around one it has already measured, and a start design is often
    evaluated a second time as the first offspring. Each repeat is a full evaluation of a
    design whose answer is already known, and with FEA in the loop that is minutes.

    Wrap the evaluator and pass this where one is expected — it is callable, so
    ``run_search(study, EvaluationCache(evaluate))`` is the whole of it:

        cached = EvaluationCache(evaluate)
        result = run_search(study, cached)
        cached.hits, cached.misses      # what it saved, and over how many designs

    **The key is the design's content, not its identity.** Two mappings with the same
    parameters and the same values are the same design however they were built, and the
    digest is taken over the sorted ``(name, value)`` pairs with each float written at full
    precision. Full precision is the point: 3,0 and 3,0000000000000004 are **different
    designs** and must not share an answer, because a refinement that has walked a
    ten-thousandth of a millimetre has walked somewhere, and a cache that rounded them
    together would hand back a stale verdict exactly where a search is most sensitive.

    **It caches what the evaluator returned, not whether that was right.** A
    :class:`StudyEvaluation` is frozen, so handing the same one back twice is safe; but an
    evaluator that is not a pure function of its design — one reading a file that changes,
    or a clock — must not be wrapped, and nothing here can detect that. One cache belongs to
    one evaluator, for the same reason.

    ``store`` lets the record live somewhere else: pass a mapping and the entries go into
    it, which is how a cache survives between runs or is shared with a solver's own result
    store. The default is a fresh dictionary, so an unshared cache is the easy case.

    A cache hit still produces a point, so this does not change what a budget counts or
    what the record contains — only how long it takes to get there.
    """

    def __init__(
        self,
        evaluate: Callable[[Mapping[str, float]], StudyEvaluation],
        *,
        store: MutableMapping[str, StudyEvaluation] | None = None,
    ) -> None:
        if not callable(evaluate):
            raise _explore_refusal(
                "evaluate is the function from a design to its StudyEvaluation",
                subject="evaluate",
                source="the study's evaluator",
            )
        if store is not None and not isinstance(store, MutableMapping):
            raise _explore_refusal(
                f"store is a mutable mapping from digest to StudyEvaluation; got "
                f"{type(store).__name__}",
                subject="store",
                source="the caller's result store, or none for a fresh one",
            )
        self._evaluate = evaluate
        self._store: MutableMapping[str, StudyEvaluation] = {} if store is None else store
        self.hits = 0
        self.misses = 0

    @staticmethod
    def digest(design: Mapping[str, float]) -> str:
        """The content digest of one design: sorted names, each value at full precision.

        ``repr`` of a float round-trips exactly in Python, which is what makes this a
        content key and not an approximation of one.
        """
        if not isinstance(design, Mapping):
            raise _explore_refusal(
                f"a design is a mapping from parameter name to value; got {type(design).__name__}",
                subject="design",
                source="the study's variables and the point being evaluated",
            )
        body = "\x1e".join(f"{name}\x1f{float(design[name])!r}" for name in sorted(design))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def __len__(self) -> int:
        """How many distinct designs the record holds."""
        return len(self._store)

    def __call__(self, design: Mapping[str, float]) -> StudyEvaluation:
        key = self.digest(design)
        held = self._store.get(key)
        if held is not None:
            self.hits += 1
            return held
        result = self._evaluate(design)
        if not isinstance(result, StudyEvaluation):
            raise _explore_refusal(
                f"the evaluator returned a {type(result).__name__}, not a StudyEvaluation; "
                f"a cache that stored it would hand the same wrong thing back every time",
                subject="evaluate",
                source="the study's evaluator",
            )
        self.misses += 1
        self._store[key] = result
        return result


class DesignPoint(RevalidatedModel):
    """One evaluated design: where it sits, what it scores, and whether it is admissible.

    ``feasible`` is the scorecard's own verdict, and ``NOT_EVALUATED`` is **not**
    feasible: a design whose governing check could not run has not been shown to work.
    ``governing_check`` names the check running closest to its limit, which is what tells
    a reader *why* a point is where it is — an infeasible point names what stopped it,
    and a feasible one names what it would hit first if pushed.

    ``fragile`` is True when a check on this point carries a margin distribution showing a
    material shortfall probability. Such a point is feasible — it passes nominally — and
    it is exactly the design an optimiser will hand back, because the front is drawn at
    the edge of feasibility where fragility lives. Reporting it is the difference between
    "the lightest passing design" and "the lightest design that passes on paper".
    """

    model_config = ConfigDict(frozen=True)

    index: int
    parameters: FrozenMap[str, float]
    objectives: FrozenMap[str, float]
    status: CheckStatus
    feasible: bool
    fragile: bool = False
    governing_check: str | None = None
    #: The evaluation tiers that ran for this point, when the evaluator was tiered. A short
    #: tuple on an infeasible point is the saving: it says the expensive tiers never ran.
    tiers: tuple[str, ...] = ()
    governing_safety_factor: float | None = None


class StudyResult(BaseModel):
    """A completed study: every point evaluated, and the exact front over the feasible ones.

    ``front`` is the non-dominated subset of the *feasible* points — exact, not
    approximate, because the whole evaluated set is in hand. ``provisional`` is True
    whenever the sweep did not exhaust the declared grid — because a budget truncated it,
    or because it sampled continuously and never visited the grid at all — and then the
    front is the best of what ran and nothing stronger. Only an untruncated grid sweep is
    complete. Nothing here is described as optimal.
    """

    model_config = ConfigDict(frozen=True)

    study: Study
    points: tuple[DesignPoint, ...]
    front_indices: tuple[int, ...]
    grid_size: int
    provisional: bool

    @property
    def front(self) -> tuple[DesignPoint, ...]:
        """The non-dominated feasible points, in evaluation order."""
        lookup = {point.index: point for point in self.points}
        return tuple(lookup[index] for index in self.front_indices)

    @property
    def feasible(self) -> tuple[DesignPoint, ...]:
        """Every point that passed — the admissible set the front is drawn over."""
        return tuple(point for point in self.points if point.feasible)

    @property
    def fragile(self) -> tuple[DesignPoint, ...]:
        """The feasible points whose own declared input scatter fails them materially often.

        A front sits at the edge of feasibility, which is where fragility lives, so these
        are disproportionately the points an optimiser returns. They are not excluded —
        they do pass — but a sweep that does not name them hands back the lightest design
        that passes *on paper*.
        """
        return tuple(point for point in self.feasible if point.fragile)

    @property
    def coverage(self) -> float:
        """The fraction of the full-factorial space this sweep evaluated, at most 1.0.

        For a Halton sweep this is a *budget* ratio, not a coverage claim: the sequence
        samples the box continuously and lands on no grid point at all, so the number says
        how much of a grid's worth of evaluation was spent rather than how much of the
        grid was seen. :attr:`provisional` is True for every Halton study for that reason.
        """
        if not self.grid_size:
            return 0.0
        return min(len(self.points) / self.grid_size, 1.0)

    def best(self, objective: str) -> DesignPoint | None:
        """The feasible point that scores best on one objective, or ``None`` if none do.

        ``None`` is the honest answer to "what is the lightest passing design" when
        nothing passed, and it is a different answer from the lightest *evaluated*
        design, which is what a sweep that dropped its infeasible points would hand back.
        """
        sense = next((o.sense for o in self.study.objectives if o.name == objective), None)
        if sense is None:
            raise KeyError(f"{objective} is not an objective of study {self.study.name}")
        candidates = self.feasible
        if not candidates:
            return None
        chooser = min if sense is ObjectiveSense.MINIMIZE else max
        return chooser(candidates, key=lambda point: point.objectives[objective])

    def summary(self) -> str:
        """One line for a report pane. Never says 'optimal'."""
        state = "provisional" if self.provisional else "complete"
        feasible = len(self.feasible)
        fragile = len(self.fragile)
        warning = f", {fragile} of them fragile" if fragile else ""
        return (
            f"{self.study.name}: {len(self.points)} of {self.grid_size} points evaluated "
            f"({self.coverage:.0%}, {state}), {feasible} feasible{warning}, "
            f"{len(self.front_indices)} on the front"
        )


def _dominates(
    left: Mapping[str, float], right: Mapping[str, float], objectives: Sequence[Objective]
) -> bool:
    """Whether ``left`` is at least as good on every objective and better on one."""
    strictly_better = False
    for objective in objectives:
        a, b = left[objective.name], right[objective.name]
        if objective.sense is ObjectiveSense.MAXIMIZE:
            a, b = -a, -b
        if a > b:
            return False
        if a < b:
            strictly_better = True
    return strictly_better


def run_study(
    study: Study, evaluate: Callable[[Mapping[str, float]], StudyEvaluation]
) -> StudyResult:
    """Sweep a :class:`Study` through ``evaluate`` and return the exact front.

    ``evaluate`` is the caller's deterministic function from a parameter set to a
    :class:`StudyEvaluation`. Every number in the result comes from it; nothing here
    proposes, interpolates or estimates a value. A study may be *proposed* by a model —
    which parameters, which bounds, which objectives — but no objective value may be.

    Feasibility is the scorecard's verdict, and an infeasible point stays in ``points``
    with ``feasible`` False rather than being dropped: a front drawn over survivors alone
    looks like the whole space, and the shape of the infeasible region is usually the
    more useful half of a sweep.

    Raises if an evaluation omits a declared objective or returns a non-finite value for
    one. A NaN objective is neither dominated nor dominating, so it would land on the
    front for no reason at all.
    """
    samples = study.sample()
    points: list[DesignPoint] = []
    for index, parameters in enumerate(samples):
        evaluation = evaluate(parameters)
        values: dict[str, float] = {}
        for objective in study.objectives:
            if objective.name not in evaluation.objectives:
                raise _explore_refusal(
                    f"point {index} of study {study.name} returned no value for the "
                    f"declared objective {objective.name!r}; got "
                    f"{sorted(evaluation.objectives)}",
                    subject="evaluate",
                    source=_EVALUATOR_SOURCE,
                )
            value = evaluation.objectives[objective.name]
            if not isfinite(value):
                raise _explore_refusal(
                    f"point {index} of study {study.name} returned {value} for objective "
                    f"{objective.name!r}. A non-finite objective compares False against "
                    f"everything, so it would sit on the front without dominating anything",
                    subject="evaluate",
                    source=_EVALUATOR_SOURCE,
                )
            values[objective.name] = value
        card = evaluation.scorecard
        governing = card.governing()
        points.append(
            DesignPoint(
                index=index,
                parameters=dict(parameters),
                objectives=values,
                status=card.status,
                # NOT_EVALUATED is not feasible: a design whose governing check could not
                # run has not been shown to work, and the front is "the best thing that
                # works", not "the best thing we did not disprove".
                feasible=card.passed,
                tiers=evaluation.tiers,
                fragile=bool(card.fragile()),
                governing_check=governing.name if governing is not None else None,
                governing_safety_factor=governing.safety_factor if governing is not None else None,
            )
        )
    feasible = [point for point in points if point.feasible]
    front = [
        point.index
        for point in feasible
        if not any(
            _dominates(other.objectives, point.objectives, study.objectives)
            for other in feasible
            if other.index != point.index
        )
    ]
    grid_size = study.grid_size()
    # A Halton sweep is ALWAYS provisional, however many points it took. It samples the
    # box continuously and hits neither bound on any axis, so evaluating grid_size points
    # is not evaluating the grid — a 5x5 study reporting "25 of 25 (100%, complete)" while
    # touching none of the 25 grid points is the exact claim rule 2 exists to prevent.
    exhaustive = study.strategy is SamplingStrategy.GRID and len(points) >= grid_size
    return StudyResult(
        study=study,
        points=tuple(points),
        front_indices=tuple(front),
        grid_size=grid_size,
        provisional=not exhaustive,
    )
