# Change: Parts as code in CI — findings on the spec's own lines, reports the dashboards read, and a baseline that says what changed

## Why

`headless-automation` calls the CI lane "the parts-as-code lane no incumbent occupies",
and the pieces that exist are solid: a CLI whose exit codes are the interface, a
container, a reusable action, a geometric diff, an evidence bundle. What a software team
takes for granted in that lane is still missing, and it is what makes a check visible to
the people who did not run it:

- **A finding has no line.** A failing check names the field it reads, in prose. A
  reviewer on a pull request sees a red job and a log, not an annotation on the line of
  the spec that caused it. Every linter in the world does better.
- **A dashboard cannot count it.** CI systems, test reporters and quality gates read
  JUnit XML and SARIF. Anvilate writes JSON in its own shape, so nothing off the shelf
  can chart how many checks pass across a repository of parts, or flag a newly failing
  one.
- **"Fails" means two different things.** A repository of forty specs has, on any given
  day, some not-evaluated entries that are known and accepted and one newly failing
  check that is the news. A job that fails on both teaches people to ignore it.

The formats are open and the tooling is universal. GitHub code scanning accepts SARIF
2.1.0 from any tool and places each result as an annotation on the file and region the
result names, keyed for de-duplication by partial fingerprints, with a limit of 5,000
results per upload. Every CI system reads JUnit XML. A baseline is a file of card
digests, which the evidence identity already provides.

## What Changes

| Area | Change |
| --- | --- |
| SARIF output | `anvilate check` and the repository sweep can write SARIF 2.1.0: one rule per check identifier (with its citation as the rule's help), one result per failing or not-evaluated entry, located on the spec file and the line of the governing field, with a fingerprint stable across runs and machines. Pass entries are not results. |
| JUnit output | One test case per check per spec: failure with the verdict line as the message, not-evaluated as skipped with the reason, never a pass for a skip. |
| Repository sweep | One command screens every spec and product under a folder, writes the reports above, and compares every card against a committed baseline of card digests: newly failing, newly passing, newly not evaluated, changed governing check. The exit code reflects the news, and the step summary says what changed. |
| Baseline discipline | The baseline is updated by an explicit command and committed; a sweep never updates it on its own. A baseline entry whose spec no longer exists is reported, not dropped. |
| The action | The shipped CI action uploads the SARIF with a category per spec set, splits uploads above the platform limit, and writes the change table to the job summary. |
| Pre-commit | A documented hook entry runs schema validation and the tiers that need no geometry on changed specs within a stated budget. |

## Impact

- Delta: `headless-automation` (ADDED). Builds on the CI action in
  `.github/workflows/ci.yml` and the CLI in `src/anvilate/cli.py`, the content-addressed
  card identity in `evidence-attestation`, and `add-interaction-quality` (exit codes
  distinguish refusal, failure and crash; the sweep adds "unchanged").
- Affected code (when implemented): a SARIF writer, a JUnit writer, YAML line marks
  carried from the parser to the refusal and the entry, the sweep command, the baseline
  file, the action's upload step.
- Explicitly out:
  - Any hosted dashboard or service (D1).
  - GitLab, Azure or Jenkins plugins; they read the same files.
  - Annotating lines inside a STEP or DXF the spec references.
