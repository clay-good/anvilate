# Agent-driving evals

**"Which local model can drive this reliably?" is the question, and only an eval over
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

A task states a `prelude` — the one-off opening, compiling the spec — and `required_tools`,
the loop that repeats. Folded into one sequence, a run that repaired twice counts a single
pass, because the second pass goes looking for a second `compile_spec` that no correct run
makes. The library asserts exactly that: the same transcript scores 2 split and 1 folded.

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

## Scope

**The corpus is not written.** A task set is a claim about what an agent should have done
with the tools, and of the eight specified operations four are backed by shipping code. The
format and its gate are what a corpus needs to be judged against; writing the corpus first
would be writing it against nothing — the same order
[the compilation metrics](valid-is-not-correct.md) shipped in, and for the same reason.

Nothing here runs a model. It scores a transcript, which is what makes it testable offline
and what keeps the published recommendation gated on a measurement rather than an
impression.

See [`examples/agent_driving_eval.py`](../examples/agent_driving_eval.py).
