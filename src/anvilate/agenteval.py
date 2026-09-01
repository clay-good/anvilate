"""Scoring an agent driving the tool surface: completion, iterations, and errors stay apart.

The question a user asks about a local model is not "is it good" but **"can it drive this
reliably"**, and that is only answerable over Anvilate's own tool surface. This module is
the half of that which can exist before the server does, and it is the half that decides
whether the answer means anything: the measurement.

Three numbers, and deliberately not a fourth that averages them:

**Completion rate** — the share of tasks where the run reached every operation the task
requires, in order. **Iterations** — how many complete passes through the loop it took.
**Tool-call error rate** — the share of calls that were malformed or named an operation
that does not exist, and ``None`` when no call was made, because 0% beside a 0% completion
rate reads as a flawless run.

**A task states its opening and its loop separately, and that is what makes the iteration
count mean anything.** Compiling a spec happens once; build → validate → read → repair is
what repeats. Folded into a single required sequence, a run that repaired twice would
count one pass, because the second pass would go looking for a second ``compile_spec`` no
correct run makes.

**Iterations are reported over completed runs only, and are ``None`` when nothing
completed.** Averaged over every run, a model that gives up after one call scores as the
most efficient driver in the field. A run that never completed has no iteration count, not
a low one — the same rule the scorecard follows for a check that could not run.

**A tool-call error is not a failing check.** A scorecard that comes back FAIL is the
correct answer to a bad design and says the model drove the tool properly. A malformed
argument, or a call to an operation the surface does not expose, is the model failing to
drive it. Collapsing the two would score a model well for never attempting the checks that
fail.

**The task set is held against the live tool surface.** :func:`task_set_issues` refuses a
task naming an operation :func:`anvilate.mcp.tool_catalog` does not carry, and refuses a
set that leaves any required operation unexercised — an eval that reports a model can drive
Anvilate while never touching half the surface is measuring something narrower than it
says. The gate reads the catalog rather than a copy of it, so renaming an operation breaks
the task set instead of silently narrowing the eval.

**Harness configuration is a required field.** Iteration counts move with the system
prompt, the retry policy and the context window as much as with the model, so a number
recorded without them cannot be compared with another one.

The corpus itself is not written here. A task set is a claim about what an agent should
have done with the tools, and eight operations are specified while four are backed; the
format and its gate are what a corpus needs to be judged against.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ConfigDict, model_validator

from ._models import RevalidatedModel
from .mcp import REQUIRED_OPERATIONS, tool_catalog

__all__ = [
    "AgentEvalReport",
    "AgentRunOutcome",
    "AgentTask",
    "ToolCall",
    "default_task_set",
    "score_run_set",
    "score_transcript",
    "task_set_issues",
]


class ToolCall(RevalidatedModel):
    """One call an agent made, and whether the call itself was well formed.

    ``failed`` is about the *call*, not about the answer. A ``run_validation`` that comes
    back with a failing scorecard is a successful call: the model drove the tool and the
    tool told it the truth. ``failed`` means the call was malformed, named an operation
    that does not exist, or was rejected before the operation ran.
    """

    model_config = ConfigDict(frozen=True)

    tool: str
    failed: bool = False
    error: str | None = None

    @model_validator(mode="after")
    def _failure_states_a_reason(self) -> ToolCall:
        if not self.tool.strip():
            raise ValueError("a tool call must name the tool it called")
        if self.failed and not (self.error or "").strip():
            raise ValueError(
                f"the call to {self.tool!r} is recorded as failed with no reason. The reason "
                "is what separates a malformed argument from an operation that does not "
                "exist, and those are different findings about the model"
            )
        if not self.failed and self.error is not None:
            raise ValueError(
                f"the call to {self.tool!r} carries an error and is not recorded as failed; "
                "one of the two is wrong, and which one decides whether the tool-call error "
                "rate is being measured or hidden"
            )
        return self

    def __str__(self) -> str:
        return f"{self.tool}" + (f" — FAILED: {self.error}" if self.failed else "")


class AgentTask(RevalidatedModel):
    """One prompt and the ordered operations a run that solved it must have reached.

    The two sequences are what make ``iterations`` mean something. ``prelude`` is the
    one-off opening a run must reach once — compiling the spec — and ``required_tools`` is
    the loop that gets counted: build, validate, read the scorecard, repair, build again.
    Folded into one sequence, a run that repaired twice would count a single pass, because
    the second pass would go looking for a second ``compile_spec`` that no correct run
    makes.

    Both are sequences and not sets because order carries the meaning: a run that reads a
    scorecard before it runs a validation read a stale one, and a run that exports before
    it validates emitted an unchecked artifact.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str
    prompt: str
    required_tools: tuple[str, ...]
    prelude: tuple[str, ...] = ()
    notes: str | None = None

    @property
    def operations(self) -> tuple[str, ...]:
        """Every operation the task names, prelude first."""
        return self.prelude + self.required_tools

    @model_validator(mode="after")
    def _has_something_to_reach(self) -> AgentTask:
        if not self.task_id.strip():
            raise ValueError("an agent task must have an id")
        if not self.prompt.strip():
            raise ValueError(f"task {self.task_id!r} has no prompt")
        if not self.required_tools:
            raise ValueError(
                f"task {self.task_id!r} requires no operation, so an empty transcript "
                "completes it — including one from a model that made no call at all"
            )
        blank = [name for name in self.operations if not name.strip()]
        if blank:
            raise ValueError(f"task {self.task_id!r} names an empty operation")
        return self


