"""Design-space exploration: determinism, exact fronts, and the three ways a sweep lies.

The failure mode of an optimiser is a confident answer, so every test here is about a
result that *looks* like an answer: a front drawn over the points that happened to
survive, a truncated sweep reporting a best, a lighter-but-failing design ranked first.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from itertools import combinations

import pytest

from anvilate.explore import (
    DesignPoint,
    Objective,
    ObjectiveSense,
    Parameter,
    SamplingStrategy,
    Study,
    StudyEvaluation,
    halton_sequence,
    run_study,
)
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry


def _card(*, safety_factor: float | None, name: str = "strength") -> Scorecard:
    return Scorecard(
        entries=(ScorecardEntry.from_safety_factor(name, computed=safety_factor, required=1.0),)
    )


def _analytic_study(**overrides) -> Study:
    kwargs = {
        "name": "analytic",
        "parameters": (
            Parameter(name="x", low=0.0, high=4.0, unit="mm", steps=5),
            Parameter(name="y", low=0.0, high=4.0, unit="mm", steps=5),
        ),
        "objectives": (Objective(name="f"), Objective(name="g")),
    }
    kwargs.update(overrides)
    return Study(**kwargs)


def _analytic_evaluate(parameters: Mapping[str, float]) -> StudyEvaluation:
    """A small space with a hand-computable front.

    Minimise both x and y, feasible only where x + y >= 4. The two objectives pull
    toward the origin and the constraint pushes away from it, so the front is exactly
    the boundary line x + y = 4: (0,4), (1,3), (2,2), (3,1), (4,0).
    """
    x, y = parameters["x"], parameters["y"]
    return StudyEvaluation(
        objectives={"f": x, "g": y},
        scorecard=_card(safety_factor=2.0 if x + y >= 4.0 else 0.5),
    )


def _brute_force_front(points: tuple[DesignPoint, ...], senses: dict[str, ObjectiveSense]):
    """A deliberately naive O(n^2) reference implementation, written a different way."""
    feasible = [p for p in points if p.feasible]
    front = []
    for point in feasible:
        dominated = False
        for other in feasible:
            if other.index == point.index:
                continue
            at_least_as_good = True
            strictly_better = False
            for name, sense in senses.items():
                a, b = other.objectives[name], point.objectives[name]
                if sense is ObjectiveSense.MAXIMIZE:
                    a, b = -a, -b
                if a > b:
                    at_least_as_good = False
                    break
                if a < b:
                    strictly_better = True
            if at_least_as_good and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(point.index)
    return tuple(front)


def test_the_halton_sequence_is_the_radical_inverse_it_claims_to_be():
    """Anchored by hand: base 2 gives 1/2, 1/4, 3/4, 1/8, 5/8 and base 3 gives 1/3, 2/3, 1/9.

    The whole reason Halton ships instead of Sobol is that it can be checked by hand —
    Sobol needs published direction numbers this library would be guessing at. So it is
    checked by hand.
    """
    points = halton_sequence(dimensions=2, count=5)
    assert [p[0] for p in points] == [0.5, 0.25, 0.75, 0.125, 0.625]
    assert [p[1] for p in points] == pytest.approx([1 / 3, 2 / 3, 1 / 9, 4 / 9, 7 / 9])
    # Index 0 is the origin in every base — a corner, not a sample — so skip defaults to 1.
    assert halton_sequence(dimensions=1, count=1, skip=0) == ((0.0,),)
    # Pure function of the index: no random state, so the same call is the same points.
    assert halton_sequence(dimensions=3, count=7) == halton_sequence(dimensions=3, count=7)
    # A prefix of a longer sequence, which is what makes a budget a truncation.
    assert halton_sequence(dimensions=2, count=3) == halton_sequence(dimensions=2, count=9)[:3]
    with pytest.raises(ValueError, match="degrades past 8 dimensions"):
        halton_sequence(dimensions=9, count=4)


def test_a_study_re_run_returns_the_identical_set_in_the_identical_order():
    study = _analytic_study()
    first = run_study(study, _analytic_evaluate)
    second = run_study(study, _analytic_evaluate)
    assert [p.parameters for p in first.points] == [p.parameters for p in second.points]
    assert first.front_indices == second.front_indices
    # The grid walks the FIRST parameter slowest, which is what makes a truncated grid a
    # sweep of the first rows rather than a sample of the box — the reason the example's
    # 20-point grid finds nothing.
    assert [p.parameters["x"] for p in first.points[:5]] == [0.0] * 5
    assert [p.parameters["y"] for p in first.points[:5]] == [0.0, 1.0, 2.0, 3.0, 4.0]
    # Both bounds are sampled, on both axes.
    assert {p.parameters["x"] for p in first.points} == {0.0, 1.0, 2.0, 3.0, 4.0}


def test_the_front_matches_a_brute_force_reference_on_a_small_space():
    """Exact, not approximate — and checked against a separately written implementation."""
    study = _analytic_study()
    result = run_study(study, _analytic_evaluate)
    senses = {o.name: o.sense for o in study.objectives}
    assert result.front_indices == _brute_force_front(result.points, senses)
    # No point on the front dominates another, which is what non-dominated means. Written
    # as `and`, not `or`: with `or` the two clauses can never both be false at once — A
    # and B together force the objective dicts equal, which the `!=` conjunct in each
    # already excludes — so the assertion was a tautology and passed against anything.
    for left, right in combinations(result.front, 2):
        assert not (
            left.objectives["f"] <= right.objectives["f"]
            and left.objectives["g"] <= right.objectives["g"]
            and (left.objectives != right.objectives)
        )
        assert not (
            right.objectives["f"] <= left.objectives["f"]
            and right.objectives["g"] <= left.objectives["g"]
            and (left.objectives != right.objectives)
        )
    # The front is exactly the constraint boundary x + y = 4, computed by hand above.
    assert sorted((p.parameters["x"], p.parameters["y"]) for p in result.front) == [
        (0.0, 4.0),
        (1.0, 3.0),
        (2.0, 2.0),
        (3.0, 1.0),
        (4.0, 0.0),
    ]


def test_maximizing_an_objective_flips_which_points_are_dominated():
    study = _analytic_study(
        objectives=(Objective(name="f", sense=ObjectiveSense.MAXIMIZE), Objective(name="g"))
    )
    result = run_study(study, _analytic_evaluate)
    senses = {o.name: o.sense for o in study.objectives}
    assert result.front_indices == _brute_force_front(result.points, senses)
    # Maximising f while still minimising g collapses the front onto the one corner that
    # is best at both — (4, 0), which is exactly on the feasibility boundary.
    assert [(p.parameters["x"], p.parameters["y"]) for p in result.front] == [(4.0, 0.0)]


def test_an_infeasible_point_is_kept_labelled_and_never_on_the_front():
    """The lighter-but-failing design is the one an infeasibility-blind sweep returns."""

    def evaluate(parameters: Mapping[str, float]) -> StudyEvaluation:
        x = parameters["x"]
        # Everything below x = 2 fails; the lightest thing in the box is the one that does.
        return StudyEvaluation(
            objectives={"f": x, "g": 0.0}, scorecard=_card(safety_factor=0.5 if x < 2.0 else 2.0)
        )

    study = _analytic_study(objectives=(Objective(name="f"),))
    result = run_study(study, evaluate)
    assert len(result.points) == 25
    infeasible = [p for p in result.points if not p.feasible]
    assert len(infeasible) == 10  # x in {0, 1}, five y values each
    # Kept, not dropped, and each names the check that stopped it.
    assert all(p.status is CheckStatus.FAIL for p in infeasible)
    assert all(p.governing_check == "strength" for p in infeasible)
    # The front is drawn over the feasible set only.
    assert all(p.feasible for p in result.front)
    assert min(p.objectives["f"] for p in result.front) == 2.0
    # And best() answers "the lightest that works", not "the lightest".
    assert result.best("f").objectives["f"] == 2.0
    assert min(p.objectives["f"] for p in result.points) == 0.0


def test_a_check_that_could_not_run_is_not_feasible():
    """NOT_EVALUATED is not a pass, and a front is the best thing that WORKS.

    A design whose governing check could not run has not been shown to work. Treating it
    as admissible would put a design nobody screened on the front, which is the silent
    green this whole library is built against.
    """
    study = _analytic_study(objectives=(Objective(name="f"),))
    result = run_study(
        study,
        lambda parameters: StudyEvaluation(
            objectives={"f": parameters["x"]}, scorecard=_card(safety_factor=None)
        ),
    )
    assert all(p.status is CheckStatus.NOT_EVALUATED for p in result.points)
    assert result.feasible == ()
    assert result.front == ()
    # "What is the lightest passing design" has an honest answer when nothing passes.
    assert result.best("f") is None
    assert "0 feasible" in result.summary()


def test_a_truncated_sweep_reports_provisional_and_names_its_coverage():
    study = _analytic_study(budget=7)
    result = run_study(study, _analytic_evaluate)
    assert len(result.points) == 7
    assert result.grid_size == 25
    assert result.provisional is True
    assert result.coverage == pytest.approx(7 / 25)
    assert "provisional" in result.summary()
    assert "optimal" not in result.summary()
    # The untruncated study is complete, and says that instead.
    full = run_study(_analytic_study(), _analytic_evaluate)
    assert full.provisional is False
    assert "complete" in full.summary()


def test_halton_covers_a_truncated_budget_where_a_grid_does_not():
    """The argument for a low-discrepancy sequence, in one assertion.

    At a budget below the grid, WHERE the points go decides whether the feasible region
    is found at all: a grid walks its first parameter slowest, so a truncated grid is the
    first few rows rather than a sample of the box.
    """

    def evaluate(parameters: Mapping[str, float]) -> StudyEvaluation:
        return StudyEvaluation(
            objectives={"f": parameters["x"]},
            scorecard=_card(safety_factor=2.0 if parameters["x"] > 3.0 else 0.5),
        )

    grid = run_study(_analytic_study(objectives=(Objective(name="f"),), budget=7), evaluate)
    halton = run_study(
        _analytic_study(
            objectives=(Objective(name="f"),), budget=7, strategy=SamplingStrategy.HALTON
        ),
        evaluate,
    )
    assert grid.feasible == ()  # the first 7 grid points are all x <= 1
    assert len(halton.feasible) > 0
    assert halton.provisional is True


def test_a_non_finite_objective_is_refused_rather_than_sorted():
    """NaN compares False against everything, so it would sit on the front dominating nothing."""
    study = _analytic_study(objectives=(Objective(name="f"),))
    for poison in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="for objective"):
            run_study(
                study,
                lambda parameters, poison=poison: StudyEvaluation(
                    objectives={"f": poison if parameters["x"] > 2.0 else parameters["x"]},
                    scorecard=_card(safety_factor=2.0),
                ),
            )
    # A declared objective the evaluator does not return is a study/evaluator mismatch,
    # not a missing value to be filled in with something.
    with pytest.raises(ValueError, match="no value for the declared objective"):
        run_study(
            study,
            lambda parameters: StudyEvaluation(
                objectives={"mass": 1.0}, scorecard=_card(safety_factor=2.0)
            ),
        )


def test_a_study_refuses_a_declaration_that_cannot_mean_anything():
    with pytest.raises(ValueError, match="at least one parameter"):
        Study(name="empty", parameters=(), objectives=(Objective(name="f"),))
    with pytest.raises(ValueError, match="needs at least one objective"):
        Study(
            name="objectiveless",
            parameters=(Parameter(name="x", low=0.0, high=1.0, unit="mm"),),
            objectives=(),
        )
    with pytest.raises(ValueError, match="duplicate parameter names"):
        Study(
            name="dupe",
            parameters=(
                Parameter(name="x", low=0.0, high=1.0, unit="mm"),
                Parameter(name="x", low=0.0, high=2.0, unit="mm"),
            ),
            objectives=(Objective(name="f"),),
        )
    with pytest.raises(ValueError, match="must be below high"):
        Parameter(name="x", low=1.0, high=1.0, unit="mm")
    with pytest.raises(ValueError, match="steps must be at least 2"):
        Parameter(name="x", low=0.0, high=1.0, unit="mm", steps=1)
    with pytest.raises(ValueError, match="bounds must be finite"):
        Parameter(name="x", low=0.0, high=math.inf, unit="mm")
    with pytest.raises(ValueError, match="budget must be at least 1"):
        _analytic_study(budget=0)
    with pytest.raises(KeyError, match="not an objective"):
        run_study(_analytic_study(), _analytic_evaluate).best("mass")


def test_the_grid_values_hit_both_bounds_exactly():
    parameter = Parameter(name="t", low=4.0, high=12.0, unit="mm", steps=5)
    assert parameter.grid_values() == (4.0, 6.0, 8.0, 10.0, 12.0)
    two = Parameter(name="t", low=4.0, high=12.0, unit="mm", steps=2)
    assert two.grid_values() == (4.0, 12.0)
