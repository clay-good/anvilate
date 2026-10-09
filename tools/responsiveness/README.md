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
