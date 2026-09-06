"""The compilation metrics keep the three numbers apart, and refuse the one that hides them.

Everything here is about one failure mode: a spec that the schema accepts and that says the
wrong thing. Constraining a small model's decoding drives schema validity to 100% and
*lowers* accuracy, so a single "success" figure over a constrained decoder rises while the
thing a user cares about falls. These tests pin the vocabulary that makes that visible.
"""

from __future__ import annotations

import pytest

from anvilate.compilation import (
    CompilationOutcome,
    CompilationReport,
    CompilationTask,
    FieldOutcome,
    field_value,
    score_candidate,
    score_task_set,
)
from anvilate.units import Quantity

_TASK = CompilationTask(
    task_id="lug-50kn",
    prompt="A lifting lug in A36 steel rated for a 50 kN vertical load, safety factor 2.",
    reference={
        "material.ref": "ASTM-A36",
        "load_cases.0.force": Quantity(magnitude=50.0, unit="kN"),
        "acceptance.min_safety_factor": 2.0,
    },
)

_RIGHT = {
    "material": {"ref": "ASTM-A36"},
    "load_cases": [{"force": {"magnitude": 50000.0, "unit": "N"}}],
    "acceptance": {"min_safety_factor": 2.0},
}


def _candidate(**overrides) -> dict:
    import copy

    candidate = copy.deepcopy(_RIGHT)
    candidate.update(overrides)
    return candidate


# --- the wrong-but-valid case ------------------------------------------------------------


def test_a_schema_valid_spec_with_the_wrong_load_is_counted_as_a_defect():
    """The case the module exists for. Nothing downstream can catch it: the spec validates,
    so every consumer treats it as an input somebody meant."""
    wrong = _candidate(load_cases=[{"force": {"magnitude": 50.0, "unit": "kip"}}])
    outcome = score_candidate(_TASK, wrong)
    assert outcome.schema_valid is True
    assert outcome.fully_correct is False
    assert outcome.wrong_but_valid is True
    assert "WRONG BUT VALID" in str(outcome)


def test_a_correct_compilation_is_not_flagged():
    outcome = score_candidate(_TASK, _RIGHT)
    assert outcome.fully_correct is True
    assert outcome.wrong_but_valid is False


def test_the_report_names_the_wrong_but_valid_candidates_not_just_the_rate():
    report = score_task_set(
        [_TASK, _TASK.model_copy(update={"task_id": "second"})],
        {
            "lug-50kn": _RIGHT,
            "second": _candidate(load_cases=[{"force": {"magnitude": 50.0, "unit": "kip"}}]),
        },
        configuration="two-pass, reason free then constrain",
    )
    assert [o.task_id for o in report.wrong_but_valid()] == ["second"]


# --- the three numbers stay three numbers -------------------------------------------------


def test_there_is_no_single_success_number():
    """A scalar over a constrained decoder is dominated by validity — the number constraint
    drives to 100% — while correctness falls. A reader handed one figure would watch the
    compiler improve as it got worse."""
    report = score_task_set(
        [_TASK], {"lug-50kn": _RIGHT}, configuration="single-pass, hard constrained"
    )
    for forbidden in ("score", "success_rate", "success", "passed", "accuracy", "overall"):
        assert not hasattr(report, forbidden), (
            f"CompilationReport grew a {forbidden!r}. Three numbers that can move in "
            "opposite directions do not average into a fourth that means anything"
        )
    assert set(CompilationReport.model_fields) == {"outcomes", "configuration", "citation"}


def test_validity_and_correctness_move_independently():
    """The finding in one assertion: a run where every candidate parses and most are wrong
    reports high validity and low correctness, and neither number hides the other."""
    tasks = [_TASK.model_copy(update={"task_id": f"t{i}"}) for i in range(4)]
    wrong = _candidate(load_cases=[{"force": {"magnitude": 50.0, "unit": "kip"}}])
    report = score_task_set(
        tasks,
        {"t0": _RIGHT, "t1": wrong, "t2": wrong, "t3": wrong},
        configuration="single-pass, hard constrained",
    )
    assert report.schema_validity == pytest.approx(1.0)
    assert report.field_correctness == pytest.approx(9 / 12)
    assert report.wrong_but_valid_rate == pytest.approx(0.75)
    summary = report.summary()
    assert "schema validity 100%" in summary
    assert "wrong-but-valid 75%" in summary


