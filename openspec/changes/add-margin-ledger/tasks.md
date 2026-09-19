# Tasks: Margin ledger

## 1. Contracts

- [x] 1.1 Ledger entry type: value, kind, origin, authority, the quantity it bears on,
      and the direction it moves the result
- [x] 1.2 Kind enumeration as a total map — every consumer handles every kind explicitly,
      with no `else` arm that files an unknown kind under a default
- [x] 1.3 Refusal of an entry with a blank origin or an authority that names no source

## 2. Capture

- [x] 2.1 Thread the ledger through check evaluation so a factor cannot be applied
      without being recorded — `ledger_for` enters each check's required safety factor,
      attributed by where it came from, and `anvilate check` renders the combined ledger
- [x] 2.2 Capture statistical-basis conservatism where a material allowable declares one —
      `MarginEntry.statistical_basis`, typical over allowable; the library applies none itself
- [x] 2.3 Capture rounding conservatism where a value is snapped to a stock size or a
      standard increment — `MarginEntry.rounding`; no screen snaps a size, so the capture
      point is the document or the caller that chose the stock size
- [x] 2.4 Capture contingency and growth allowances from budgets

## 3. Analysis

- [x] 3.1 Cumulative factor per checked quantity, with the multiplication shown
- [x] 3.2 Physics-limited result: re-evaluate with code-required entries only —
      `physics_limited`, printed under the ledger on `anvilate check`
- [x] 3.3 Duplicate detection across origins for the same kind and quantity
- [x] 3.4 Dominant-entry identification with ties reported rather than broken arbitrarily

## 4. Gates

- [ ] 4.1 CI gate: every code path that multiplies or divides a demand or capacity by a
      factor records a ledger entry — detected structurally over the source, not by name —
      measured today over the screened results of every shipped spec, with a floor; the
      source-level detection is still to build
- [ ] 4.2 The gate carries a population floor and an enumerated exclusion list with a
      stated cause per exclusion, so it cannot pass by finding nothing

## 5. Rendering

- [x] 5.1 Ledger table in the calculation report: entry, kind, value, origin, authority
- [x] 5.2 Cumulative factor and physics-limited comparison beside the verdict
- [x] 5.3 Possible-double-count entries rendered with both origins

## 6. Tests

- [x] 6.1 A part with five separately defensible factors reports its cumulative factor,
      and the number is the product — the defect class this capability exists to expose
- [x] 6.2 An unattributed factor is refused
- [x] 6.3 A code-required factor and an elected one never render identically
- [ ] 6.4 Removing a factor from the code changes the ledger, not only the verdict

## 7. Docs & examples

- [x] 7.1 Worked example: the same bracket at code-minimum and as delivered, side by side
- [x] 7.2 Explanation page: why the tool reports conservatism and never removes it —
      docs/margin-ledger.md, "Why it reports conservatism and never removes it"
