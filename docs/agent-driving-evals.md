# Agent-driving evals

**"Which agent can drive this reliably?" is the question, and only an eval over
Anvilate's own tool surface answers it.** This page describes the measurement — the part
that has to be right before any number is published, because a scalar built the obvious way
rewards a model for giving up.

Three numbers, and deliberately no fourth that averages them
([`anvilate.agenteval`](../src/anvilate/agenteval.py)):

| Number | What it is | How it could lie |
| --- | --- | --- |
| Completion rate | Tasks where the run reached every required operation, in order | Nothing — this is the number a reader wants |
| Mean iterations | Passes through the build → validate → repair loop, **over completed runs only** | Averaged over every run, a model that gives up after one call posts the best score in the field |
| Tool-call error rate | Malformed calls and invented tool names, as a share of calls made | 0% beside a 0% completion rate reads as a flawless run, so no calls means `None` |

`AgentEvalReport` has no `score`, no `success_rate` and no `passed`, and a contract test
asserts none can be added. A model that abandons the hard tasks drives its iteration count
down and its error count with it; only the completion rate says so.

## The opening and the loop are separate, and that is what makes iterations mean anything

A task states a `prelude` — a one-off opening, such as compiling a document the run wrote
itself — and `required_tools`, the loop that repeats. Folded into one sequence, a run that
repaired twice counts a single pass, because the second pass goes looking for a second
`compile_spec` that no correct run makes. The library asserts exactly that: the same transcript scores 2 split and 1 folded.

## A tool-call error is not a failing check

A validation that comes back FAIL is a **successful call** — the model drove the tool and
the tool told it the truth. A malformed argument, or a call to an operation the surface
does not expose, is the model failing to drive it. Collapsing the two would score a model
well for never attempting the checks that fail. Invented tool names are reported separately
again, because a bad argument is a model that misread a schema and an invented name is a
model that did not read the catalog at all.

## The task set is held against the live tool surface

`task_set_issues()` reads [`anvilate.mcp.tool_catalog`](../src/anvilate/mcp.py) rather than
a copy of it, and refuses two things: a task naming an operation the catalog does not
expose, and a set that leaves any of the eight required operations untouched. An eval that
covers half the surface would otherwise report that a model can drive Anvilate on the
strength of the half it was asked about. Renaming an operation breaks the task set instead
of quietly narrowing the eval.

A run that skipped a task is an error, not an omission — otherwise the remaining tasks'
completion rate gets reported as the run's, and a model that refuses to start is exactly
the failure this eval exists to see. A model that made no call is recorded as an empty
transcript, which scores incomplete.

## The harness is part of the measurement

`model_name`, `client` and `harness` are all required. Completion and iteration counts move
with the system prompt, the retry policy and the context window as much as with the model,
so a number recorded without them cannot be compared with another one.

`default_versioned_task_set()` wraps the published corpus in `AgentTaskSet` version 1.2.0.
`evaluate_task_set()` retains that version and the complete ordered task-id list beside the
report; an `AgentEvaluation` refuses a report that silently drops or adds a task.

## The recommendation joins both evidence sets

`assess_local_model_recommendation()` accepts a compilation-gate decision, a versioned
agent evaluation, and an explicit `AgentRecommendationPolicy`. It refuses mismatched model
names and task-set versions, then applies completion, mean-iteration, and tool-call-error
thresholds independently. No threshold has a library default, and the result has no
composite score.

Nothing attempted remains not evaluated: a run with no completed task fails the completion
gate and has no mean iteration count; a run with no calls has no tool-call error rate. Neither
absence can satisfy a zero-error policy. `LocalModelRecommendation.render_markdown()` places
the compilation figures beside the agent-driving figures, including the exact client and
harness, and names every failed gate in release-note-ready Markdown.

## Scope

**The corpus is written now**, as `agenteval.default_task_set`: nine tasks over the eight
published operations. It waited for the server, because a task set is a claim about what an
agent should have done with the tools and writing it before they could be driven would have
been writing it against nothing — the same order
[the compilation metrics](valid-is-not-correct.md) shipped in.

The viewport and measurement tasks check the positive geometry path: build a base plate,
carry its subject handle into `render_viewport` and `measure_geometry`, and use the returned
image and measurements rather than describing or calculating values the model invented.

## Measured: Claude Code, with and without the skill (2026-10-09)

The corpus was run through Claude Code 2.1.295 (`claude -p`, model `claude-opus-5-5`), once
with only the server's own instructions and once with the [skill](agent-skill.md)
appended to the system prompt. Each run got a fresh session and subject store, the three
example specs, and only `Read`, `Glob` and the Anvilate tools. The harness, scorer and
every scored result set are in
[`tools/agent-skill-measurement/`](../tools/agent-skill-measurement/).

| Condition | Completion | Mean iterations | Tool-call errors | Calls | Cost |
| --- | --- | --- | --- | --- | --- |
| Baseline | 8 of 9 (89%) | 1.0 | 1 of 17 (6%) | 17 | $3.05 |
| With the skill | 8 of 9 (89%) | 1.0 | 1 of 15 (7%) | 15 | $3.45 |

