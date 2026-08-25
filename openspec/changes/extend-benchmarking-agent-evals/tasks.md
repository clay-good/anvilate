# Tasks: External suites and agent-driving evals

## 1. Structured-spec benchmarks

- [ ] 1.1 License review of MUSE-class suites (bundle vs. reference-only per the
      dataset-licensing requirement)
- [ ] 1.2 Spec-format adapter (benchmark spec → Anvilate Spec IR where in-scope)
- [ ] 1.3 Funnel-stage scoring and out-of-scope accounting

## 2. Agent-driving suite

- [x] 2.1 Task set over the tool surface (compile → build → validate → repair) — the
      *format* and its gate; the corpus itself is not written, see below
- [x] 2.2 Per-combination metrics: completion, iterations, tool-call errors — three
      numbers, and no fourth that averages them
- [x] 2.3 Harness-configuration capture in published results — `model_name`, `client`
      and `harness` are required fields, not optional metadata

## 3. Publication

- [ ] 3.1 Release-notes integration and local-model recommendation update path

## Scope as shipped 2026-08-25 — tasks 2.1-2.3

`src/anvilate/agenteval.py`, `examples/agent_driving_eval.py`,
`docs/agent-driving-evals.md`. The measurement, before the server it measures — the same
order the compilation metrics shipped in, and for the same reason: a harness built around a
number that flatters the wrong model would look like it was finding good ones.

**The obvious scalar rewards giving up.** A model that abandons the hard tasks drives its
iteration count down and its error count with it; only the completion rate says so. So
there is no `score`, no `success_rate` and no `passed`, a contract test asserts none can be
added, and **mean iterations is over completed runs only** — averaged over every run, a
model that made one call and stopped posts the best efficiency in the field. The worked
example is exactly that pair of models.

**Two more places nothing-attempted read as nothing-wrong.** A run that never completed has
no iteration count rather than zero, and — found auditing the module an hour after writing
it — a run that made no call at all has no tool-call error *rate*: 0% printed beside a 0%
completion rate reads as a flawless run. Both return `None`.

**The opening and the loop are separate fields.** `prelude` is what happens once (compiling
the spec) and `required_tools` is what repeats. Folded into one sequence, a run that
repaired twice counts a single pass, because the second pass goes looking for a second
`compile_spec` no correct run makes. Asserted both ways on the same transcript: 2 split,
1 folded.

**A tool-call error is not a failing check.** A validation returning FAIL is a successful
call — the model drove the tool and the tool told it the truth. An invented tool name is
reported separately from a malformed argument, because one is a model that misread a schema
and the other is a model that did not read the catalog.

**The task set is bound to the live tool catalog.** `task_set_issues` refuses a task naming
an operation `anvilate.mcp.tool_catalog` does not expose, and refuses a set that leaves any
of the eight required operations untouched. Renaming an operation breaks the task set rather
than quietly narrowing what the eval covers.

**One infinite loop, behind a validator that does not always run.** An empty required
sequence is reached vacuously at every position, so the pass counter never terminated —
unreachable through the constructors, and one `model_copy` away otherwise. Guarded, and
pinned with a test that would hang without the guard.

The corpus is not written, and 1.x is untouched: a MUSE-class adapter needs the license
review in 1.1 first, and a task set is a claim about what an agent should have done with
tools of which four of eight are backed by shipping code.
