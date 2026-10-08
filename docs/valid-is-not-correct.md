# A valid spec can still be the wrong spec

**Constraining a small model's output to a schema takes validity from ~62% to 100% and takes
accuracy *down* from ~20% to 11%.** The wrong-but-schema-valid share goes from about half to
nearly nine in ten. That is the measured result in "The Constraint Tax"
([arXiv:2605.26128](https://arxiv.org/abs/2605.26128), May 2026), on the 0.5B–1.7B models
Anvilate's local-first promise depends on.

A confidently well-formed spec with the wrong load in it is worse than a malformed one.
Schema validation cannot catch it; every consumer downstream treats it as an input somebody
meant.

## What is built, and what is not

[`anvilate.compilation`](../src/anvilate/compilation.py) now contains the backend-independent
compiler boundary and the measurement vocabulary. The caller injects a backend; Anvilate
makes no model or network choice. A two-pass backend first reasons without a schema, then
receives the exact Design Spec JSON Schema for constrained packaging. A backend that cannot
separate the passes uses a single constrained pass, and that fallback is recorded rather
than presented as equivalent.

Every packaged candidate goes through the ordinary `parse_spec` front door. A malformed
candidate is returned to the backend as validation context up to the bounded retry budget;
exhaustion raises `CompilationFailure` and no candidate reaches another subsystem. A
successful `CompilationResult` keeps the typed `DesignSpec` in `result.spec` and the
reasoning/configuration in `result.provenance`. Screening, geometry, and export accept the
former, not the reasoning-bearing wrapper.

Compiler refusals are actionable without parsing their messages. A malformed constrained
response raises `CompilationCandidateError` with a `Remedy` naming that backend response and
the Design Spec JSON Schema it must follow. Retry exhaustion raises `CompilationFailure` with
the backend and model as its concrete subject and points to both the schema and
`provenance.validation_errors`. Both remain `ValueError` subclasses for existing callers;
their messages are unchanged.

Anvilate ships no model and calls none. The language model is your own agent (Claude Code,
Claude Desktop, Cursor or any MCP client), driving Anvilate's local MCP server: the agent
writes the spec, `compile_spec` validates it and names every refusal, and `run_validation`
screens it. The server's `initialize` result carries `instructions` for the agent, generated
from the live databases: the exact material, component and element identifiers, and the rules
a real model got wrong when it had only the schema (a stated minimum safety factor written
into `max_safety_factor`, "ASTM A36" for `ASTM-A36`, a load dropped, no element named).

The scoring below grades any candidate spec against a reference, whoever wrote it, so an
agent's output is measured the same way a compiler's was.

The measurement came first on purpose: a compiler shipped against a metric that hides the
wrong-but-valid failure would look like it was improving as it got worse.

```python
from anvilate.compilation import CompilationTask, score_task_set

report = score_task_set(tasks, candidates, configuration="single-pass, hard constrained")
print(report.summary())
```

```
4 tasks under single-pass, hard constrained: schema validity 100%, field correctness 75%,
wrong-but-valid 75%
```

## Three numbers, and no fourth

`CompilationReport` has **no `score`, no `success_rate`, no `passed`.** A contract test
asserts none of them can be added.

That is not fastidiousness. A single figure over a constrained decoder is dominated by
schema validity — the number constraint drives to 100% — while field correctness falls and
the wrong-but-valid rate rises. Average them and the compiler appears to improve as the thing
a user cares about gets worse. The three numbers move in different directions, which is
exactly why they cannot be one number.

| Number | What it measures | Which way constraint moves it |
| --- | --- | --- |
| `schema_validity` | the fraction of outputs the schema accepted | up, to 100% |
| `field_correctness` | the fraction of referenced fields found and agreeing | down |
| `wrong_but_valid_rate` | the fraction the schema accepted that are wrong anyway | up |

`wrong_but_valid()` names those candidates rather than only counting them, because a rate is
not something anybody can act on.

**And `render()` prints the caveat under the numbers**, which nothing did. `citation` is the
argument for the shape of the three figures — the published source for the constraint tax, and
the words "screening measurement, not a certified benchmark" — and it had carried both since
the model was written while no rendering showed either. The one reading a person actually saw
was three percentages with nothing saying what they are not. It is on `render` rather than
`summary`, because the summary is a report pane's single headline and a two-sentence citation
in it pushes the numbers off the end.

## What does not count as correct

**A field the candidate omits.** It counts against correctness and says "the candidate does
not carry this field". Skipping absent fields is how a compiler that omits half the spec
scores well.

**A field nobody could compare.** An output that did not parse has all its fields recorded as
not compared, and they stay in the denominator: a compiler that produces nothing must not
outscore one that produces something wrong.

**A task nobody attempted.** `score_task_set` refuses a task with neither a candidate nor a
parse error. A run that skipped the hard tasks would otherwise publish the easy ones' numbers
as the run's.

**A unit read wrong.** Comparison is dimensional: `50 kN` and `50000 N` are the same answer,
`50 kN` and `50 kip` are not, and `50 kN` against `50 mm` is reported as a wrong answer
rather than an incomparable one — reading a force as a length is precisely the failure a
dimensional comparison exists to catch.

## The configuration is part of the number

A report must state how it was decoded, and refuses to be built without it. Validity and
accuracy both move with the pass structure, so a number without its configuration cannot be
compared against another one — and comparing "reason free, then constrain late" against
"constrain from the first token" is the whole reason to measure.

## This is screening, not a benchmark

Every report carries that caveat in its citation. The numbers are only as good as the
reference fields the task set declares, and a task set is a claim about what the compiler
should have understood.

## A task set survives being written down

`CompilationTask.reference` maps a dotted path to the value expected there, and that value
is typed `Any` — a spec field can be a string, a number or a quantity. `Any` is the one
annotation pydantic cannot rebuild from, so a task stating `force` as `5 kN` serialized to
`{"magnitude": 5.0, "unit": "kN"}` and read back as exactly that dictionary. The reloaded
task no longer compared equal to the one it was written from, and a report scored against it
printed its own expected value as `{'magnitude': 5.0, 'unit': 'kN'}` where the original
printed `5 kN`. The verdict was the same either way, which is what kept it quiet.

Only the two-key shape Anvilate's own serializer emits is rebuilt. A `{"magnitude", "unit"}`
pair that does not parse stays a dictionary, and a string is never coerced: a task stating
`"5 kN"` as a string is asking for a string, and answering it with a quantity would score a
different question than the task asked.

`default_compilation_task_set()` is the first versioned corpus: six prompts spanning a
lifting lug, a stepper bracket, a bolted connection, a timber beam, a hydraulic run, and an
ISO-fit shaft dimension. Each reference contains only fields its prompt actually states,
not a full “golden” spec filled with defaults the compiler was never asked to choose.

`task_set_issues()` resolves every reference path through the published Design Spec schema
and, for `element_params`, the published schema selected by that task's `element_type`.
Renaming `manufacturing.process` or a pack field such as `pipe_run.flow_rate` therefore
breaks CI at the task that still names it. This is a schema-drift gate, not a model result:
the separate release gate remains open until the corpus is run through real configured
models and its correctness effect is recorded.

`evaluate_task_set(task_set, backend)` is the runner an external harness uses for that model
work. It compiles every prompt, retains each validated spec or bounded failure with its
provenance, and derives the three-number `CompilationReport` without dropping failed tasks.
The report's configuration names the task-set version, backend, model, pass shape, Spec IR
version, and retry budget. A backend transport or implementation defect aborts the run; it
is not converted into a schema-invalid answer, because a partial run is not a low-scoring
complete run. The runner remains offline until the caller injects a backend that chooses to
communicate with a model.

## A recommendation needs an explicit release policy

`assess_compilation_recommendation(evaluation, policy)` is the publication gate. Its
`CompilationRecommendationPolicy` requires the release owner to state all three thresholds,
the task-set version they govern, and the source of that decision. Anvilate provides no
house thresholds: choosing how much model error is acceptable is a release decision, not a
number the measurement code can infer.

The gate refuses evidence from another task-set version, a stale Spec IR schema, or a run
that mixes decoding configurations. It applies each threshold independently. In particular,
100% schema validity cannot rescue a candidate whose wrong-but-valid rate exceeds policy.
The resulting `CompilationRecommendation` has no aggregate score; `reasons` names every
failed gate.

`render_markdown()` produces the release-note table row. It includes the model, backend,
task-set version, pass shape, schema version, retry budget, all three measured figures, the
decision, and the policy source. Producing that evidence does not publish a recommendation
or run a model by itself.
