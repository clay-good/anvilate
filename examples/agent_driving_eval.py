"""Worked example: two models over the same tasks, and the one that looks better is worse.

Model A finishes both tasks — one in a single pass, one after two repairs. Model B finishes
one and abandons the other after a single call. Averaged over every run, B's iteration
count is 0.5 against A's 2.0: fewer iterations reads as a more efficient driver, and B
earned it by not trying. Only the completion rate — 50% against 100% — says what happened.

(B's error rate is worse, 20% against 0%, and that is the point rather than a
counter-example: the three numbers disagree, which is exactly why there is no fourth that
averages them.)

That is the whole reason the vocabulary refuses a summary number:

* **Mean iterations is over completed runs.** B's abandoned task contributes no iteration
  count, not a low one. A run that never completed has nothing to be efficient at.
* **A tool-call error is not a failing check.** A validation that returns FAIL is a
  successful call — the model drove the tool and the tool told it the truth. B's error is a
  call to an operation the catalog does not expose, which is a different finding from a
  malformed argument and is reported as one.
* **The task set is held against the live tool surface.** These two tasks deliberately do
  not cover it, and `task_set_issues` says so: an eval that covers half the surface reports
  a model can drive Anvilate on the strength of the half it was asked about.

Run it directly (``python examples/agent_driving_eval.py``); :func:`tasks`,
:func:`transcripts` and :func:`reports` are exercised in the test suite.
"""

from __future__ import annotations

from anvilate.agenteval import (
    AgentEvalReport,
    AgentTask,
    ToolCall,
    score_run_set,
    task_set_issues,
)

LOOP = ("build_part", "run_validation", "read_scorecard")

HARNESS = "3 retries, 32k context, tool-choice auto"


def tasks() -> list[AgentTask]:
    """Two tasks over the tool surface: compile once, then build → validate → read."""
    return [
        AgentTask(
            task_id="lug-50kn",
            prompt="Size a lifting lug for a 50 kN load and tell me whether it passes.",
            prelude=("compile_spec",),
            required_tools=LOOP,
        ),
        AgentTask(
            task_id="bracket-deflection",
            prompt="This bracket fails on deflection. Make it pass and show me the scorecard.",
            prelude=("compile_spec",),
            required_tools=LOOP,
        ),
    ]


def _ok(*names: str) -> list[ToolCall]:
    return [ToolCall(tool=name) for name in names]


def transcripts() -> dict[str, dict[str, list[ToolCall]]]:
    """What each model actually called, per task."""
    return {
        "model-a": {
            "lug-50kn": _ok("compile_spec", *LOOP),
            # Two repairs: build, check, read, three times over.
            "bracket-deflection": _ok("compile_spec", *LOOP, *LOOP, *LOOP),
        },
        "model-b": {
            "lug-50kn": _ok("compile_spec", *LOOP),
            # One call, to an operation the catalog does not expose, and then nothing.
            "bracket-deflection": [
                ToolCall(tool="fix_the_bracket", failed=True, error="no such tool")
            ],
        },
    }


def reports() -> dict[str, AgentEvalReport]:
    """One report per model, each carrying the harness it ran under."""
    task_set = tasks()
    return {
        name: score_run_set(task_set, runs, model_name=name, client="anvilate-cli", harness=HARNESS)
        for name, runs in transcripts().items()
    }


def main() -> None:
    for report in reports().values():
        print(report.render())
        print()

    a, b = reports()["model-a"], reports()["model-b"]
    print("read the completion rate first:")
    print(f"  model-a completed {a.completion_rate:.0%}, model-b {b.completion_rate:.0%}")
    naive_a = sum(o.iterations for o in a.outcomes) / len(a.outcomes)
    naive_b = sum(o.iterations for o in b.outcomes) / len(b.outcomes)
    print(
        f"  averaged over every run, model-b needs {naive_b:.1f} iterations against "
        f"model-a's {naive_a:.1f} — fewer, which reads as more efficient, and model-b "
        "earned it by not trying"
    )
    print(f"  over completed runs only: model-a {a.mean_iterations:.1f}, ", end="")
    print(f"model-b {b.mean_iterations:.1f}")

    unknown = [t for o in b.outcomes for t in o.unknown_tools]
    print(f"\nmodel-b invented a tool name: {unknown}")

    print("\nand the task set itself:")
    for issue in task_set_issues(tasks()):
        print(f"  {issue}")


if __name__ == "__main__":
    main()
