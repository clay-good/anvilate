"""Search: the best design found under a stated budget, checked against a published benchmark.

The speed reducer is re-implemented from its published definition: Cagnina, Esquivel and
Coello Coello, "Solving Engineering Optimization Problems with the Simple Constrained
Particle Swarm Optimizer", Informatica 32 (2008) 319-326, problem E03 (after Golinski),
with x3 (pinion teeth) an integer and 7.8 <= x5 <= 8.3. Its best known design is
x* = (3.5, 0.7, 17, 7.3, 7.8, 3.350214, 5.286683), weight 2,996.348165.
"""

from __future__ import annotations

from math import pi, sqrt

import pytest

from anvilate.explore import StudyEvaluation
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.search import (
    BEST_FOUND,
    SearchStrategy,
    SearchStudy,
    SearchVariable,
    VariableKind,
    run_search,
    violation,
)

_PUBLISHED_BEST = 2996.348165
_NAMES = ("x1", "x2", "x3", "x4", "x5", "x6", "x7")
_BOUNDS = ((2.6, 3.6), (0.7, 0.8), (17, 28), (7.3, 8.3), (7.8, 8.3), (2.9, 3.9), (5.0, 5.5))


def _weight(x1, x2, x3, x4, x5, x6, x7):
    return (0.7854 * x1 * x2**2 * (3.3333 * x3**2 + 14.9334 * x3 - 43.0934)
            - 1.508 * x1 * (x6**2 + x7**2) + 7.4777 * (x6**3 + x7**3)
            + 0.7854 * (x4 * x6**2 + x5 * x7**2))  # fmt: skip


def _constraints(x1, x2, x3, x4, x5, x6, x7):
    """The eleven constraints, each as g <= 0, in the source's normalized form."""
    return (
        27 / (x1 * x2**2 * x3) - 1,
        397.5 / (x1 * x2**2 * x3**2) - 1,
        1.93 * x4**3 / (x2 * x3 * x6**4) - 1,
        1.93 * x5**3 / (x2 * x3 * x7**4) - 1,
        sqrt((745 * x4 / (x2 * x3)) ** 2 + 16.9e6) / (110 * x6**3) - 1,
        sqrt((745 * x5 / (x2 * x3)) ** 2 + 157.5e6) / (85 * x7**3) - 1,
        x2 * x3 / 40 - 1,
        5 * x2 / x1 - 1,
        x1 / (12 * x2) - 1,
        (1.5 * x6 + 1.9) / x4 - 1,
        (1.1 * x7 + 1.9) / x5 - 1,
    )


def _evaluate(design):
    """Each constraint g <= 0 is a check whose safety factor is 1 / (1 + g)."""
    x = [design[n] for n in _NAMES]
    entries = tuple(ScorecardEntry.from_safety_factor(f"g{i}", computed=1 / (1 + g), required=1.0)
                    for i, g in enumerate(_constraints(*x), start=1))  # fmt: skip
    return StudyEvaluation(objectives={"weight": _weight(*x)}, scorecard=Scorecard(entries=entries))


def _reducer(**overrides) -> SearchStudy:
    variables = tuple(
        SearchVariable(name=n, low=a, high=b,
                       kind=VariableKind.INTEGER if n == "x3" else VariableKind.CONTINUOUS)
        for n, (a, b) in zip(_NAMES, _BOUNDS, strict=True)
    )  # fmt: skip
    return SearchStudy(**{"name": "speed reducer", "variables": variables,
                          "objective": "weight", "seed": 7, "evaluations": 4000,
                          "population": 30, **overrides})  # fmt: skip


def test_the_benchmark_as_written_reproduces_its_published_best():
    x_star = (3.5, 0.7, 17, 7.3, 7.8, 3.350214, 5.286683)
    assert _weight(*x_star) == pytest.approx(_PUBLISHED_BEST, abs=1e-3)
    assert max(_constraints(*x_star)) < 1e-5  # active to the source's printed precision


