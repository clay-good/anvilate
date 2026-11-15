# Parts as code in CI

**A failing check lands on the line that caused it.** Not in a log a reviewer has to open
— on the spec's own line, in the diff, where every linter they already use puts findings.

```bash
anvilate check parts/ \
  --sarif anvilate.sarif --sarif-category parts \
  --junit anvilate.xml \
  --baseline parts/baseline.json --summary "$GITHUB_STEP_SUMMARY"
```

One run, one verdict. The reports are written by the same invocation whose exit code is
the gate, because screening a repository twice can report one answer and gate on another.

## The three things a repository of parts was missing

| | Before | Now |
| --- | --- | --- |
| A finding has a place | A red job and a log | SARIF 2.1.0, each result on the line of the spec field the check is about |
| A dashboard can count it | JSON in Anvilate's own shape | JUnit XML, one case per check per spec |
| "Fails" means one thing | Every not-evaluated entry failed the run, every day | A committed baseline, and the run reports *what changed* |

## Where a finding goes

A check that could not run states the declaration it needed; a check that failed states
the parameter that moves it back into bounds. Both are data the screen wrote down, not a
parse of its prose. That field name is looked up in the document's own YAML marks, and
the result is annotated there.

A field the document never declared is exactly the not-evaluated case — the declaration
missing is *why* the check did not run — so the finding lands on the document's first
line rather than on a line that does not mention it.

**A pass is not a result.** Nor is a check the document deliberately deferred: that is a
decision somebody already made. A **warning** is, at `note` level, because a caution
nobody is shown is the silent green this tool exists to refuse.

| Verdict | SARIF level | JUnit |
| --- | --- | --- |
| `fail` | `error` | failure |
| `not_evaluated` | `warning` | **skipped** — never a pass |
| `warning` | `note` | pass |
| `over_margin` | `note` | pass |
| `out_of_depth` | — | skipped |
| `pass` | — | pass |

Both writers are byte-deterministic: no timestamp, no duration, sorted keys. The same
cards give the same file, so it caches, diffs, and can be attached to a
content-addressed bundle.

## The baseline

```bash
anvilate check parts/ --write-baseline parts/baseline.json   # then commit it
```

The baseline is a file of card digests. A later run compares against it and reports each
spec as unchanged, newly failing, newly passing, newly not evaluated, governing check
changed, new, or **missing** — a spec the baseline records and the sweep did not find,
which is a deletion or a rename and wants a person either way.

Three rules:

- **A sweep never writes the baseline.** Comparing against a file that updates itself is
  comparing against nothing. `--write-baseline` is the only thing that writes one.
- **A missing entry is reported, not dropped.**
- **The exit code follows the news.** A repository where every card passes and one spec
  has gone missing exits 1. A newly *passing* spec is not news a gate stops for — failing
  a run over good news is how people learn to ignore runs.

The digest covers the card and deliberately **not** the library version, which is where
it differs from the review digest in `anvilate.review`. A review that survived an upgrade
would be assurance nobody gave; a baseline that marked all forty parts changed on every
upgrade would bury the one part that really changed.

## In GitHub Actions

```yaml
permissions:
  security-events: write
steps:
  - uses: actions/checkout@v4
  - uses: anvilate/anvilate/.github/actions/check@main
    with:
      path: parts/
      sarif: anvilate.sarif
      sarif-category: parts
      baseline: parts/baseline.json
  - uses: github/codeql-action/upload-sarif@v3
    if: always()
    with:
      sarif_file: anvilate.sarif
      category: parts
```

The action writes the file and says how many results it holds; **uploading is your step**,
because an upload needs `security-events: write` and a composite action should not assume
permissions its caller did not grant. GitHub takes 5,000 results per upload; above that
the action warns and tells you to split by folder, one category each.

## On commit

Add this repository to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/clay-good/anvilate
    rev: main
    hooks:
      - id: anvilate-check
```

One hook, not two. A "schema only" variant was written and removed: this CLI has no
validate-only command, so the fast hook would have been the same screen under a name that
said it was not. The budget is the measured one — `tools/responsiveness/budget.json` holds
`check` on one spec to well under a second — and pre-commit passes only the files that
changed. A repository whose commits touch dozens of specs should make this a push hook.

## Out

No hosted dashboard or service. No GitLab, Azure or Jenkins plugins: they read these same
two files. No annotations inside a STEP or DXF a spec references.