def _reach(required: Sequence[str], reached: Sequence[str], start: int = 0) -> int | None:
    """The index just past the first ordered match of ``required`` in ``reached``.

    ``None`` when the sequence is never reached in full.
    """
    index = start
    for name in required:
        while index < len(reached) and reached[index] != name:
            index += 1
        if index == len(reached):
            return None
        index += 1
    return index


def _passes(required: Sequence[str], reached: Sequence[str], start: int) -> int:
    """How many complete, non-overlapping ordered passes of ``required`` follow ``start``.

    Greedy: each pass consumes the calls it matched, so a run that built once and validated
    three times counts one pass through build → validate, not three. That is the number a
    reader wants — how many attempts the loop took — rather than how many times any single
    operation happened to be called.
    """
    # An empty requirement is reached vacuously at every position, so the loop below would
    # never terminate. The validators refuse an empty sequence, but `model_copy` does not
    # run them, and a hang is a worse way to find that out than a zero.
    if not required:
        return 0
    passes = 0
    index = start
    while (nxt := _reach(required, reached, index)) is not None:
        passes += 1
        index = nxt
    return passes


class AgentRunOutcome(RevalidatedModel):
    """One (task, run) result: the calls made, in the order they were made.

    Every metric below is derived from ``calls`` rather than declared, so a transcript
    cannot claim a completion its calls do not show.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str
    required_tools: tuple[str, ...]
    calls: tuple[ToolCall, ...]
    prelude: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _well_formed(self) -> AgentRunOutcome:
        if not self.task_id.strip():
            raise ValueError("an agent run outcome must name the task it came from")
        if not self.required_tools:
            raise ValueError(
                f"the run of task {self.task_id!r} carries no required operations, so it "
                "completes on an empty transcript"
            )
        return self

    @property
    def iterations(self) -> int:
        """Complete passes through the required loop, after the prelude, using calls that
        did not fail. Zero when the prelude was never reached."""
        reached = [c.tool for c in self.calls if not c.failed]
        start = _reach(self.prelude, reached) if self.prelude else 0
        return 0 if start is None else _passes(self.required_tools, reached, start)

    @property
    def completed(self) -> bool:
        """Whether the run reached the prelude and then the whole loop, in order, once."""
        return self.iterations >= 1

    @property
    def tool_call_errors(self) -> int:
        """Malformed or rejected calls. Not the same thing as a check that came back FAIL."""
        return sum(1 for call in self.calls if call.failed)

    @property
    def unknown_tools(self) -> tuple[str, ...]:
        """Calls naming an operation the surface does not expose, in first-seen order.

        Reported separately from the error count because it is a different finding: a bad
        argument is a model that misread a schema, and an invented tool name is a model
        that did not read the catalog at all.
        """
        known = {tool.name for tool in tool_catalog()}
        seen: list[str] = []
        for call in self.calls:
            if call.tool not in known and call.tool not in seen:
                seen.append(call.tool)
        return tuple(seen)

    def __str__(self) -> str:
        state = f"completed in {self.iterations} iteration(s)" if self.completed else "INCOMPLETE"
        return (
            f"{self.task_id}: {state}, {len(self.calls)} calls, "
            f"{self.tool_call_errors} tool-call error(s)"
        )


class AgentEvalReport(RevalidatedModel):
    """One model+client combination over a task set, with its harness written down.

    There is no ``score``, no ``success_rate`` and no ``passed``. A single figure over
    these three moves the wrong way: a model that abandons the hard tasks early drives its
    iteration count down and its error count with it, and only the completion rate says so.
    A contract test asserts no such scalar exists on the model.
    """

    model_config = ConfigDict(frozen=True)

    model_name: str
    client: str
    # The system prompt, retry policy, context window and tool-choice mode this ran under.
    # Required, because iteration counts move with all four as much as with the model.
    harness: str
    outcomes: tuple[AgentRunOutcome, ...]

    @model_validator(mode="after")
    def _measures_something(self) -> AgentEvalReport:
        if not self.outcomes:
            raise ValueError(
                "an eval report over no tasks has no numbers in it; an empty run is "
                "reported as not run, not as a clean sheet"
            )
        for field, value in (
            ("model_name", self.model_name),
            ("client", self.client),
            ("harness", self.harness),
        ):
            if not value.strip():
                raise ValueError(
                    f"an eval report must state its {field}. Completion and iteration counts "
                    "move with the harness — the system prompt, the retry policy, the "
                    "context window — as much as with the model, so a number recorded "
                    "without them cannot be compared with another one"
                )
        seen = [outcome.task_id for outcome in self.outcomes]
        if len(set(seen)) != len(seen):
            raise ValueError(f"the report scores a task twice: {sorted(seen)}")
        return self

    @property
    def completion_rate(self) -> float:
        """The share of tasks the run reached the end of."""
        return sum(1 for o in self.outcomes if o.completed) / len(self.outcomes)

    @property
    def mean_iterations(self) -> float | None:
        """Mean iterations **over completed runs**, or ``None`` when none completed.

        Not averaged over every run. A model that gives up after one call would otherwise
        post the best iteration count in the field, and a reader comparing two models on
        this number alone would pick the one that solved fewer tasks.
        """
        completed = [o.iterations for o in self.outcomes if o.completed]
        return sum(completed) / len(completed) if completed else None

    @property
    def tool_call_error_rate(self) -> float | None:
        """Failed calls as a share of all calls made, or ``None`` when none were made.

        Not zero. A model that never called anything has no error rate, and 0% printed
        beside a 0% completion rate reads as a flawless run — the same way an averaged
        iteration count would. Nothing attempted is not nothing wrong.
        """
        total = sum(len(o.calls) for o in self.outcomes)
        if not total:
            return None
        return sum(o.tool_call_errors for o in self.outcomes) / total

    def incomplete(self) -> tuple[AgentRunOutcome, ...]:
        """The tasks the run did not finish — named, not just counted."""
        return tuple(o for o in self.outcomes if not o.completed)

    def summary(self) -> str:
        """All three numbers in one line, with none of them averaged into the others."""
        iterations = (
            f"{self.mean_iterations:.1f}" if self.mean_iterations is not None else "not evaluated"
        )
        errors = (
            f"{self.tool_call_error_rate:.0%}"
            if self.tool_call_error_rate is not None
            else "not evaluated"
        )
        return (
            f"{self.model_name} via {self.client} under {self.harness}: "
            f"completion {self.completion_rate:.0%}, "
            f"mean iterations (completed runs) {iterations}, "
            f"tool-call errors {errors}"
        )

    def render(self) -> str:
        """The summary, then every task under it, unfinished ones first."""
        ranked = sorted(self.outcomes, key=lambda o: (o.completed, o.iterations))
        return "\n".join([self.summary(), *(f"  {outcome}" for outcome in ranked)])


def score_transcript(task: AgentTask, calls: Sequence[ToolCall]) -> AgentRunOutcome:
    """One run's transcript against the task it was attempting."""
    return AgentRunOutcome(
        task_id=task.task_id,
        required_tools=task.required_tools,
        prelude=task.prelude,
        calls=tuple(calls),
    )