def test_the_speed_reducer_search_lands_on_the_published_best_and_every_feasible_point_is():
    result = run_search(_reducer(), _evaluate)
    best = result.points[result.best]
    assert best.objective == pytest.approx(_PUBLISHED_BEST, rel=5e-4)
    assert best.objective >= _PUBLISHED_BEST - 0.01  # never better than the published best
    assert best.values["x3"] == 17.0 and float(best.values["x3"]).is_integer()
    feasible = [p for p in result.points if p.feasible]
    assert len(feasible) > 100
    for point in feasible:
        x = [point.values[n] for n in _NAMES]
        assert max(_constraints(*x)) <= 1e-12, point.index
        assert all(low <= v <= high for v, (low, high) in zip(x, _BOUNDS, strict=True))
    assert len(result.history) == 4000 and result.exhausted


def test_a_search_reruns_identically_on_one_worker_or_four():
    one = run_search(_reducer(evaluations=400), _evaluate)
    four = run_search(_reducer(evaluations=400), _evaluate, workers=4)
    assert one.points == four.points and one.best == four.best
    other_seed = run_search(_reducer(evaluations=400, seed=8), _evaluate)
    assert other_seed.points != one.points


def test_the_result_is_never_called_optimal_and_a_better_neighbor_is_named():
    result = run_search(_reducer(evaluations=800), _evaluate)
    assert result.best is not None
    text = str(result) + result.label
    assert "optimal" not in text.lower() and BEST_FOUND in result.label
    if result.better_neighbor is not None:
        assert not result.confirmed and "not locally confirmed" in result.label
        assert "a feasible neighbor is better" in str(result)
    assert all(result.points[i].origin == "neighbor" for i in result.neighbors)


def test_a_start_is_evaluated_first_and_a_local_refinement_improves_on_it():
    start = {"x1": 3.6, "x2": 0.8, "x3": 20.0, "x4": 8.3, "x5": 8.3, "x6": 3.9, "x7": 5.5}
    continuous = tuple(v for v in _reducer().variables if v.name != "x3")
    fixed = {"x3": 17.0}

    def evaluate(design):
        return _evaluate({**design, **fixed})

    study = SearchStudy(name="refine", variables=continuous, objective="weight",
                        strategy=SearchStrategy.LOCAL, evaluations=600,
                        start={k: v for k, v in start.items() if k != "x3"})  # fmt: skip
    result = run_search(study, evaluate)
    assert result.points[0].origin == "start"
    assert result.points[result.best].objective < result.points[0].objective


def test_a_choice_needs_its_source_and_takes_only_its_values():
    with pytest.raises(ValueError, match="name no source"):
        SearchVariable(name="thickness", kind=VariableKind.CHOICE, choices=(6.0, 7.3, 8.0))
    plate = SearchVariable(name="thickness", kind=VariableKind.CHOICE, choices=(6.0, 8.0, 10.0),
                           source="mill stock list MS-2, rev 4")  # fmt: skip
    study = SearchStudy(name="plate", variables=(plate,), objective="mass", evaluations=20,
                        population=4)  # fmt: skip

    def evaluate(design):
        t = design["thickness"]
        card = Scorecard(entries=(ScorecardEntry.from_safety_factor(
            "bending", computed=t / 7.0, required=1.0),))  # fmt: skip
        return StudyEvaluation(objectives={"mass": t}, scorecard=card)

    result = run_search(study, evaluate)
    assert {p.values["thickness"] for p in result.points} <= {6.0, 8.0, 10.0}
    assert result.points[result.best].values["thickness"] == 8.0 and result.confirmed


@pytest.mark.parametrize(("kwargs", "said"), [
    ({"strategy": SearchStrategy.LOCAL}, "give start"),
    ({"start": {"x1": 3.0}}, "every variable"),
])  # fmt: skip
def test_an_incoherent_study_is_refused(kwargs, said):
    with pytest.raises(ValueError, match=said):
        _reducer(**kwargs)


