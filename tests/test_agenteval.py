"""Tests for the agent-driving eval vocabulary.

What is being pinned is not arithmetic — it is the set of ways a number here could flatter
a model that is worse. Three of them:

* **Averaging iterations over every run.** A model that gives up after one call would post
  the best iteration count in the field. Iterations are over completed runs, and are
  ``None`` rather than zero when nothing completed.
* **Folding the one-off opening into the loop.** A run that repaired twice would count one
  pass, because the second pass would go looking for a second ``compile_spec`` no correct
  run makes.
* **A task set that names only the operations a model happens to be good at.** The set is
  held against the live tool catalog in both directions: a task cannot name an operation
  that does not exist, and the set cannot leave a required operation untouched.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.agenteval import (
    AGENT_TASK_SET_VERSION,
    AgentEvalReport,
    AgentEvaluation,
    AgentRecommendationPolicy,
    AgentRunOutcome,
    AgentTask,
    AgentTaskSet,
    LocalModelRecommendation,
    ToolCall,
    assess_local_model_recommendation,
    default_task_set,
    default_versioned_task_set,
    evaluate_task_set,
    score_run_set,
    score_transcript,
    task_set_issues,
)
from anvilate.compilation import (
    CompilationMode,
    CompilationRecommendation,
    CompilationRecommendationPolicy,
    DecodingConfiguration,
)
from anvilate.mcp import REQUIRED_OPERATIONS, tool_catalog

LOOP = ("build_part", "run_validation", "read_scorecard")


def _task(task_id: str = "lug", **kwargs) -> AgentTask:
    defaults = {
        "task_id": task_id,
        "prompt": "size a lifting lug for 50 kN and tell me whether it passes",
        "prelude": ("compile_spec",),
        "required_tools": LOOP,
    }
    return AgentTask(**{**defaults, **kwargs})


def _calls(*names: str) -> list[ToolCall]:
    return [ToolCall(tool=name) for name in names]


# --- a call is well formed or it says why ---------------------------------------------


def test_a_failed_call_must_say_why():
    with pytest.raises(ValidationError, match="recorded as failed with no reason"):
        ToolCall(tool="build_part", failed=True)


def test_a_call_cannot_carry_an_error_and_be_recorded_as_succeeding():
    with pytest.raises(ValidationError, match="carries an error and is not recorded as failed"):
        ToolCall(tool="build_part", error="bad argument")


# --- a task has something to reach ----------------------------------------------------


def test_a_task_requiring_nothing_is_refused():
    """An empty transcript would complete it — including one from a model that never
    made a call."""
    with pytest.raises(ValidationError, match="an empty transcript"):
        _task(required_tools=())


def test_a_task_needs_an_id_and_a_prompt():
    with pytest.raises(ValidationError, match="must have an id"):
        _task(task_id="  ")
    with pytest.raises(ValidationError, match="has no prompt"):
        _task(prompt="")


# --- iterations count the loop, not the opening ---------------------------------------


def test_the_repair_loop_counts_as_two_iterations():
    run = score_transcript(
        _task(),
        _calls(*("compile_spec", *LOOP, *LOOP)),
    )
    assert run.completed
    assert run.iterations == 2, "the run built and checked twice; it compiled once"


def test_folding_the_opening_into_the_loop_would_undercount_it():
    """The reason ``prelude`` exists, asserted rather than argued.

    The same transcript scored against a task that requires compile → build → validate →
    read as one sequence counts a single pass, because the second pass goes looking for a
    second ``compile_spec`` that no correct run makes.
    """
    transcript = _calls(*("compile_spec", *LOOP, *LOOP))
    split = score_transcript(_task(), transcript)
    folded = score_transcript(_task(prelude=(), required_tools=("compile_spec", *LOOP)), transcript)
    assert (split.iterations, folded.iterations) == (2, 1)


def test_a_run_that_never_reached_the_opening_is_incomplete():
    run = score_transcript(_task(), _calls(*LOOP))
    assert not run.completed
    assert run.iterations == 0


def test_order_is_part_of_the_requirement():
    """Reading a scorecard before running the validation read a stale one."""
    run = score_transcript(
        _task(), _calls("compile_spec", "build_part", "read_scorecard", "run_validation")
    )
    assert not run.completed


def test_a_failed_call_does_not_satisfy_the_operation_it_named():
    good = score_transcript(_task(), _calls("compile_spec", *LOOP))
    calls = _calls("compile_spec", "build_part")
    calls.append(ToolCall(tool="run_validation", failed=True, error="unknown field 'laod'"))
    calls.extend(_calls("read_scorecard"))
    bad = score_transcript(_task(), calls)
    assert good.completed and not bad.completed
    assert bad.tool_call_errors == 1


def test_a_failed_call_is_not_a_failing_check():
    """A validation that comes back FAIL is a successful call — the model drove the tool
    and the tool told it the truth. Nothing in the transcript records the verdict, which
    is the point: this eval measures driving, not design."""
    run = score_transcript(_task(), _calls("compile_spec", *LOOP))
    assert run.completed and run.tool_call_errors == 0


def test_an_invented_tool_name_is_reported_separately_from_a_bad_argument():
    calls = _calls("compile_spec", "build_part")
    calls.append(ToolCall(tool="check_the_part", failed=True, error="no such tool"))
    calls.extend(_calls("run_validation", "read_scorecard"))
    run = score_transcript(_task(), calls)
    assert run.unknown_tools == ("check_the_part",)
    assert run.tool_call_errors == 1
    assert all(name in {t.name for t in tool_catalog()} for name in ("compile_spec", *LOOP))


def test_an_outcome_cannot_claim_a_completion_its_calls_do_not_show():
    """Every metric is derived from the calls, so there is no field to overstate."""
    fields = set(AgentRunOutcome.model_fields)
    assert fields == {"task_id", "required_tools", "prelude", "calls"}
    assert "completed" not in fields and "iterations" not in fields


# --- the report's three numbers stay three numbers ------------------------------------


def _report(**kwargs) -> AgentEvalReport:
    defaults = {
        "model_name": "a-local-7b",
        "client": "anvilate-cli",
        "harness": "3 retries, 32k context, tool-choice auto",
    }
    return AgentEvalReport(**{**defaults, **kwargs})


def test_there_is_no_single_success_number():
    report = _report(outcomes=(score_transcript(_task(), _calls("compile_spec", *LOOP)),))
    for forbidden in ("score", "success_rate", "success", "passed", "accuracy", "overall"):
        assert not hasattr(report, forbidden), (
            f"AgentEvalReport grew a {forbidden!r}. A model that abandons the hard tasks "
            "drives its iteration count down and its error count with it, and only the "
            "completion rate says so"
        )
    assert set(AgentEvalReport.model_fields) == {"model_name", "client", "harness", "outcomes"}


def test_iterations_are_averaged_over_completed_runs_only():
    """The failure mode in one assertion: a model that gave up on one task must not have
    its efficiency improved by the task it abandoned."""
    finished = score_transcript(_task("a"), _calls(*("compile_spec", *LOOP, *LOOP, *LOOP)))
    abandoned = score_transcript(_task("b"), _calls("compile_spec"))
    report = _report(outcomes=(finished, abandoned))
    assert report.completion_rate == pytest.approx(0.5)
    assert report.mean_iterations == pytest.approx(3.0), "not 1.5"


def test_a_run_that_completed_nothing_has_no_iteration_count():
    report = _report(outcomes=(score_transcript(_task(), _calls("compile_spec")),))
    assert report.completion_rate == 0.0
    assert report.mean_iterations is None, "zero would read as the most efficient run there is"
    assert "not evaluated" in report.summary()


def test_the_tool_call_error_rate_is_over_calls_not_tasks():
    calls = _calls("compile_spec", *LOOP)
    calls.append(ToolCall(tool="build_part", failed=True, error="missing 'material'"))
    report = _report(outcomes=(score_transcript(_task(), calls),))
    assert report.tool_call_error_rate == pytest.approx(1 / 5)


def test_a_report_over_no_tasks_is_refused():
    with pytest.raises(ValidationError, match="reported as not run"):
        _report(outcomes=())


@pytest.mark.parametrize("field", ["model_name", "client", "harness"])
def test_the_harness_configuration_is_required(field):
    """Completion and iteration counts move with the retry policy and the context window
    as much as with the model."""
    with pytest.raises(ValidationError, match=f"must state its {field}"):
        _report(
            outcomes=(score_transcript(_task(), _calls("compile_spec", *LOOP)),),
            **{field: " "},
        )


def test_a_task_scored_twice_is_refused():
    run = score_transcript(_task(), _calls("compile_spec", *LOOP))
    with pytest.raises(ValidationError, match="scores a task twice"):
        _report(outcomes=(run, run))


def test_a_task_nobody_attempted_is_an_error_not_an_omission():
    tasks = [_task("a"), _task("b")]
    with pytest.raises(ValueError, match="no transcript"):
        score_run_set(
            tasks,
            {"a": _calls("compile_spec", *LOOP)},
            model_name="m",
            client="c",
            harness="h",
        )


def test_a_model_that_made_no_call_scores_incomplete_rather_than_missing():
    report = score_run_set([_task("a")], {"a": []}, model_name="m", client="c", harness="h")
    assert report.completion_rate == 0.0
    assert report.tool_call_error_rate is None, (
        "0% errors beside 0% completion reads as a flawless run; nothing attempted is "
        "not nothing wrong"
    )
    assert "tool-call errors not evaluated" in report.summary()
    assert [o.task_id for o in report.incomplete()] == ["a"]


# --- the task set is held against the live tool surface -------------------------------


def _covering_set() -> list[AgentTask]:
    """A set that exercises every required operation, split arbitrarily across tasks."""
    operations = sorted(REQUIRED_OPERATIONS)
    return [_task(f"t{i}", prelude=(), required_tools=(name,)) for i, name in enumerate(operations)]


def test_a_covering_task_set_has_no_issues():
    assert task_set_issues(_covering_set()) == []


def test_the_coverage_gate_is_looking_at_a_real_number_of_operations():
    """A gate that compares against an empty set passes forever."""
    assert len(REQUIRED_OPERATIONS) == 8
    assert REQUIRED_OPERATIONS <= {tool.name for tool in tool_catalog()}


def test_a_task_naming_an_operation_the_catalog_does_not_expose_is_reported():
    tasks = [*_covering_set(), _task("extra", prelude=(), required_tools=("polish_the_part",))]
    issues = task_set_issues(tasks)
    assert any("polish_the_part" in issue and "does not expose" in issue for issue in issues)


def test_a_task_set_that_leaves_the_surface_untouched_is_reported():
    issues = task_set_issues([_task()])
    assert len(issues) == 1
    for name in REQUIRED_OPERATIONS - {"compile_spec", *LOOP}:
        assert name in issues[0]


def test_a_duplicate_task_id_is_reported():
    tasks = [*_covering_set(), _covering_set()[0]]
    assert any("appears twice" in issue for issue in task_set_issues(tasks))


def test_an_empty_task_set_is_reported():
    assert task_set_issues([]) == ["the task set is empty, so every model scores the same on it"]


def test_renaming_every_operation_breaks_the_task_set():
    """The gate resolves names against the live catalog, so a rename has to surface here
    rather than quietly narrowing what the eval covers."""
    assert task_set_issues(_covering_set()) == []
    renamed = [
        _task(f"t{i}", prelude=(), required_tools=(f"{name}_v2",))
        for i, name in enumerate(sorted(REQUIRED_OPERATIONS))
    ]
    issues = task_set_issues(renamed)
    assert len(issues) == len(REQUIRED_OPERATIONS) + 1, (
        "one issue per task naming an operation that does not exist, plus one for the "
        "surface none of them now touches"
    )


def test_an_outcome_cannot_be_copied_past_its_validators():
    """An empty requirement is reached vacuously at every position, which is an infinite
    loop rather than a wrong number — so the defence used to be that the copy *degrades*
    safely. It is now that the copy does not happen: `AgentRunOutcome` inherits
    `RevalidatedModel`, so the update is refused by the same validator the constructor ran.
    """
    run = score_transcript(_task(), _calls("compile_spec", *LOOP))
    with pytest.raises(ValidationError, match="no required operations"):
        run.model_copy(update={"required_tools": ()})


def test_the_default_task_set_covers_the_surface_it_claims_to():
    """The corpus half of `add-agent-skill-surface` 4.1, held against the live catalog.

    A completion rate is a claim about driving *Anvilate*, so the set has to reach every
    published operation — `task_set_issues` refuses one that leaves half the surface
    untouched, and this asserts the set it is given is the shipped one rather than a fixture
    that happens to pass.
    """
    from anvilate.agenteval import default_task_set, task_set_issues
    from anvilate.mcp import REQUIRED_OPERATIONS, tool_catalog

    tasks = default_task_set()
    assert len(tasks) >= 8, f"only {len(tasks)} tasks; the set has shrunk"
    assert task_set_issues(list(tasks)) == []

    exercised = {operation for task in tasks for operation in task.operations}
    from anvilate.mcp import CATALOG_OPERATIONS, CONTEXT_OPERATIONS

    assert exercised == REQUIRED_OPERATIONS
    assert {tool.name for tool in tool_catalog()} == (
        REQUIRED_OPERATIONS | CATALOG_OPERATIONS | CONTEXT_OPERATIONS
    )

    # A required call is a claim that no correct run skips it. `run_validation` and
    # `build_part` parse a document themselves, so a compile before them is allowed and never
    # required: requiring it marked correct runs incomplete, even where the run wrote the
    # document (measured 2026-10-09). The one task that needs it asks for no screen.
    assert not any(task.prelude for task in tasks)
    (compiling,) = [task for task in tasks if "compile_spec" in task.required_tools]
    assert compiling.required_tools == ("compile_spec",)
    assert all(task.notes and task.notes.strip() for task in tasks), (
        "a task with no note is a prompt whose grading rule nobody wrote down"
    )
    assert len({task.task_id for task in tasks}) == len(tasks)


# --- recommendation evidence is versioned and complete -------------------------------


def _agent_evaluation(*, model_name: str = "a-local-7b") -> AgentEvaluation:
    task_set = AgentTaskSet(version=AGENT_TASK_SET_VERSION, tasks=tuple(_covering_set()))
    transcripts = {task.task_id: _calls(*task.required_tools) for task in task_set.tasks}
    return evaluate_task_set(
        task_set,
        transcripts,
        model_name=model_name,
        client="anvilate-cli 1.4.0",
        harness="scaffold v3; 3 retries; 32k context; tool-choice auto",
    )


def _compilation_recommendation(*, recommended: bool = True) -> CompilationRecommendation:
    reasons = () if recommended else ("field correctness 70.0% is below 80.0%",)
    return CompilationRecommendation(
        task_set_version="1.0.0",
        configuration=DecodingConfiguration(
            backend="llama.cpp",
            model="a-local-7b",
            mode=CompilationMode.TWO_PASS,
            retry_budget=2,
        ),
        schema_validity=1.0,
        field_correctness=0.9 if recommended else 0.7,
        wrong_but_valid_rate=0.0,
        policy=CompilationRecommendationPolicy(
            task_set_version="1.0.0",
            minimum_schema_validity=0.9,
            minimum_field_correctness=0.8,
            maximum_wrong_but_valid_rate=0.1,
            reference="release policy 2026-09",
        ),
        recommended=recommended,
        reasons=reasons,
    )


def _agent_policy(**overrides) -> AgentRecommendationPolicy:
    values = {
        "task_set_version": AGENT_TASK_SET_VERSION,
        "minimum_completion_rate": 0.9,
        "maximum_mean_iterations": 2.0,
        "maximum_tool_call_error_rate": 0.05,
        "reference": "agent-driving release policy 2026-09",
    }
    values.update(overrides)
    return AgentRecommendationPolicy(**values)


def test_the_published_agent_corpus_and_evaluation_are_versioned_and_complete():
    task_set = default_versioned_task_set()
    assert task_set.version == AGENT_TASK_SET_VERSION == "1.2.0"
    assert task_set.tasks == default_task_set()

    evaluation = _agent_evaluation()
    assert evaluation.task_set_version == "1.2.0"
    assert evaluation.task_ids == tuple(outcome.task_id for outcome in evaluation.report.outcomes)


def test_a_versioned_agent_evaluation_refuses_a_partial_report():
    evaluation = _agent_evaluation()
    with pytest.raises(ValidationError, match="task set and report outcomes differ"):
        AgentEvaluation(
            task_set_version=evaluation.task_set_version,
            task_ids=(*evaluation.task_ids, "silently-skipped"),
            report=evaluation.report,
        )


def test_local_model_recommendation_requires_both_evidence_sets_to_clear_policy():
    decision = assess_local_model_recommendation(
        _compilation_recommendation(), _agent_evaluation(), _agent_policy()
    )
    assert isinstance(decision, LocalModelRecommendation)
    assert decision.recommended is True
    assert decision.reasons == ()
    for forbidden in ("score", "success_rate", "passed", "overall"):
        assert not hasattr(decision, forbidden)

    refused = assess_local_model_recommendation(
        _compilation_recommendation(recommended=False),
        _agent_evaluation(),
        _agent_policy(minimum_completion_rate=1.0),
    )
    assert refused.recommended is False
    assert refused.reasons == ("compilation: field correctness 70.0% is below 80.0%",)


def test_unattempted_agent_work_is_not_a_passing_zero_error_run():
    task_set = AgentTaskSet(version=AGENT_TASK_SET_VERSION, tasks=tuple(_covering_set()))
    evaluation = evaluate_task_set(
        task_set,
        {task.task_id: [] for task in task_set.tasks},
        model_name="a-local-7b",
        client="anvilate-cli 1.4.0",
        harness="scaffold v3; 3 retries; 32k context; tool-choice auto",
    )
    decision = assess_local_model_recommendation(
        _compilation_recommendation(), evaluation, _agent_policy()
    )
    assert decision.recommended is False
    assert decision.reasons == (
        "agent completion 0.0% is below 90.0%",
        "agent mean iterations were not evaluated because no task completed",
        "agent tool-call error rate was not evaluated because no call was made",
    )


def test_agent_iteration_and_tool_error_gates_fail_independently_of_completion():
    task_set = AgentTaskSet(version=AGENT_TASK_SET_VERSION, tasks=tuple(_covering_set()))
    transcripts = {}
    for task in task_set.tasks:
        required = task.required_tools[0]
        transcripts[task.task_id] = [
            *_calls(required, required, required),
            ToolCall(tool="invented", failed=True, error="no such tool"),
        ]
    evaluation = evaluate_task_set(
        task_set,
        transcripts,
        model_name="a-local-7b",
        client="anvilate-cli 1.4.0",
        harness="scaffold v3; 3 retries; 32k context; tool-choice auto",
    )
    decision = assess_local_model_recommendation(
        _compilation_recommendation(), evaluation, _agent_policy()
    )
    assert evaluation.report.completion_rate == 1.0
    assert decision.reasons == (
        "agent mean iterations 3.0 exceeds 2.0",
        "agent tool-call error rate 25.0% exceeds 5.0%",
    )


def test_joined_recommendation_refuses_stale_or_different_model_evidence():
    with pytest.raises(ValueError, match="agent evidence is stale"):
        assess_local_model_recommendation(
            _compilation_recommendation(),
            _agent_evaluation(),
            _agent_policy(task_set_version="2.0.0"),
        )
    with pytest.raises(ValueError, match="different models"):
        assess_local_model_recommendation(
            _compilation_recommendation(),
            _agent_evaluation(model_name="another-model"),
            _agent_policy(),
        )


def test_joined_recommendation_markdown_discloses_both_configurations_and_all_metrics():
    rendered = assess_local_model_recommendation(
        _compilation_recommendation(), _agent_evaluation(), _agent_policy()
    ).render_markdown()
    for expected in (
        "Compilation evidence",
        "Schema validity",
        "Field correctness",
        "Wrong-but-valid",
        "Agent-driving evidence",
        "Completion",
        "Mean iterations",
        "Tool-call errors",
        "anvilate-cli 1.4.0",
        "scaffold v3; 3 retries; 32k context; tool-choice auto",
        "agent-driving release policy 2026-09",
        "Overall decision: **recommended**",
    ):
        assert expected in rendered


def test_the_corpus_reaches_every_backed_operation():
    """The corpus measures the whole live surface rather than a favored subset."""
    from anvilate import mcp
    from anvilate.agenteval import default_task_set

    assert set(mcp._UNBUILT) == set()
    reached = {operation for task in default_task_set() for operation in task.operations}
    # Every pipeline operation. The catalog lookup is a reference an agent may read, not
    # a step it must take, so the corpus is not required to reach it.
    assert set(mcp._DISPATCH) - mcp.CATALOG_OPERATIONS - mcp.CONTEXT_OPERATIONS <= reached


# --- the published measurement -------------------------------------------------------


def test_the_published_skill_measurement_is_what_its_transcripts_score():
    """The table in docs/agent-driving-evals.md, recomputed from the saved outcomes.

    The rates are rebuilt by `AgentEvalReport` rather than read from the stored numbers, and
    each outcome must carry the current corpus's operations: a corpus edit leaves this
    measurement describing tasks that no longer exist, and it has to be re-run or relabelled
    rather than left standing beside the new set.
    """
    import json
    from pathlib import Path

    from anvilate.agenteval import AgentEvalReport

    root = Path(__file__).resolve().parent.parent
    results = json.loads(
        (root / "tools/agent-skill-measurement/results/2026-10-09.json").read_text("utf-8")
    )
    page = (root / "docs/agent-driving-evals.md").read_text("utf-8")
    corpus = {task.task_id: task for task in default_task_set()}
    for condition, label in (("baseline", "Baseline"), ("skill", "With the skill")):
        report = AgentEvalReport.model_validate(results[condition]["report"])
        for outcome in report.outcomes:
            task = corpus[outcome.task_id]
            assert (outcome.prelude, outcome.required_tools) == (
                task.prelude,
                task.required_tools,
            ), f"{outcome.task_id}: the corpus changed since this measurement"
        assert len(report.outcomes) == len(corpus)
        calls = sum(len(outcome.calls) for outcome in report.outcomes)
        errors = sum(outcome.tool_call_errors for outcome in report.outcomes)
        completed = sum(outcome.completed for outcome in report.outcomes)
        cost = sum(extra["cost_usd"] for extra in results[condition]["extra"].values())
        row = (
            f"| {label} | {completed} of {len(corpus)} ({report.completion_rate:.0%}) "
            f"| {report.mean_iterations:.1f} | {errors} of {calls} "
            f"({report.tool_call_error_rate:.0%}) | {calls} | ${cost:.2f} |"
        )
        assert row in page, row