def test_the_report_states_how_it_was_decoded():
    """Validity and accuracy both move with the pass structure, so a number without its
    configuration cannot be compared with another one."""
    with pytest.raises(ValueError, match="how it was decoded"):
        score_task_set([_TASK], {"lug-50kn": _RIGHT}, configuration="  ")


# --- what does not count as correct -------------------------------------------------------


def test_a_field_the_candidate_omits_counts_against_correctness():
    """Skipping an absent field is how a compiler that omits half the spec scores well."""
    outcome = score_candidate(_TASK, {"material": {"ref": "ASTM-A36"}})
    missing = [f for f in outcome.fields if not f.matched]
    assert {f.path for f in missing} == {"load_cases.0.force", "acceptance.min_safety_factor"}
    assert all("does not carry this field" in f.detail for f in missing)
    assert outcome.correct_fields == 1


def test_an_unparseable_candidate_scores_zero_fields_rather_than_no_fields():
    """A compiler that produces nothing must not outscore one that produces something
    wrong, so its fields count in the denominator."""
    outcome = score_candidate(_TASK, None, parse_error="unexpected token at line 3")
    assert outcome.schema_valid is False
    assert outcome.correct_fields == 0
    assert len(outcome.fields) == 3
    assert all("did not parse" in f.detail for f in outcome.fields)
    # And it is not counted as wrong-but-valid: the schema caught this one.
    assert outcome.wrong_but_valid is False

    report = score_task_set(
        [_TASK], {}, parse_errors={"lug-50kn": "bad token"}, configuration="single-pass"
    )
    assert report.schema_validity == pytest.approx(0.0)
    assert report.field_correctness == pytest.approx(0.0)


def test_a_task_nobody_attempted_is_an_error_not_an_omission():
    """A run that skipped the hard tasks would otherwise publish the easy ones' numbers."""
    with pytest.raises(ValueError, match="neither a candidate nor a parse error"):
        score_task_set(
            [_TASK, _TASK.model_copy(update={"task_id": "skipped"})],
            {"lug-50kn": _RIGHT},
            configuration="single-pass",
        )


def test_a_null_field_is_not_the_same_as_a_missing_one():
    found, value = field_value(
        {"acceptance": {"min_safety_factor": None}}, "acceptance.min_safety_factor"
    )
    assert (found, value) == (True, None)
    assert field_value({"acceptance": {}}, "acceptance.min_safety_factor") == (False, None)


# --- comparison is dimensional ------------------------------------------------------------


@pytest.mark.parametrize(
    ("actual", "matches"),
    [
        ({"magnitude": 50000.0, "unit": "N"}, True),
        ({"magnitude": 50.0, "unit": "kN"}, True),
        ("50 kN", True),
        ({"magnitude": 50.0, "unit": "kip"}, False),
        ({"magnitude": 51.0, "unit": "kN"}, False),
        ({"magnitude": 50.0, "unit": "mm"}, False),
        ("fifty kilonewtons", False),
    ],
)
def test_a_quantity_is_compared_by_dimension_not_by_spelling(actual, matches):
    """Comparing against a reference rather than a string is the whole point: 50 kN and
    50000 N are the same answer, and 50 kN and 50 kip are not."""
    outcome = score_candidate(_TASK, _candidate(load_cases=[{"force": actual}]))
    force = next(f for f in outcome.fields if f.path == "load_cases.0.force")
    assert force.matched is matches


def test_an_incommensurable_unit_is_a_wrong_answer_not_an_incomparable_one():
    """Reading kilonewtons as millimetres is the failure a dimensional comparison exists to
    catch. Reporting it as "could not compare" would hide it."""
    outcome = score_candidate(_TASK, _candidate(load_cases=[{"force": "50 mm"}]))
    force = next(f for f in outcome.fields if f.path == "load_cases.0.force")
    assert force.matched is False
    assert "not commensurable" in force.detail


