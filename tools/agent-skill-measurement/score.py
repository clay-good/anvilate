"""Score the harness's stream-json transcripts with anvilate.agenteval."""

import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
RUNS = Path(sys.argv[2])
sys.path.insert(0, str(REPO / "src"))
from anvilate.agenteval import ToolCall, default_task_set, score_run_set  # noqa: E402

PREFIX = "mcp__anvilate__"


def _is_document(text: str) -> bool:
    try:
        return isinstance(json.loads(text), dict)
    except ValueError:
        return False


def transcript(stream: Path):
    uses, results, model, version, final, cost, turns = {}, {}, None, None, None, None, None
    order = []
    for line in stream.read_text().splitlines():
        message = json.loads(line)
        if message.get("type") == "system" and message.get("subtype") == "init":
            model, version = message.get("model"), message.get("claude_code_version")
        if message.get("type") == "result":
            final = message.get("result")
            cost, turns = message.get("total_cost_usd"), message.get("num_turns")
        for block in (message.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block["name"].startswith(PREFIX):
                uses[block["id"]] = block["name"][len(PREFIX) :]
                order.append(block["id"])
            if block.get("type") == "tool_result":
                content = block.get("content")
                text = (
                    content
                    if isinstance(content, str)
                    else " ".join(
                        part.get("text", "") for part in content or [] if isinstance(part, dict)
                    )
                )
                results[block["tool_use_id"]] = (bool(block.get("is_error")), text)
    calls = []
    for use in order:
        is_error, text = results.get(use, (True, "no result"))
        # A tool that answered returns its JSON document, `errors` and all, even with
        # is_error set; a protocol rejection (-32602 and the like) is bare text, and Claude
        # Code 2.1.295 strips the "MCP error -326xx" prefix from it.
        protocol = is_error and ("MCP error -32" in text or not _is_document(text))
        error = text[:300] if protocol else None
        calls.append(ToolCall(tool=uses[use], failed=protocol, error=error))
    return calls, model, version, final, cost, turns


summary = {}
for condition in ("baseline", "skill"):
    transcripts, models, versions, extra = {}, set(), set(), {}
    for task in default_task_set():
        stream = RUNS / condition / task.task_id / "stream.jsonl"
        calls, model, version, final, cost, turns = transcript(stream)
        transcripts[task.task_id] = calls
        models.add(model)
        versions.add(version)
        extra[task.task_id] = {"cost_usd": cost, "turns": turns, "answer": (final or "")[:600]}
    report = score_run_set(
        default_task_set(),
        transcripts,
        model_name=",".join(sorted(m or "?" for m in models)),
        client=f"Claude Code {','.join(sorted(v or '?' for v in versions))} (claude -p)",
        harness=f"{condition}: stdio MCP, Read/Glob only",
    )
    summary[condition] = {
        # The three numbers are properties, which model_dump does not carry.
        "completion_rate": report.completion_rate,
        "mean_iterations": report.mean_iterations,
        "tool_call_error_rate": report.tool_call_error_rate,
        "report": json.loads(report.model_dump_json()),
        "extra": extra,
    }
    print(f"== {condition}\n{report.render()}")
(RUNS / "summary.json").write_text(json.dumps(summary, indent=2))
