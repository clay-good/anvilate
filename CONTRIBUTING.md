# Contributing

Start at **[adding a check](docs/contributing-analysis.md)**. It is the real guide: what a
new analysis function owes (a citation, a dimension check, a test that pins the number
against a hand calculation), and the manifests it has to be added to.

Two things worth knowing before the first pull request, because both are enforced and
neither is obvious:

- **A check ships with its derivation.** Every scorecard entry either carries the worked
  formula or states why it has none. There is no third option; the gate names the check.
  See [calculation reports](docs/calculation-reports.md).
- **A number in prose is held against the thing it counts.** The counts on this page, the
  ratios on the docs pages, and the claims in `SECURITY.md` are all read back by the suite.
  If you change a count, the test tells you the real one.

Run the whole gate before pushing — CI runs each of these and the format check is separate
from the lint:

```bash
ruff check src tests examples && ruff format --check src tests examples && pytest -q
```

Behavior changes land as [OpenSpec](openspec/) change proposals first: the requirement and
its scenarios, then the implementation, then the change is archived into
`openspec/specs/`. `npx openspec validate --all --strict` is part of the gate.

Security issues go through [SECURITY.md](SECURITY.md), not a pull request.
