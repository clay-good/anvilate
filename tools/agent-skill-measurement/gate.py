"""Hold one measurement against the last: exit 1 if an agent stopped completing a task.

    python tools/agent-skill-measurement/gate.py BASELINE.json CANDIDATE.json

Both files are what `score.py` writes: a report for each condition a run was made under.
Each condition both files carry is compared with itself, per client. A task that completed
in the baseline and does not in the candidate fails the gate by name, as does a lower
completion count over the tasks both share (audit-agent-surface 3.5). A release names the
result file it was held against; with no baseline for a client there is nothing to hold it
to, and the gate says so and fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from anvilate.agenteval import AgentEvalReport, completion_regressions  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    before, after = (json.loads(Path(name).read_text(encoding="utf-8")) for name in argv)
    conditions = sorted(set(before) & set(after))
    problems = [
        f"the baseline was run {condition!r} and the candidate was not"
        for condition in sorted(set(before) - set(after))
    ]
    if not conditions:
        problems.append("the two files share no condition, so nothing was compared")
    for condition in conditions:
        problems += [
            f"{condition}: {issue}"
            for issue in completion_regressions(
                AgentEvalReport.model_validate(before[condition]["report"]),
                AgentEvalReport.model_validate(after[condition]["report"]),
            )
        ]
    for problem in problems:
        print(problem)
    if not problems:
        print(f"no regression across {', '.join(conditions)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
