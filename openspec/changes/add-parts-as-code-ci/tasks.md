# Tasks: Parts as code in CI

Affects `src/anvilate/cli.py` and the action in `.github/workflows/ci.yml`.

## 1. Locations

- [x] 1.1 YAML line and column marks carried from the parser onto refusals and card entries
      (the governing field of each check)
- [x] 1.2 Products: the line in the product document, or in the sub-document by path

## 2. Reports

- [x] 2.1 SARIF 2.1.0 writer: rules per check id with citation as help, results for failing
      and not-evaluated entries, regions, partial fingerprints; validated against the
      published schema
- [x] 2.2 JUnit XML writer: one case per check per spec; skipped for not evaluated
- [x] 2.3 Both writers byte-deterministic for the same card

## 3. Sweep and baseline

- [x] 3.1 Repository sweep over a folder; change classification against a committed
      baseline of card digests; exit codes; step summary table
- [x] 3.2 Baseline update as an explicit command; missing specs reported
- [x] 3.3 Action: SARIF upload with category and split above the platform limit; summary
- [x] 3.4 Pre-commit hook entry with its budget; a docs page for parts as code in CI
