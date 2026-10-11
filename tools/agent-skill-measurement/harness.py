"""Run the agent-driving corpus through a client, with and without the Anvilate skill.

    python tools/agent-skill-measurement/harness.py REPO OUT            # Claude Code
    python tools/agent-skill-measurement/harness.py REPO OUT codex      # OpenAI Codex

Each run gets a fresh subject store and a working directory holding three example specs.
The client's own output goes to ``OUT/<condition>/<task>/stream.jsonl``. `score.py` reads
what Claude Code writes there; what Codex writes has not been read from a real run yet, so
a Codex run is recorded and not scored (audit-agent-surface 3.1 and 3.3).
"""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CLIENTS = ("claude", "codex")
SPECS = {
    "padeye.spec.yaml": "examples/padeye.spec.yaml",
    "base_plate.spec.yaml": "examples/base_plate.spec.yaml",
    "bracket.spec.yaml": "examples/nema23_bracket.spec.yaml",
}


def server_python() -> str:
    """The interpreter the MCP server runs under: one with the geometry extra installed."""
    return os.path.join(os.environ["TMPDIR"], "anvilate-geovenv/bin/python")


def server(repo: Path, run_dir: Path, python: str) -> dict:
    """How either client starts the server for one run: its own store, this checkout's code."""
    return {
        "command": python,
        "args": ["-m", "anvilate.mcp"],
        "env": {
            "PYTHONPATH": str(repo / "src"),
            "ANVILATE_SUBJECT_STORE": str(run_dir / "store"),
        },
    }


def claude_argv(prompt: str, config: Path, skill: str | None) -> list[str]:
    argv = [
        "claude", "-p", prompt,
        "--mcp-config", str(config), "--strict-mcp-config",
        "--allowedTools", "mcp__anvilate", "Read", "Glob",
        "--disallowedTools", "Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task",
        "--output-format", "stream-json", "--verbose",
        "--max-turns", "20", "--no-session-persistence",
    ]  # fmt: skip
    if skill is not None:
        argv += ["--append-system-prompt", skill]
    return argv


def codex_override(launch: dict) -> str:
    """The server as one ``-c`` override: a TOML key and an inline table for its value.

    The same registration `codex mcp add anvilate -- anvilate-mcp` writes to Codex's
    configuration, given for one run so a measurement never edits the user's own.
    """
    env = ",".join(f"{name}={json.dumps(value)}" for name, value in launch["env"].items())
    return (
        f"mcp_servers.anvilate={{command={json.dumps(launch['command'])},"
        f"args={json.dumps(launch['args'])},env={{{env}}}}}"
    )


def codex_argv(prompt: str, launch: dict, skill: str | None) -> list[str]:
    # Codex has no flag that appends to the system prompt, so the skill leads the prompt.
    asked = prompt if skill is None else f"{skill}\n\n{prompt}"
    return ["codex", "exec", "--skip-git-repo-check", "-c", codex_override(launch), asked]


def run(repo: Path, out: Path, client: str, task, condition: str, skill: str) -> None:
    run_dir = out / condition / task.task_id
    if (run_dir / "stream.jsonl").exists():
        return
    work = run_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    for name, source in SPECS.items():
        shutil.copy(repo / source, work / name)
    launch = server(repo, run_dir, server_python())
    appended = skill if condition == "skill" else None
    if client == "claude":
        (run_dir / "mcp.json").write_text(json.dumps({"mcpServers": {"anvilate": launch}}))
        argv = claude_argv(task.prompt, run_dir / "mcp.json", appended)
    else:
        argv = codex_argv(task.prompt, launch, appended)
    with open(run_dir / "stream.jsonl", "w") as stream, open(run_dir / "stderr.txt", "w") as err:
        subprocess.run(  # noqa: S603 - the user's own client, a fixed argv
            argv, cwd=work, stdin=subprocess.DEVNULL, stdout=stream, stderr=err,
            timeout=900, check=False,
        )  # fmt: skip


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] not in CLIENTS):
        print(__doc__)
        return 2
    repo, out = Path(argv[0]), Path(argv[1])
    client = argv[2] if len(argv) == 3 else "claude"
    if shutil.which(client) is None:
        print(f"{client} is not installed on this machine; nothing was run")
        return 2
    sys.path.insert(0, str(repo / "src"))
    from anvilate.agenteval import default_task_set

    skill = (repo / "src/anvilate/skills/anvilate/SKILL.md").read_text(encoding="utf-8")
    jobs = [(task, condition) for condition in ("baseline", "skill") for task in default_task_set()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda job: run(repo, out, client, job[0], job[1], skill), jobs))
    print("done", len(jobs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
