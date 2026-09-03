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

First, install the development extra — the gate below needs `pytest` and `ruff`, and the
README's `pip install -e ".[export]"` does not carry them:

```bash
pip install -e ".[dev]"
```

Then run the whole gate before pushing. The format check is separate from the lint, and CI
runs the first three:

```bash
ruff check src tests examples && ruff format --check src tests examples && pytest -q
npx openspec validate --all --strict
```

The OpenSpec validation is a local check rather than a CI one, so it is the step that
depends on you running it. Behavior changes land as [OpenSpec](openspec/) change proposals
first: the requirement and its scenarios, then the implementation, then the change is
archived into `openspec/specs/`.

Security issues go through [SECURITY.md](SECURITY.md), not a pull request.
