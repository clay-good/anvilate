# Agent-skill measurement (agent-skill-surface task 4.1)

Runs the eight-task agent-driving corpus (`anvilate.agenteval.default_task_set`) through
your own Claude Code, once with only the MCP server's instructions and once with the
Anvilate skill appended, then scores both with `anvilate.agenteval`. Anvilate runs no
model; this uses your `claude` CLI and its login, and costs tokens on your account.

Run on 2026-10-09. The scored results are in `results/`, and the write-up is in
[docs/agent-driving-evals.md](../../docs/agent-driving-evals.md#measured-claude-code-with-and-without-the-skill-2026-10-09).
`results/2026-10-09-before-schema-fix.json` is the first run, which scored 0 of 8 because
the server's spec schema was unreadable to the model. A test holds the doc's table to
`results/2026-10-09.json`.

```bash
# needs: a logged-in `claude` CLI, and a venv with `pip install -e ".[dev,geometry]"`
python tools/agent-skill-measurement/harness.py . /tmp/anvilate-skill-runs
python tools/agent-skill-measurement/score.py . /tmp/anvilate-skill-runs
```

The harness reads `$TMPDIR/anvilate-geovenv/bin/python` for the MCP server; edit `PY` in
`harness.py` to point at your venv. Each run gets a fresh subject store and a working
directory with the padeye, base-plate and bracket specs. A call counts as failed only when
the protocol rejected it, per `agenteval.ToolCall`. Claude Code strips the `MCP error -326xx`
prefix from that text, so the scorer tells a rejection (bare text) from a tool's answer (a
JSON document, even one listing errors).