**The skill does not change whether an agent can drive Anvilate. It changes how the
result is reported.** Both conditions finish the same eight tasks in nearly the same number
of calls. With the skill, 5 of 9 final answers say the result is a screen and not a
certified analysis, against 0 of 9 without it. That is a keyword count over the answers,
cruder than the scoring above. The skill costs about $0.40 more over the nine tasks, which
is the length of the prompt it adds. The error-rate difference is one refusal over two
denominators, not a difference.

The task neither condition completes is the FEA tier. `run_fea_validation` ran only as an
MCP task and Claude Code declares no tasks extension, so the server refused it in both
conditions. Both agents said so rather than inventing a result. Since that run, a client
without the extension gets the result in the reply instead (where, with no FEA solver in
this release, T3 is honestly not evaluated).

### How the number got here: three runs, four defects

The same day's earlier runs are kept beside this one, because each found something the
offline suite could not:

| Run | Result | What it found |
| --- | --- | --- |
| [1](../tools/agent-skill-measurement/results/2026-10-09-before-schema-fix.json) | 0 of 8, both conditions | The tools that take a spec declared it as a bare `$ref`, and the model sent `spec` as a JSON string in all 16 runs. Every input now states its type inline (gated in `tests/test_mcp.py`), and a string holding a JSON object is refused with that reason. The scorer also read 0% errors here: it looked for `MCP error -32…`, which Claude Code strips, so a refusal is now recognized as bare text where an answer is a JSON document. |
| [2](../tools/agent-skill-measurement/results/2026-10-09-before-instructions-fix.json) | 7 of 8 both; 30 calls against 18 | Claude Code keeps the first 2,048 characters of a server's instructions, and the element list sat after them, so the baseline agent guessed element names the skill had told the other one. The rules, element names and material ids now come first, held under that limit by a test. The call gap closed in run 3. |
| This one | 8 of 9 both | Corpus 1.0.0 asked about "the part you built" in a fresh session, and required a `compile_spec` that `run_validation` makes unnecessary, which scored correct runs incomplete. Corpus 1.2.0 requires `compile_spec` only where a document is checked without screening it. |

What this does not show: one run per task per condition, one model and one client. The
runs also inherited the operator's own Claude Code configuration, the same in both
conditions. A difference smaller than a whole task is not resolvable at this size.

## The other half: external suites, referenced rather than bundled

This page is the agent-driving eval. Its sibling is the structured-spec comparison —
scoring Anvilate against a public text-to-CAD benchmark so a claim about it is comparable
with the wider field. The licence question that gates *that* work is settled: MUSE's code
is MIT and its 106-case dataset is CC BY 4.0, verified from the repository, the project
site and the dataset card independently, so neither is excluded by the non-commercial rule
the benchmarking spec sets.

All 106 case descriptions were then fetched and parsed, which answers the scope question
with a census rather than an impression: 69 of them are assemblies of 2 to 36 components,
which a one-part Design Spec cannot express, and all 37 single-part cases are PLA, timber,
resin, sheet metal or ABS — none of those materials is in the bundled database. **0 of 106
compile today**, and what binds is the material path rather than the format. That is the
out-of-scope accounting this comparison owes, published as the count and the reason rather
than as a percentage of a set the pipeline cannot accept.

### `anvilate.specbench` — the reader, and the denominator

The module that does that census ships and until now appeared on no page. Its whole subject
is the denominator: **a benchmark score over a set the pipeline cannot accept is a number
about the benchmark**, so every case is read into a typed `CaseSpecification` and then
screened for scope before anything is compiled.

```python
from anvilate.specbench import parse_case_specification, scope_verdict, suite_accounting

case = parse_case_specification("demo-1", markdown)          # the suite's twelve headings
verdict = scope_verdict(case, known_materials=frozenset({"ASTM-A36"}))
```

```text
in_scope=True   reason=''
in_scope=False  reason="the material 'ASTM-A36' has no record in the database"
in_scope=False  reason='an assembly of 7 parts; a Design Spec states intent for one part'
```

Three things it refuses to do, each of which would have produced a better-looking number:

- **A refusal names itself.** `ScopeVerdict` cannot be built out-of-scope with an empty
  reason, so "0 of 106 compile" comes with 106 reasons rather than a count.
- **Part count binds before material.** A 44-part PLA bookshelf is not a materials problem,
  and reporting it as one would suggest that adding PLA to the database fixes it.
- **A document missing a heading is refused rather than parsed.** The suite's format carries
  all twelve in every case, so a document without them is a different document, and reading
  it leniently would silently score against something else.

`suite_accounting` is the census a published score has to sit beside: the total, the
in-scope count, and every reason with how many cases it took out. It is derived from the
verdicts, so the number moves when materials land rather than going stale in a document.

The data is still not vendored. Those cases are drawings, renders and rubric prose rather
than values, a benchmark with a leaderboard moves under its own version, and the
fetch-on-first-use flow this repository already uses for license-restricted tables records
the checksum, the version and the attribution CC BY 4.0 asks for. A run that has not
fetched reports `not_evaluated`, not a score. The full review, with what was checked and
how, is in
[`openspec/changes/extend-benchmarking-agent-evals/design.md`](../openspec/changes/extend-benchmarking-agent-evals/design.md).

See [`examples/agent_driving_eval.py`](../examples/agent_driving_eval.py).