def score_run_set(
    tasks: Sequence[AgentTask],
    transcripts: dict[str, Sequence[ToolCall]],
    *,
    model_name: str,
    client: str,
    harness: str,
) -> AgentEvalReport:
    """Score a whole task set, refusing to silently drop a task nobody attempted.

    A task with no transcript is an error rather than an omission. A run that skipped the
    hard tasks would otherwise report the remaining tasks' completion rate as the run's —
    and a model that refuses to start is exactly the failure this eval exists to see. A
    model that made no call at all is recorded as an empty transcript, which scores
    incomplete.
    """
    missing = [task.task_id for task in tasks if task.task_id not in transcripts]
    if missing:
        raise ValueError(
            f"{len(missing)} task(s) have no transcript: {missing}. A skipped task is not a "
            "task that scored zero, and dropping it silently reports the remaining tasks' "
            "completion rate as the run's"
        )
    return AgentEvalReport(
        model_name=model_name,
        client=client,
        harness=harness,
        outcomes=tuple(score_transcript(task, transcripts[task.task_id]) for task in tasks),
    )


def task_set_issues(tasks: Sequence[AgentTask]) -> list[str]:
    """Everything wrong with a task set, held against the live tool surface.

    Reads :func:`anvilate.mcp.tool_catalog` rather than a copy of it, so renaming an
    operation breaks the task set here instead of quietly narrowing what the eval covers.
    An empty list means the set names only operations that exist and exercises every
    operation the headless-automation spec requires — an eval that leaves half the surface
    untouched reports a model can drive Anvilate when it has only been asked to drive part
    of it.
    """
    issues: list[str] = []
    if not tasks:
        return ["the task set is empty, so every model scores the same on it"]

    known = {tool.name for tool in tool_catalog()}
    seen_ids: set[str] = set()
    exercised: set[str] = set()
    for task in tasks:
        if task.task_id in seen_ids:
            issues.append(f"task id {task.task_id!r} appears twice")
        seen_ids.add(task.task_id)
        for name in task.operations:
            exercised.add(name)
            if name not in known:
                issues.append(
                    f"task {task.task_id!r} requires {name!r}, which the tool catalog does "
                    f"not expose; the eval would score every model as failing it"
                )

    unexercised = sorted(REQUIRED_OPERATIONS - exercised)
    if unexercised:
        issues.append(
            f"no task exercises {unexercised}; the eval would report that a model can drive "
            "Anvilate on the strength of a surface it never touched"
        )
    return issues


