"""The compilation metrics keep the three numbers apart, and refuse the one that hides them.

Everything here is about one failure mode: a spec that the schema accepts and that says the
wrong thing. Constraining a small model's decoding drives schema validity to 100% and
*lowers* accuracy, so a single "success" figure over a constrained decoder rises while the
thing a user cares about falls. These tests pin the vocabulary that makes that visible.
"""

from __future__ import annotations

import json

import pytest

from anvilate.compilation import (
    COMPILATION_TASK_SET_VERSION,
    CompilationCandidateError,
    CompilationEvaluation,
    CompilationFailure,
    CompilationMode,
    CompilationOutcome,
    CompilationRecommendation,
    CompilationRecommendationPolicy,
    CompilationReport,
    CompilationTask,
    CompilationTaskSet,
    FieldOutcome,
    LlamaCppBackend,
    LlamaCppError,
    OllamaBackend,
    OllamaError,
    assess_compilation_recommendation,
    compile_intent,
    default_compilation_task_set,
    evaluate_task_set,
    field_value,
    score_candidate,
    score_task_set,
    task_set_issues,
)
from anvilate.contracts import spec_json_schema
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

_VALID_SPEC = {
    "name": "compiled_lug",
    "description": "A compiled lifting lug.",
    "units": {"value": "SI", "origin": "user_stated"},
    "material": {"ref": "ASTM-A36"},
    "manufacturing": {"process": "cnc_milling"},
    "acceptance": {"tiers": ["T1_analytical"]},
}


class _Backend:
    name = "test-backend"
    model = "small-local-model"

    def __init__(self, outputs, *, two_pass=True, reasoning="private chain of thought"):
        self.supports_two_pass = two_pass
        self.outputs = iter(outputs)
        self.reasoning = reasoning
        self.reason_calls = []
        self.package_calls = []

    def reason(self, prompt):
        self.reason_calls.append(prompt)
        return self.reasoning

    def package_spec(self, prompt, *, schema, reasoning, validation_error):
        self.package_calls.append((prompt, schema, reasoning, validation_error))
        return next(self.outputs)


class _OllamaTransport:
    def __init__(self, contents: list[str | bytes]):
        self.contents = iter(contents)
        self.calls: list[tuple[str, dict, float]] = []

    def __call__(self, url: str, body: bytes, timeout: float) -> bytes:
        self.calls.append((url, json.loads(body), timeout))
        content = next(self.contents)
        if isinstance(content, bytes):
            return content
        return json.dumps({"message": {"role": "assistant", "content": content}}).encode()


class _LlamaCppTransport:
    def __init__(self, contents: list[str | bytes]):
        self.contents = iter(contents)
        self.calls: list[tuple[str, dict, float]] = []

    def __call__(self, url: str, body: bytes, timeout: float) -> bytes:
        self.calls.append((url, json.loads(body), timeout))
        content = next(self.contents)
        if isinstance(content, bytes):
            return content
        return json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": content}}]}
        ).encode()


# --- the compiler boundary ---------------------------------------------------------------


def test_two_pass_compilation_reasons_free_then_returns_only_validated_spec_ir():
    backend = _Backend([_VALID_SPEC])
    result = compile_intent("Make a lifting lug.", backend)

    assert result.spec.name == "compiled_lug"
    assert backend.reason_calls == ["Make a lifting lug."]
    (_, schema, reasoning, validation_error) = backend.package_calls[0]
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert reasoning == "private chain of thought"
    assert validation_error is None
    assert result.provenance.configuration.mode is CompilationMode.TWO_PASS
    assert result.provenance.reasoning == reasoning
    assert result.provenance.attempts == 1


def test_invalid_packaging_is_retried_with_the_validation_error_and_never_returned():
    backend = _Backend([{"name": "not enough"}, _VALID_SPEC])
    result = compile_intent("Make a lifting lug.", backend, retry_budget=1)

    assert result.provenance.attempts == 2
    assert len(result.provenance.validation_errors) == 1
    assert backend.package_calls[0][3] is None
    assert backend.package_calls[1][3] == result.provenance.validation_errors[0]
    assert "description" in backend.package_calls[1][3]