def test_a_real_design_spec_can_be_scored_directly():
    """The scorer follows attributes as well as mapping keys, so a parsed DesignSpec goes
    straight in without being dumped first — which matters because the compiler's output is
    a spec, and dumping it first would score the serialization rather than the answer."""
    from anvilate.spec import (
        AcceptanceCriteria,
        DesignSpec,
        LoadCase,
        LoadKind,
        Manufacturing,
        ManufacturingProcess,
        MaterialRef,
        Provenanced,
        ValidationTier,
    )
    from anvilate.units import UnitSystem

    spec = DesignSpec(
        name="lug",
        description="a lifting lug",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        load_cases=[
            LoadCase(
                name="hoist",
                kind=LoadKind.STATIC,
                applied_to="pin_bore",
                force=Quantity.parse("50 kN"),
            )
        ],
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )
    task = CompilationTask(
        task_id="lug-attrs",
        prompt=_TASK.prompt,
        reference={
            "material.ref": "ASTM-A36",
            "load_cases.0.force": Quantity(magnitude=50.0, unit="kN"),
            "load_cases.0.kind": LoadKind.STATIC,
        },
    )
    assert score_candidate(task, spec).fully_correct is True

    # And a spec that reads the load in the wrong unit is wrong-but-valid: it is a perfectly
    # legal DesignSpec, so nothing downstream will object to it.
    wrong = spec.model_copy(
        update={
            "load_cases": [
                spec.load_cases[0].model_copy(update={"force": Quantity.parse("50 kip")})
            ]
        }
    )
    assert score_candidate(task, wrong).wrong_but_valid is True


# --- the models refuse states that would hide the measurement ----------------------------


def test_an_outcome_cannot_be_valid_and_carry_a_parse_error():
    with pytest.raises(ValueError, match="one of the two is wrong"):
        CompilationOutcome(
            task_id="t",
            schema_valid=True,
            fields=(FieldOutcome(path="a", expected="1", actual="1", matched=True, detail="ok"),),
            parse_error="boom",
        )


def test_an_invalid_outcome_must_say_why():
    with pytest.raises(ValueError, match="recorded as schema-invalid with no reason"):
        CompilationOutcome(
            task_id="t",
            schema_valid=False,
            fields=(FieldOutcome(path="a", expected="1", actual=None, matched=False, detail="x"),),
        )


def test_an_outcome_that_compared_nothing_is_refused():
    with pytest.raises(ValueError, match="compared no fields"):
        CompilationOutcome(task_id="t", schema_valid=True, fields=())


def test_a_task_with_no_reference_fields_is_refused():
    """Every output would score as fully correct — including an empty one."""
    with pytest.raises(ValueError, match="states no reference fields"):
        CompilationTask(task_id="t", prompt="do something", reference={})


def test_a_report_over_no_tasks_is_refused():
    with pytest.raises(ValueError, match="reported as not run"):
        CompilationReport(outcomes=(), configuration="single-pass")


def test_a_report_cannot_score_one_task_twice():
    outcome = score_candidate(_TASK, _RIGHT)
    with pytest.raises(ValueError, match="scores a task twice"):
        CompilationReport(outcomes=(outcome, outcome), configuration="single-pass")


def test_the_report_carries_the_caveat_it_is_screening_and_prints_it():
    """The field was checked and the rendering was not, which is a decorative assertion.

    `citation` is the argument for the shape of the numbers beside it — three figures rather
    than one, because a single score is dominated by schema validity and would show the
    compiler improving as it gets worse. It has carried that source, and the words "screening
    measurement, not a certified benchmark", since the model was written. Nothing printed it:
    the only reading a person sees was three percentages with nothing saying what they are
    not, and the only test on the field asserted `"arXiv" in report.citation`.
    """
    report = score_task_set([_TASK], {"lug-50kn": _RIGHT}, configuration="single-pass")
    assert "not a certified benchmark" in report.citation
    assert "arXiv" in report.citation
    assert report.citation in report.render()
    # Not in the one-line summary, which is a report pane's headline: a two-sentence
    # citation there pushes the numbers off the end.
    assert report.citation not in report.summary()


def test_every_field_of_a_compilation_report_reaches_a_rendering():
    """The property that found the citation, kept: move a field and the rendering moves.

    Over the model's own field list rather than one restated here, so a fourth field cannot
    land unrendered — which is exactly how `citation` sat unprinted from the day it was
    added, with a test asserting its *value* and none asserting it was ever shown.
    """
    from anvilate.compilation import CompilationReport

    report = score_task_set([_TASK], {"lug-50kn": _RIGHT}, configuration="single-pass")
    rendered = report.render()
    moved = {
        "outcomes": report.outcomes
        + (score_candidate(_TASK.model_copy(update={"task_id": "b"}), _RIGHT),),
        "configuration": "two-pass",
        "citation": "a different source entirely, and still screening",
    }
    assert set(moved) == set(CompilationReport.model_fields), (
        "CompilationReport's fields and the ones moved here have diverged: "
        f"unmoved {sorted(set(CompilationReport.model_fields) - set(moved))}"
    )
    for field, value in moved.items():
        assert report.model_copy(update={field: value}).render() != rendered, (
            f"moving {field} left the rendering identical"
        )


