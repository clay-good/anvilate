# Agent-skill measurement (agent-skill-surface task 4.1)

Runs the eight-task agent-driving corpus (`anvilate.agenteval.default_task_set`) through
your own Claude Code, once with only the MCP server's instructions and once with the
Anvilate skill appended, then scores both with `anvilate.agenteval`. Anvilate runs no
model; this uses your `claude` CLI and its login, and costs tokens on your account.

Run three times on 2026-10-09. The scored results are in `results/`, and the write-up is in
[docs/agent-driving-evals.md](../../docs/agent-driving-evals.md#measured-claude-code-with-and-without-the-skill-2026-10-09).
`results/2026-10-09.json` is the published run, and a test holds the doc's table to it. The
two earlier files are the runs that found the server's unreadable spec schema and its
truncated instructions.

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

## Holding a release to the last run

```bash
python tools/agent-skill-measurement/gate.py results/2026-10-09.json /tmp/new-results.json
```

Exits 1 and names each task that completed in the first file and does not in the second,
for each condition both carry. Run it per client, against that client's own last result.
