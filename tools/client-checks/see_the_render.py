"""Does the model in a real client see the image `render_viewport` returns?

Both target clients pass only `structuredContent` to the model when a tool result carries it
beside an image, so a render used to arrive as metadata and no picture. This check asks a
question only the picture answers: the colour the part is drawn in. The spec does not say
(the renderer draws light blue on white), and file-reading tools are off, so the tool result
is the only way to know.

    python tools/client-checks/see_the_render.py claude    # Claude Code, `claude -p`
    python tools/client-checks/see_the_render.py codex     # Codex, `codex exec`

Each run is one short paid session on the caller's own account. The transcript and verdict
are written to tools/client-checks/results/<client>-<date>.json. Exit 0 when the model
named the colour, 1 when it did not, 2 when the client is not installed.
"""

from __future__ import annotations

import datetime
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results"
PROMPT = (
    "Use the anvilate tools. Call build_part with exactly this spec, then call "
    "render_viewport on the returned subject with view iso. Then answer in one line, from "
    "the image alone: what colour is the part drawn in, and what colour is the background? "
    "If you received no image you can look at, answer exactly NO IMAGE.\n\nspec:\n"
)
SPEC = REPO / "examples" / "cover_plate.spec.yaml"


def _spec_json() -> str:
    import yaml

    return json.dumps(yaml.safe_load(SPEC.read_text(encoding="utf-8")))


def _claude(work: Path, out: Path) -> tuple[list[str], str]:
    config = {
        "mcpServers": {
            "anvilate": {
                "command": sys.executable,
                "args": ["-m", "anvilate.mcp", "--out", str(out)],
                "env": {
                    "PYTHONPATH": str(REPO / "src"),
                    "ANVILATE_SUBJECT_STORE": str(work / "store"),
                },
            }
        }
    }
    (work / "mcp.json").write_text(json.dumps(config))
    argv = [
        "claude", "-p", PROMPT + _spec_json(),
        "--mcp-config", str(work / "mcp.json"), "--strict-mcp-config",
        "--allowedTools", "mcp__anvilate",
        "--disallowedTools", "Bash", "Read", "Glob", "Grep", "Write", "Edit", "WebFetch",
        "WebSearch", "Task",
        "--output-format", "json", "--max-turns", "8", "--no-session-persistence",
    ]  # fmt: skip
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout
    return argv, version.strip()


def _codex(work: Path, out: Path) -> tuple[list[str], str]:
    override = (
        f'mcp_servers.anvilate={{command="{sys.executable}",'
        f'args=["-m","anvilate.mcp","--out","{out}"],'
        f'env={{PYTHONPATH="{REPO / "src"}",ANVILATE_SUBJECT_STORE="{work / "store"}"}}}}'
    )
    argv = ["codex", "exec", "--skip-git-repo-check", "-c", override, PROMPT + _spec_json()]
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout
    return argv, version.strip()


def main() -> int:
    client = sys.argv[1] if len(sys.argv) > 1 else ""
    if client not in ("claude", "codex"):
        print(__doc__)
        return 2
    if shutil.which(client) is None:
        print(f"{client} is not installed on this machine; the check was not run")
        return 2
    with tempfile.TemporaryDirectory(prefix="anvilate-client-check-") as scratch:
        work, out = Path(scratch), Path(scratch) / "out"
        argv, version = (_claude if client == "claude" else _codex)(work, out)
        done = subprocess.run(
            argv, cwd=work, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600
        )
        written = sorted(path.name for path in out.iterdir()) if out.exists() else []
    answer = done.stdout.strip()
    try:
        answer = json.loads(answer).get("result", answer)
    except ValueError:
        pass
    lowered = str(answer).lower()
    saw = "blue" in lowered and "no image" not in lowered
    record = {
        "client": client,
        "client_version": version,
        "date": datetime.date.today().isoformat(),
        "question": "what colour is the part drawn in (answerable only from the image)",
        "answer": str(answer)[-600:],
        "model_saw_the_image": saw,
        "files_written": written,
    }
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{client}-{record['date']}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if saw else 1


if __name__ == "__main__":
    raise SystemExit(main())
