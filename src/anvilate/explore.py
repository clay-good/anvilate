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

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from itertools import product
from math import isfinite

from pydantic import BaseModel, ConfigDict, model_validator

from ._models import RevalidatedModel
from .scorecard import CheckStatus, Scorecard

__all__ = [
    "ObjectiveSense",
    "SamplingStrategy",
    "Parameter",
    "Objective",
    "Study",
    "StudyEvaluation",
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
        raise ValueError(f"dimensions must be at least 1; got {dimensions}")
    if dimensions > _HALTON_MAX_DIMENSIONS:
        raise ValueError(
            f"the Halton sequence degrades past {_HALTON_MAX_DIMENSIONS} dimensions — the "
            f"high prime bases correlate and the points stripe rather than fill — and "
            f"{dimensions} were asked for. Use SamplingStrategy.GRID, or sweep fewer "
            f"parameters at once"
        )
    if count < 0:
        raise ValueError(f"count must be non-negative; got {count}")
    if skip < 0:
        raise ValueError(f"skip must be non-negative; got {skip}")
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
            raise ValueError("a parameter needs a name")
        if not (isfinite(self.low) and isfinite(self.high)):
            raise ValueError(f"{self.name}: bounds must be finite; got [{self.low}, {self.high}]")
        if self.low >= self.high:
            raise ValueError(
                f"{self.name}: low ({self.low}) must be below high ({self.high}); a "
                f"collapsed range is a fixed value, not a swept parameter"
            )
        if self.steps < 2:
            raise ValueError(
                f"{self.name}: steps must be at least 2 so both bounds are sampled; "
                f"got {self.steps}"
            )
        return self

    def grid_values(self) -> tuple[float, ...]:
        """The ``steps`` values a grid sweep takes, both bounds included."""
        span = self.high - self.low
        return tuple(self.low + span * index / (self.steps - 1) for index in range(self.steps))


class Objective(BaseModel):
    """One quantity the study ranks designs by, and which direction is better."""

    model_config = ConfigDict(frozen=True)

    name: str
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

    name: str
    parameters: tuple[Parameter, ...]
    objectives: tuple[Objective, ...]
    strategy: SamplingStrategy = SamplingStrategy.GRID
    budget: int | None = None
    seed: int = 0

    @model_validator(mode="after")
    def _well_formed(self) -> Study:
        if not self.parameters:
            raise ValueError("a study needs at least one parameter to sweep")
        if not self.objectives:
            raise ValueError(
                "a study needs at least one objective; without one every feasible point "
                "is non-dominated and the front is just the feasible set"
            )
        names = [p.name for p in self.parameters]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate parameter names in {self.name}: {sorted(names)}")
        objective_names = [o.name for o in self.objectives]
        if len(set(objective_names)) != len(objective_names):
            raise ValueError(f"duplicate objective names in {self.name}: {sorted(objective_names)}")
        if self.budget is not None and self.budget < 1:
            raise ValueError(f"budget must be at least 1 when given; got {self.budget}")
        if self.seed < 0:
            raise ValueError(f"seed must be non-negative; got {self.seed}")
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


class StudyEvaluation(BaseModel):
    """What the caller's evaluator returns for one design point: its numbers and its verdict.

    ``objectives`` must carry a finite value for every objective the study declares, and
    ``scorecard`` decides feasibility. Splitting them is deliberate: the objectives are
    what the point is *ranked* by and the scorecard is what makes it *admissible*, and
    conflating the two is how a lighter-but-failing design ends up on a front.
    """

    model_config = ConfigDict(frozen=True)

    objectives: dict[str, float]
    scorecard: Scorecard


class DesignPoint(BaseModel):
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
    parameters: dict[str, float]
    objectives: dict[str, float]
    status: CheckStatus
    feasible: bool
    fragile: bool = False
    governing_check: str | None = None
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
                raise ValueError(
                    f"point {index} of study {study.name} returned no value for the "
                    f"declared objective {objective.name!r}; got "
                    f"{sorted(evaluation.objectives)}"
                )
            value = evaluation.objectives[objective.name]
            if not isfinite(value):
                raise ValueError(
                    f"point {index} of study {study.name} returned {value} for objective "
                    f"{objective.name!r}. A non-finite objective compares False against "
                    f"everything, so it would sit on the front without dominating anything"
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
