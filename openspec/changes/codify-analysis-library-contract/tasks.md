# Tasks: Codify the analysis-library contract

## 1. Audit & codify

- [ ] 1.1 Citation coverage audit across the ~495-symbol public surface; backfill gaps
- [x] 1.2 Enumerate the public API explicitly (single source of truth for the surface:
      `docs/api/analysis-public-surface.txt`, enforced by `tests/test_contract.py`)
- [ ] 1.3 Inventory design inverses and their forward-check pairings

## 2. CI enforcement

- [ ] 2.1 Citation-required gate for new public functions
- [ ] 2.2 Worked-example anchor presence check (every public function maps to a sourced test)
- [x] 2.3 Example-per-module coverage gate (`tests/test_contract.py`; backfilled the six
      uncovered modules: clutch, coupling, impact, journal_bearing, rivet, scotch_yoke)
- [x] 2.4 Public-surface diff check (additions/removals are deliberate; removals require
      deprecation path) — manifest diff in `tests/test_contract.py`

## 3. Docs

- [ ] 3.1 Contributor doc: the seven contract rules with examples
- [ ] 3.2 User doc: what a citation on a result means and how to verify it