def test_exhausted_packaging_is_a_failure_with_every_rejected_attempt_recorded():
    from anvilate.refusal import RefusalError

    backend = _Backend([{"name": "still invalid"}] * 3)
    with pytest.raises(CompilationFailure, match="failed after 3 attempts") as failure:
        compile_intent("Make a lifting lug.", backend, retry_budget=2)

    assert isinstance(failure.value, RefusalError)
    assert isinstance(failure.value, ValueError), "the public exception hierarchy changed"
    provenance = failure.value.provenance
    assert provenance.succeeded is False
    assert provenance.attempts == 3
    assert len(provenance.validation_errors) == 3
    assert len(failure.value.remedies) == 1
    remedy = failure.value.remedies[0]
    assert remedy.action == "correct and recompile"
    assert remedy.subject == (
        "the rejected Spec IR candidate from test-backend model small-local-model"
    )
    assert "Design Spec JSON Schema" in remedy.source
    assert "provenance.validation_errors" in remedy.source


def test_a_backend_without_two_pass_support_uses_an_explicit_recorded_fallback():
    backend = _Backend([_VALID_SPEC], two_pass=False)
    result = compile_intent("Make a lifting lug.", backend)

    assert backend.reason_calls == []
    assert backend.package_calls[0][2] is None
    assert result.provenance.reasoning is None
    assert result.provenance.configuration.mode is CompilationMode.SINGLE_PASS_FALLBACK


def test_reasoning_is_provenance_and_never_reaches_the_spec_or_its_screening_result():
    from anvilate.screening import screen_spec

    sentinel = "PRIVATE-REASONING-MUST-NOT-CROSS"
    result = compile_intent("Make a lifting lug.", _Backend([_VALID_SPEC], reasoning=sentinel))
    spec_document = result.spec.model_dump_json()
    card_document = screen_spec(result.spec).model_dump_json()

    assert sentinel in result.provenance.reasoning
    assert sentinel not in spec_document
    assert sentinel not in card_document


def test_the_retry_budget_is_bounded_before_the_backend_runs():
    backend = _Backend([_VALID_SPEC])
    with pytest.raises(ValueError, match="less than or equal to 5"):
        compile_intent("Make a lifting lug.", backend, retry_budget=6)
    assert backend.reason_calls == []
    assert backend.package_calls == []


def test_ollama_runs_an_unconstrained_pass_then_packages_under_the_exact_schema():
    transport = _OllamaTransport(["identified stated inputs", json.dumps(_VALID_SPEC)])
    backend = OllamaBackend(model="qwen3:8b", transport=transport)

    result = compile_intent("Make a lifting lug.", backend)

    assert result.spec.name == "compiled_lug"
    assert result.provenance.reasoning == "identified stated inputs"
    assert len(transport.calls) == 2
    reason_url, reason_request, timeout = transport.calls[0]
    package_url, package_request, _ = transport.calls[1]
    assert reason_url == package_url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 120.0
    assert reason_request["stream"] is False
    assert "format" not in reason_request
    assert package_request["stream"] is False
    assert package_request["options"] == {"temperature": 0}
    assert package_request["format"]["$schema"] == ("https://json-schema.org/draft/2020-12/schema")
    assert "identified stated inputs" in package_request["messages"][1]["content"]


def test_ollama_candidate_json_failure_is_bounded_and_retried_with_context():
    transport = _OllamaTransport(["reasoning", "not json", json.dumps(_VALID_SPEC)])
    result = compile_intent(
        "Make a lifting lug.",
        OllamaBackend(model="local", transport=transport),
        retry_budget=1,
    )

    assert result.provenance.attempts == 2
    assert result.provenance.validation_errors == (
        "Ollama constrained response was not JSON: Expecting value: line 1 column 1 (char 0)",
    )
    assert result.provenance.validation_errors[0] in transport.calls[2][1]["messages"][1]["content"]


def test_ollama_refuses_nonlocal_endpoints_and_invalid_service_responses():
    with pytest.raises(ValueError, match="loopback origin"):
        OllamaBackend(model="local", endpoint="https://models.example.com")

    service_error = _OllamaTransport([b'{"error":"model not found"}'])
    with pytest.raises(OllamaError, match="model not found"):
        OllamaBackend(model="missing", transport=service_error).reason("Compile this.")

    malformed = _OllamaTransport([b'{"message":{"content":""}}'])
    with pytest.raises(OllamaError, match="no nonblank message.content"):
        OllamaBackend(model="local", transport=malformed).reason("Compile this.")

    oversized = _OllamaTransport([b"x" * (4 * 1024 * 1024 + 1)])
    with pytest.raises(OllamaError, match="4,194,304-byte limit"):
        OllamaBackend(model="local", transport=oversized).reason("Compile this.")