def test_the_render_puts_the_worst_task_first():
    tasks = [_TASK.model_copy(update={"task_id": f"t{i}"}) for i in range(3)]
    report = score_task_set(
        tasks,
        {"t0": _RIGHT, "t1": _candidate(load_cases=[{"force": "50 kip"}])},
        parse_errors={"t2": "unexpected token"},
        configuration="single-pass",
    )
    lines = report.render().splitlines()
    assert lines[1].strip().startswith("t2:")
    # -1 is the caveat the tasks are under; the tasks end one line above it.
    assert lines[-2].strip().startswith("t0:")
    assert lines[-1] == report.citation


def test_a_field_that_was_never_compared_does_not_read_like_one_that_was_wrong():
    """`FieldOutcome`'s docstring makes this the point of carrying `detail`: "a compiler
    that omits fields must not look like one that gets them wrong". The rendering dropped
    it, so "not compared — the candidate did not parse" and "the candidate does not carry
    this field" both printed as `expected X, got —`.
    """
    from anvilate.compilation import FieldOutcome

    unparsed = FieldOutcome(
        path="material.ref",
        expected="ASTM-A36",
        actual=None,
        matched=False,
        detail="not compared — the candidate did not parse",
    )
    absent = FieldOutcome(
        path="material.ref",
        expected="ASTM-A36",
        actual=None,
        matched=False,
        detail="the candidate does not carry this field",
    )
    assert str(unparsed) != str(absent)
    assert "did not parse" in str(unparsed)
    assert "does not carry this field" in str(absent)

    # A wrong value still shows what was produced, and says why it missed.
    wrong = FieldOutcome(
        path="load.magnitude",
        expected="50 kN",
        actual="50 kip",
        matched=False,
        detail="units differ",
    )
    assert str(wrong) == "[MISS] load.magnitude: expected 50 kN, got 50 kip — units differ"

    # A match needs no reason, and `_compare` gives every match the detail "agreed" — so
    # this has to be asserted against a *populated* detail, not an empty one. With an empty
    # one the mutation that shows detail on every outcome survives, and every matched line
    # in a report picks up a trailing "— agreed".
    ok = FieldOutcome(
        path="material.ref",
        expected="ASTM-A36",
        actual="ASTM-A36",
        matched=True,
        detail="agreed",
    )
    assert str(ok) == "[match] material.ref: expected ASTM-A36, got ASTM-A36"


def test_a_celsius_reference_is_compared_as_a_temperature_not_as_a_string():
    """The grader reads a reference value with `Quantity.parse`, which refused Celsius.

    A task whose reference said `"400 degC"` came back as *not a quantity*, so the
    comparison fell through to string equality — and a candidate that produced the right
    temperature, in the right unit, spelled the way the library renders it (`400 °C`) was
    graded wrong. The spelling is not the answer; the temperature is.
    """
    task = CompilationTask(
        task_id="celsius",
        prompt="a line running at 400 °C",
        reference={"design_temperature": "400 degC"},
    )
    for spelling in ("400 degC", "400 °C", "673.15 K"):
        outcome = score_candidate(task, {"design_temperature": spelling})
        (field,) = outcome.fields
        assert field.matched, f"{spelling} is the same temperature and graded {field.detail}"

    # A different temperature is still wrong, and says so as a temperature.
    wrong = score_candidate(task, {"design_temperature": "200 degC"})
    assert not wrong.fields[0].matched
    assert "200 °C" in wrong.fields[0].detail

    # And an angle, the other family the front door used to refuse: a reference in degrees
    # against a candidate in radians is the same angle, not a mismatch.
    angles = CompilationTask(
        task_id="angle",
        prompt="a 30 degree miter",
        reference={"miter_angle": "30 degree"},
    )
    assert score_candidate(angles, {"miter_angle": "0.5235987755982988 rad"}).fields[0].matched
    assert not score_candidate(angles, {"miter_angle": "45 degree"}).fields[0].matched