def test_no_feasible_design_is_said_plainly():
    def never(design):
        card = Scorecard(entries=(ScorecardEntry.from_safety_factor("g", computed=0.5,
                                                                    required=1.0),))  # fmt: skip
        return StudyEvaluation(objectives={"weight": 1.0}, scorecard=card)

    result = run_search(_reducer(evaluations=40), never)
    assert result.best is None and result.label == "no feasible design found in 40 evaluations"
    assert result.neighbors == ()


def test_an_evaluator_that_omits_the_objective_or_returns_nan_is_refused():
    def nan(design):
        return StudyEvaluation(objectives={"weight": float("nan")},
                               scorecard=Scorecard(entries=()))  # fmt: skip

    with pytest.raises(RefusalError, match="finite number"):
        run_search(_reducer(evaluations=10), nan)

    def silent(design):
        return StudyEvaluation(objectives={}, scorecard=Scorecard(entries=()))

    with pytest.raises(RefusalError, match="no value for the objective"):
        run_search(_reducer(evaluations=10), silent)


def test_violation_measures_how_far_a_card_is_from_passing():
    passing = Scorecard(entries=(ScorecardEntry.from_safety_factor("a", computed=2, required=1),))
    short = Scorecard(entries=(ScorecardEntry.from_safety_factor("a", computed=0.5, required=1),
                               ScorecardEntry(name="b", status=CheckStatus.NOT_EVALUATED,
                                              detail="did not run")))  # fmt: skip
    assert violation(passing) == 0 and violation(short) == pytest.approx(1.5)


def test_the_seeded_stream_is_pinned_so_a_recorded_search_replays_on_any_interpreter():
    """The search draws from its own SplitMix64 stream rather than `random`, whose sampling
    algorithms change between Python releases. Pinned here: a change to the stream moves
    every recorded search, and must be a deliberate one."""
    from anvilate.search import _Stream

    stream = _Stream(7)
    assert [stream._next() for _ in range(3)] == [
        7191089600892374487,
        309689372594955804,
        16616101746815609346,
    ]
    picks = _Stream(7).distinct(range(10), 3)
    assert len(set(picks)) == 3 and all(0 <= p < 10 for p in picks)


# The pressure vessel, the same paper's problem E02 (after Sandgren): shell and head plate
# thicknesses are integer multiples of 0.0625 in from 1x to 99x, a sourced choice, and
# 10 <= x3, x4 <= 200. Best known x* = (0.8125, 0.4375, 42.098446, 176.636596), cost
# 6,059.714335.
_VESSEL_BEST = 6059.714335
_PLATE = tuple(k * 0.0625 for k in range(1, 100))
_PLATE_SOURCE = "Cagnina et al., Informatica 32 (2008), E02: integer multiples of 0.0625 in"


def _vessel_cost(x1, x2, x3, x4):
    return 0.6224 * x1 * x3 * x4 + 1.7781 * x2 * x3**2 + 3.1661 * x1**2 * x4 + 19.84 * x1**2 * x3


def _vessel(design):
    """g1..g4 of E02 as safety factors: each requirement over what it is held against."""
    x1, x2, x3, x4 = (design[n] for n in ("x1", "x2", "x3", "x4"))
    factors = {
        "shell thickness": x1 / (0.0193 * x3),
        "head thickness": x2 / (0.00954 * x3),
        "volume": (pi * x3**2 * x4 + 4 / 3 * pi * x3**3) / 1_296_000,
        "length": 240 / x4,
    }
    card = Scorecard(entries=tuple(ScorecardEntry.from_safety_factor(name, computed=f,
                                                                     required=1.0)
                                   for name, f in factors.items()))  # fmt: skip
    return StudyEvaluation(objectives={"cost": _vessel_cost(x1, x2, x3, x4)}, scorecard=card)