# The corpus itself: what a run is asked to do, and the operations a correct one reaches.
#
# `add-agent-skill-surface` 4.1 asks for the agent-driving funnel measured with and without
# the skill loaded. The scoring half of that is this module; the server half exists; this is
# the third piece, and it is the one that says what "driving Anvilate" means.
#
# **The tasks are written against the surface as it is, refusals included.** Three operations
# are published and not dispatched — two wait on built geometry, one on a decision about
# writing files — and a task set that avoided them would report a model can drive Anvilate on
# the strength of a surface it never touched, which is the thing `task_set_issues` refuses.
# Reaching an operation is not the same as being answered by it: a run that calls
# `render_viewport`, receives the refusal naming geometry, and reports that rather than
# inventing a picture has driven the tool correctly. That is the behaviour this library most
# needs a model to have, and it is only measurable if the corpus asks for it.
#
# What is still missing after this is the measurement, and it is missing for a reason no code
# here can fix: running the funnel needs an agent, and this package initiates no sampling and
# ships no model. The corpus and the scoring are what a harness outside it consumes.
_TASK_SET: tuple[AgentTask, ...] = (
    AgentTask(
        task_id="screen-a-described-part",
        prompt=(
            "A 120 mm wide, 20 mm thick ASTM-A36 padeye with a 40 mm pin hole carries a "
            "60 kN sling leg. Required safety factor 2.0. Screen it and tell me the verdict "
            "with the clause behind each check."
        ),
        prelude=("compile_spec",),
        required_tools=("run_validation",),
        notes=(
            "The shortest complete loop, and the one every other task is built on. The "
            "answer must come from the card rather than from the model's own arithmetic."
        ),
    ),
    AgentTask(
        task_id="read-the-card-back-by-handle",
        prompt=(
            "Screen that padeye, then show me the scorecard again without re-running the checks."
        ),
        prelude=("compile_spec",),
        required_tools=("run_validation", "read_scorecard"),
        notes=(
            "The subject handle is the only way to do this. A run that re-screens instead "
            "reached the same verdict by the wrong route, and one that quotes its own memory "
            "of the earlier reply never touched the store at all."
        ),
    ),
    AgentTask(
        task_id="repair-a-failing-check",
        prompt=(
            "Take that padeye down to 6 mm thick, screen it, and fix whatever fails — using "
            "the repair the scorecard gives you rather than a size you pick."
        ),
        prelude=("compile_spec",),
        required_tools=("run_validation", "compile_spec", "run_validation"),
        notes=(
            "Two passes through the loop, which is what makes the iteration count mean "
            "something. The second compile is the repair; the entry carries the thickness "
            "that lands exactly on the required margin, so a run that guesses a size has "
            "ignored the answer it was given."
        ),
    ),
    AgentTask(
        task_id="refuse-to-paper-over-a-gap",
        prompt=(
            "Screen this bracket spec, which declares no element type, and tell me whether "
            "it passed."
        ),
        prelude=("compile_spec",),
        required_tools=("run_validation",),
        notes=(
            "The card is NOT_EVALUATED with the reason. The failure mode being measured is a "
            "run that reports 'no failures' — true, and read by a person as a pass."
        ),
    ),
    AgentTask(
        task_id="report-an-unbuilt-operation",
        prompt="Show me a rendered view of the part you just screened.",
        prelude=("compile_spec",),
        required_tools=("run_validation", "render_viewport"),
        notes=(
            "The tool is published, takes a subject, and is refused with what it waits on. A "
            "correct run reaches it, reads the refusal and says geometry is not generated — "
            "rather than describing a picture it never received."
        ),
    ),
    AgentTask(
        task_id="measure-rather-than-assume",
        prompt=(
            "What is the actual bore diameter on the part you built, as opposed to what the "
            "spec asked for?"
        ),
        prelude=("compile_spec",),
        required_tools=("build_part", "measure_geometry"),
        notes=(
            "Both are refused today — one task-dispatched, one waiting on geometry — and the "
            "distinction is the point: a run must not answer a question about built geometry "
            "out of the spec that asked for it."
        ),
    ),
    AgentTask(
        task_id="export-only-what-passed",
        prompt="Screen the padeye and export the evidence bundle for it.",
        prelude=("compile_spec",),
        required_tools=("run_validation", "export_artifact"),
        notes=(
            "The order is the whole task: the export takes the scorecard handle, so a run "
            "that reaches for it before validating has nothing to name and is refused. It is "
            "also the one task whose tool answers with a document rather than a file — a run "
            "that reports a path it was never given has invented one."
        ),
    ),
    AgentTask(
        task_id="use-the-convergent-tier-through-its-handle",
        prompt="Run the FEA-class checks on that padeye and tell me when they finish.",
        prelude=("compile_spec",),
        required_tools=("run_fea_validation",),
        notes=(
            "Task-dispatched, because the run stops on a convergence tolerance rather than a "
            "clock. A run that blocks on a synchronous reply has misread the contract it was "
            "handed; the refusal says so and names the Tasks extension."
        ),
    ),
)


def default_task_set() -> tuple[AgentTask, ...]:
    """The agent-driving corpus, in a fixed order.

    Eight tasks over the eight published operations, so a completion rate is a claim about
    the whole surface rather than about the half that happens to be dispatched. Held against
    the live catalog by :func:`task_set_issues`, which is what stops a renamed operation
    quietly narrowing what the eval covers.
    """
    return _TASK_SET
