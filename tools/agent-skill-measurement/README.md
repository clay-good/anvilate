# Agent-skill measurement (agent-skill-surface task 4.1)

Runs the eight-task agent-driving corpus (`anvilate.agenteval.default_task_set`) through
your own Claude Code, once with only the MCP server's instructions and once with the
Anvilate skill appended, then scores both with `anvilate.agenteval`. Anvilate runs no
model; this uses your `claude` CLI and its login, and costs tokens on your account.

Not run yet: the first attempt was paused on 2026-10-08 before any result was scored.

```bash
# needs: a logged-in `claude` CLI, and a venv with `pip install -e ".[dev,geometry]"`
python tools/agent-skill-measurement/harness.py . /tmp/anvilate-skill-runs
python tools/agent-skill-measurement/score.py . /tmp/anvilate-skill-runs
```

The harness reads `$TMPDIR/anvilate-geovenv/bin/python` for the MCP server; edit `PY` in
`harness.py` to point at your venv. Each run gets a fresh subject store and a working
directory with the padeye, base-plate and bracket specs. A call counts as failed only when
the protocol rejected it (`MCP error -326xx`), per `agenteval.ToolCall`.
