# Tasks: Codify the analysis-library contract

## 1. Audit & codify

- [ ] 1.1 Citation coverage audit across the ~495-symbol public surface; backfill gaps
- [ ] 1.2 Enumerate the public API explicitly (single source of truth for the surface)
- [ ] 1.3 Inventory design inverses and their forward-check pairings

## 2. CI enforcement

- [ ] 2.1 Citation-required gate for new public functions
- [ ] 2.2 Worked-example anchor presence check (every public function maps to a sourced test)
- [ ] 2.3 Example-per-module coverage gate
- [ ] 2.4 Public-surface diff check (additions/removals are deliberate; removals require
      deprecation path)

## 3. Docs

- [ ] 3.1 Contributor doc: the seven contract rules with examples
- [ ] 3.2 User doc: what a citation on a result means and how to verify it