def test_ollama_construction_is_offline_and_candidate_errors_are_distinct():
    from anvilate.refusal import RefusalError

    calls = 0

    def transport(url: str, body: bytes, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return json.dumps({"message": {"content": "[]"}}).encode()

    backend = OllamaBackend(model="local", transport=transport)
    assert calls == 0
    with pytest.raises(CompilationCandidateError, match="must be a JSON object") as refused:
        backend.package_spec(
            "Compile this.", schema={"type": "object"}, reasoning=None, validation_error=None
        )
    assert isinstance(refused.value, RefusalError)
    assert isinstance(refused.value, ValueError), "the public exception hierarchy changed"
    assert len(refused.value.remedies) == 1
    remedy = refused.value.remedies[0]
    assert remedy.action == "replace"
    assert remedy.subject == "the rejected constrained response from Ollama"
    assert remedy.source == "the Design Spec JSON Schema supplied to package_spec"
    assert calls == 1


def test_llama_cpp_runs_an_unconstrained_pass_then_packages_under_the_exact_schema():
    transport = _LlamaCppTransport(["identified stated inputs", json.dumps(_VALID_SPEC)])
    backend = LlamaCppBackend(model="qwen3-8b.gguf", transport=transport)

    result = compile_intent("Make a lifting lug.", backend)

    assert result.spec.name == "compiled_lug"
    assert result.provenance.reasoning == "identified stated inputs"
    assert result.provenance.configuration.backend == "llama.cpp"
    assert len(transport.calls) == 2
    reason_url, reason_request, timeout = transport.calls[0]
    package_url, package_request, _ = transport.calls[1]
    assert reason_url == package_url == "http://127.0.0.1:8080/v1/chat/completions"
    assert timeout == 120.0
    assert reason_request["stream"] is False
    assert "response_format" not in reason_request
    assert package_request["stream"] is False
    assert package_request["temperature"] == 0
    assert package_request["response_format"] == {
        "type": "json_object",
        "schema": spec_json_schema(),
    }
    assert package_request["response_format"]["schema"]["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert "identified stated inputs" in package_request["messages"][1]["content"]


def test_llama_cpp_candidate_json_failure_is_bounded_and_retried_with_context():
    transport = _LlamaCppTransport(["reasoning", "not json", json.dumps(_VALID_SPEC)])
    result = compile_intent(
        "Make a lifting lug.",
        LlamaCppBackend(model="local.gguf", transport=transport),
        retry_budget=1,
    )

    assert result.provenance.attempts == 2
    assert result.provenance.validation_errors == (
        "llama.cpp constrained response was not JSON: Expecting value: line 1 column 1 (char 0)",
    )
    assert result.provenance.validation_errors[0] in transport.calls[2][1]["messages"][1]["content"]


def test_llama_cpp_refuses_nonlocal_endpoints_and_invalid_service_responses():
    with pytest.raises(ValueError, match="loopback origin"):
        LlamaCppBackend(model="local.gguf", endpoint="https://models.example.com")

    service_error = _LlamaCppTransport([b'{"error":{"message":"model not loaded"}}'])
    with pytest.raises(LlamaCppError, match="model not loaded"):
        LlamaCppBackend(model="missing.gguf", transport=service_error).reason("Compile this.")

    malformed = _LlamaCppTransport([b'{"choices":[]}'])
    with pytest.raises(LlamaCppError, match=r"choices\[0\]\.message\.content"):
        LlamaCppBackend(model="local.gguf", transport=malformed).reason("Compile this.")

    oversized = _LlamaCppTransport([b"x" * (4 * 1024 * 1024 + 1)])
    with pytest.raises(LlamaCppError, match="4,194,304-byte limit"):
        LlamaCppBackend(model="local.gguf", transport=oversized).reason("Compile this.")


def test_llama_cpp_construction_is_offline_and_candidate_errors_are_distinct():
    calls = 0

    def transport(url: str, body: bytes, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return json.dumps({"choices": [{"message": {"content": "[]"}}]}).encode()

    backend = LlamaCppBackend(model="local.gguf", transport=transport)
    assert calls == 0
    with pytest.raises(CompilationCandidateError, match="must be a JSON object"):
        backend.package_spec(
            "Compile this.", schema={"type": "object"}, reasoning=None, validation_error=None
        )
    assert calls == 1


# --- the versioned task corpus -----------------------------------------------------------


def test_the_default_compilation_corpus_is_versioned_and_spans_distinct_tasks():
    task_set = default_compilation_task_set()
    assert task_set.version == COMPILATION_TASK_SET_VERSION
    assert len(task_set.tasks) == 6
    assert len({task.task_id for task in task_set.tasks}) == len(task_set.tasks)
    referenced = {path for task in task_set.tasks for path in task.reference}
    assert {
        "material.ref",
        "manufacturing.process",
        "interfaces.0.ref",
        "load_cases.0.force",
        "dimensions.0.tolerance.designation",
        "element_params.flow_rate",
    } <= referenced


def test_every_default_reference_path_resolves_in_a_published_schema():
    assert task_set_issues(default_compilation_task_set()) == ()


def test_the_task_path_gate_detects_stale_spec_and_element_field_names():
    source = default_compilation_task_set()
    spec_typo = CompilationTask(
        task_id="stale-spec-field",
        prompt="A task with a stale field.",
        reference={"manufacturing.proces": "turning"},
    )
    element_typo = CompilationTask(
        task_id="stale-element-field",
        prompt="A task with a stale pack field.",
        reference={
            "element_type": "pipe_run",
            "element_params.flowrate": Quantity.parse("25 gal/min"),
        },
    )
    broken = source.model_copy(update={"tasks": source.tasks + (spec_typo, element_typo)})
    issues = task_set_issues(broken)
    assert any("manufacturing.proces" in issue for issue in issues)
    assert any("element_params.flowrate" in issue for issue in issues)


def test_a_task_set_refuses_an_unversioned_or_duplicate_corpus():
    task = default_compilation_task_set().tasks[0]
    with pytest.raises(ValueError, match="version must be semantic"):
        CompilationTaskSet(version="next", tasks=(task,))
    with pytest.raises(ValueError, match="repeats task ids"):
        CompilationTaskSet(version="1.0.0", tasks=(task, task))


def _evaluation_task_set() -> CompilationTaskSet:
    return CompilationTaskSet(
        version="1.0.0",
        tasks=(
            CompilationTask(
                task_id="valid",
                prompt="Compile the valid lug.",
                reference={"name": "compiled_lug", "material.ref": "ASTM-A36"},
            ),
            CompilationTask(
                task_id="invalid",
                prompt="Compile another lug.",
                reference={"name": "another_lug"},
            ),
        ),
    )


def test_evaluation_retains_every_success_and_bounded_failure_then_scores_all_tasks():
    backend = _Backend([_VALID_SPEC, *([{"name": "invalid"}] * 3)])
    evaluation = evaluate_task_set(_evaluation_task_set(), backend)

    assert isinstance(evaluation, CompilationEvaluation)
    assert [attempt.task_id for attempt in evaluation.attempts] == ["valid", "invalid"]
    assert evaluation.attempts[0].result is not None
    assert evaluation.attempts[1].failure is not None
    assert evaluation.attempts[1].failure.succeeded is False
    assert evaluation.report.schema_validity == pytest.approx(0.5)
    assert evaluation.report.field_correctness == pytest.approx(2 / 3)
    assert "task set 1.0.0" in evaluation.report.configuration
    assert "test-backend" in evaluation.report.configuration
    assert "small-local-model" in evaluation.report.configuration
    assert "two_pass" in evaluation.report.configuration
    assert "schema 1.18.0" in evaluation.report.configuration
    assert "retry budget 2" in evaluation.report.configuration


def test_backend_identity_changes_attribution_not_the_spec_contract_or_outcomes():
    task_set = CompilationTaskSet(version="1.0.0", tasks=(_evaluation_task_set().tasks[0],))
    local = _Backend([_VALID_SPEC])
    cloud = _Backend([_VALID_SPEC])
    cloud.name = "user-cloud-endpoint"
    cloud.model = "cloud-model"

    local_run = evaluate_task_set(task_set, local)
    cloud_run = evaluate_task_set(task_set, cloud)
    assert local_run.report.outcomes == cloud_run.report.outcomes
    assert local_run.attempts[0].result.spec == cloud_run.attempts[0].result.spec
    assert local_run.report.configuration != cloud_run.report.configuration


def test_an_unexpected_backend_defect_aborts_instead_of_becoming_a_low_score():
    class BrokenBackend(_Backend):
        def package_spec(self, prompt, *, schema, reasoning, validation_error):
            raise RuntimeError("backend transport broke")

    with pytest.raises(RuntimeError, match="transport broke"):
        evaluate_task_set(
            CompilationTaskSet(version="1.0.0", tasks=(_evaluation_task_set().tasks[0],)),
            BrokenBackend([]),
        )


def test_evaluation_refuses_a_stale_corpus_before_calling_the_backend():
    stale = CompilationTaskSet(
        version="1.0.0",
        tasks=(
            CompilationTask(
                task_id="stale",
                prompt="Compile a stale field.",
                reference={"material.identifer": "ASTM-A36"},
            ),
        ),
    )
    backend = _Backend([_VALID_SPEC])
    with pytest.raises(ValueError, match="task set is stale"):
        evaluate_task_set(stale, backend)
    assert backend.reason_calls == []


def _recommendation_policy(**overrides) -> CompilationRecommendationPolicy:
    values = {
        "task_set_version": "1.0.0",
        "minimum_schema_validity": 0.5,
        "minimum_field_correctness": 0.6,
        "maximum_wrong_but_valid_rate": 0.25,
        "reference": "release policy approved for the 1.0.0 compilation corpus",
    }
    values.update(overrides)
    return CompilationRecommendationPolicy(**values)


def test_recommendation_gate_applies_all_three_metrics_without_a_composite_score():
    evaluation = evaluate_task_set(
        _evaluation_task_set(),
        _Backend([_VALID_SPEC, *([{"name": "invalid"}] * 3)]),
    )
    decision = assess_compilation_recommendation(evaluation, _recommendation_policy())

    assert isinstance(decision, CompilationRecommendation)
    assert decision.recommended is True
    assert decision.reasons == ()
    for forbidden in ("score", "success_rate", "passed", "overall"):
        assert not hasattr(decision, forbidden)


def test_high_validity_with_too_many_wrong_but_valid_outputs_is_not_recommended():
    evaluation = evaluate_task_set(
        _evaluation_task_set(),
        _Backend([_VALID_SPEC, _VALID_SPEC]),
    )
    decision = assess_compilation_recommendation(evaluation, _recommendation_policy())

    assert decision.schema_validity == pytest.approx(1.0)
    assert decision.wrong_but_valid_rate == pytest.approx(0.5)
    assert decision.recommended is False
    assert decision.reasons == ("wrong-but-valid rate 50.0% exceeds 25.0%",)


def test_recommendation_gate_names_every_failed_threshold_independently():
    evaluation = evaluate_task_set(
        _evaluation_task_set(),
        _Backend([_VALID_SPEC, *([{"name": "invalid"}] * 3)]),
    )
    decision = assess_compilation_recommendation(
        evaluation,
        _recommendation_policy(
            minimum_schema_validity=0.75,
            minimum_field_correctness=0.75,
            maximum_wrong_but_valid_rate=0.0,
        ),
    )

    assert decision.recommended is False
    assert decision.reasons == (
        "schema validity 50.0% is below 75.0%",
        "field correctness 66.7% is below 75.0%",
    )


def test_recommendation_markdown_carries_the_model_run_policy_and_three_metrics():
    evaluation = evaluate_task_set(
        _evaluation_task_set(),
        _Backend([_VALID_SPEC, _VALID_SPEC]),
    )
    rendered = assess_compilation_recommendation(
        evaluation, _recommendation_policy()
    ).render_markdown()

    for expected in (
        "small-local-model",
        "test-backend",
        "1.0.0",
        "two_pass",
        "schema 1.18.0",
        "Schema validity",
        "Field correctness",
        "Wrong-but-valid",
        "100.0%",
        "66.7%",
        "50.0%",
        "not recommended",
        "release policy approved",
    ):
        assert expected in rendered


def test_recommendation_gate_refuses_evidence_for_another_task_set_or_schema():
    evaluation = evaluate_task_set(
        _evaluation_task_set(),
        _Backend([_VALID_SPEC, *([{"name": "invalid"}] * 3)]),
    )
    with pytest.raises(ValueError, match="evidence is stale"):
        assess_compilation_recommendation(
            evaluation,
            _recommendation_policy(task_set_version="2.0.0"),
        )

    one_task = evaluate_task_set(
        CompilationTaskSet(version="1.0.0", tasks=(_evaluation_task_set().tasks[0],)),
        _Backend([_VALID_SPEC]),
    )
    first = one_task.attempts[0]
    assert first.result is not None
    stale_configuration = first.result.provenance.configuration.model_copy(
        update={"schema_version": "1.17.0"}
    )
    stale_result = first.result.model_copy(
        update={
            "provenance": first.result.provenance.model_copy(
                update={"configuration": stale_configuration}
            )
        }
    )
    stale = one_task.model_copy(
        update={"attempts": (first.model_copy(update={"result": stale_result}),)}
    )
    with pytest.raises(ValueError, match="uses stale Spec IR schema"):
        assess_compilation_recommendation(stale, _recommendation_policy())


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