def test_the_pressure_vessel_takes_only_stocked_plate_and_lands_on_the_published_best():
    """The second mixed-variable benchmark: two choices from a sourced list, two continuous."""
    published = _vessel_cost(0.8125, 0.4375, 42.098446, 176.636596)
    assert published == pytest.approx(_VESSEL_BEST, abs=1e-3)
    plate = {"kind": VariableKind.CHOICE, "choices": _PLATE, "source": _PLATE_SOURCE}
    study = SearchStudy(
        name="pressure vessel", objective="cost", seed=7, evaluations=3000, population=30,
        variables=(SearchVariable(name="x1", **plate), SearchVariable(name="x2", **plate),
                   SearchVariable(name="x3", low=10, high=200),
                   SearchVariable(name="x4", low=10, high=200)),
    )  # fmt: skip
    result = run_search(study, _vessel)
    best = result.points[result.best]
    assert best.objective == pytest.approx(_VESSEL_BEST, rel=1e-4)
    assert (best.values["x1"], best.values["x2"]) == (0.8125, 0.4375)
    assert all(p.values["x1"] in _PLATE and p.values["x2"] in _PLATE for p in result.points)


def test_a_result_is_a_proposed_edit_and_applying_it_records_the_study():
    """Design optimization 1.6: the base document does not change until the diff is
    applied, and the applied edit says which study, seed and record chose the values."""
    from pathlib import Path

    from anvilate.search import apply_search_diff, search_diff
    from anvilate.spec import load_spec_yaml, parse_spec

    base = load_spec_yaml((Path(__file__).parents[1] / "examples" / "padeye.spec.yaml")
                          .read_text()).model_dump(mode="json")  # fmt: skip
    path = "element_params.thickness"
    thickness = SearchVariable(name=path, kind=VariableKind.CHOICE,
                               choices=(16.0, 20.0, 25.0, 30.0),
                               source="mill plate list MP-1, rev 2")  # fmt: skip
    study = SearchStudy(name="lighter lug", variables=(thickness,), objective="thickness",
                        evaluations=12, population=4)  # fmt: skip

    def evaluate(design):
        t = design[path]
        card = Scorecard(entries=(ScorecardEntry.from_safety_factor(
            "bearing", computed=t / 22.0, required=1.0),))  # fmt: skip
        return StudyEvaluation(objectives={"thickness": t}, scorecard=card)

    result = run_search(study, evaluate)
    diff = search_diff(result, {path: base["element_params"]["thickness"]["magnitude"]})
    assert diff.changes == ((path, 20.0, 25.0),)  # the lightest stocked plate that passes
    lighter = diff
    edited = apply_search_diff(base, lighter)
    assert base["element_params"]["thickness"] == {"magnitude": 20.0, "unit": "mm"}  # unchanged
    assert edited["element_params"]["thickness"] == {"magnitude": 25.0, "unit": "mm"}
    (record,) = edited["study_derived"]
    assert record == {"study": "lighter lug", "seed": 0, "record_sha256": diff.record_sha256,
                      "changed": [path]}  # fmt: skip
    assert parse_spec(edited).study_derived[0].changed == (path,)
    assert "proposes element_params.thickness: 20 -> 25" in str(lighter)
    with pytest.raises(RefusalError, match="holds no value at element_params.flange"):
        apply_search_diff(base, lighter.model_copy(
            update={"changes": (("element_params.flange", 1.0, 2.0),)}))  # fmt: skip


def test_a_search_with_no_feasible_design_proposes_no_edit():
    from anvilate.search import search_diff

    def never(design):
        card = Scorecard(entries=(ScorecardEntry.from_safety_factor("g", computed=0.5,
                                                                    required=1.0),))  # fmt: skip
        return StudyEvaluation(objectives={"weight": 1.0}, scorecard=card)

    with pytest.raises(RefusalError, match="proposes no edit"):
        search_diff(run_search(_reducer(evaluations=20), never), {})
