# Responsiveness budget

How long Anvilate keeps you waiting, declared and measured. `budget.json` is the declaration:
a time per interactive operation (the CLI commands, and the first call of each MCP tool on a
fresh server), and onboarding's ten minutes from a fresh install to a first validated part.

| What | Where it runs | What happens on a breach |
|---|---|---|
| `measure.py` | every release, in `publish-mcp-registry.yml` | a sustained breach stops the registry publication; both records are attached to the release |
| `measure.py` | weekly and on dispatch, in `ci.yml` | the scheduled run fails, as an early warning |

**The reference profile** is a GitHub-hosted `ubuntu-latest` standard runner with Python 3.11.
Every release is measured on that one machine class, so two releases' numbers compare.

**Sustained** means the same operation breaches its budget on two full passes. A shared
runner has slow moments; one pass over budget triggers a second, and only what breaches both
times blocks. Each operation is timed several times and judged by its median, after checking
that it succeeded: a refusal returns fast and would pass any budget.

```bash
python tools/responsiveness/measure.py --out responsiveness.json
python tools/responsiveness/measure.py --first-part --out first-part.json
```

Raising a budget is a deliberate edit to `budget.json`, visible in the diff with its reason.

## First measurement on the reference profile

2026-10-09, `ffef42f7`, GitHub-hosted ubuntu24 runner, 4 vCPU, Python 3.11.17; medians of five:

| Operation | Median | Budget |
|---|---|---|
| `anvilate check` | 0.70 s | 2 s |
| `anvilate build` | 3.14 s | 15 s |
| `anvilate view` | 3.02 s | 15 s |
| MCP `initialize` (server start to reply) | 0.57 s | 2 s |
| MCP `tools/list` | 0.17 s | 1 s |
| MCP `build_part` (first call, kernel import) | 1.73 s | 10 s |
| MCP `export_artifact` | 0.09 s | 2 s |
| Every other MCP tool | under 0.01 s | 1–2 s |
| Fresh install to a first validated STEP | 25 s | 600 s |
