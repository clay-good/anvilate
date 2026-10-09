"""Run the agent-driving corpus through Claude Code, with and without the Anvilate skill."""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(REPO / "src"))
from anvilate.agenteval import default_task_set  # noqa: E402

PY = os.path.join(os.environ["TMPDIR"], "anvilate-geovenv/bin/python")
SKILL = (REPO / "src/anvilate/skills/anvilate/SKILL.md").read_text(encoding="utf-8")
FILES = {
    "padeye.spec.yaml": REPO / "examples/padeye.spec.yaml",
    "base_plate.spec.yaml": REPO / "examples/base_plate.spec.yaml",
    "bracket.spec.yaml": REPO / "examples/nema23_bracket.spec.yaml",
}


def run(task, condition):
    run_dir = OUT / condition / task.task_id
    if (run_dir / "stream.jsonl").exists():
        return
    work = run_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    for name, source in FILES.items():
        shutil.copy(source, work / name)
    config = {
        "mcpServers": {
            "anvilate": {
                "command": PY,
                "args": ["-m", "anvilate.mcp"],
                "env": {
                    "PYTHONPATH": str(REPO / "src"),
                    "ANVILATE_SUBJECT_STORE": str(run_dir / "store"),
                },
            }
        }
    }
    (run_dir / "mcp.json").write_text(json.dumps(config))
    argv = [
        "claude",
        "-p",
        task.prompt,
        "--mcp-config",
        str(run_dir / "mcp.json"),
        "--strict-mcp-config",
        "--allowedTools",
        "mcp__anvilate",
        "Read",
        "Glob",
        "--disallowedTools",
        "Bash",
        "Write",
        "Edit",
        "WebFetch",
        "WebSearch",
        "Task",
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "20",
        "--no-session-persistence",
    ]
    if condition == "skill":
        argv += ["--append-system-prompt", SKILL]
    with open(run_dir / "stream.jsonl", "w") as out, open(run_dir / "stderr.txt", "w") as err:
        subprocess.run(
            argv,
            cwd=work,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            timeout=900,
            check=False,
        )


jobs = [(task, condition) for condition in ("baseline", "skill") for task in default_task_set()]
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(lambda job: run(*job), jobs))
print("done", len(jobs))
