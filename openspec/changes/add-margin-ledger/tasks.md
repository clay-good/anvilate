# Tasks: Margin ledger

## 1. Contracts

- [ ] 1.1 Ledger entry type: value, kind, origin, authority, the quantity it bears on,
      and the direction it moves the result
- [ ] 1.2 Kind enumeration as a total map — every consumer handles every kind explicitly,
      with no `else` arm that files an unknown kind under a default
- [ ] 1.3 Refusal of an entry with a blank origin or an authority that names no source

## 2. Capture

- [ ] 2.1 Thread the ledger through check evaluation so a factor cannot be applied
      without being recorded
- [ ] 2.2 Capture statistical-basis conservatism where a material allowable declares one
- [ ] 2.3 Capture rounding conservatism where a value is snapped to a stock size or a
      standard increment
- [ ] 2.4 Capture contingency and growth allowances from budgets

## 3. Analysis

- [ ] 3.1 Cumulative factor per checked quantity, with the multiplication shown
- [ ] 3.2 Physics-limited result: re-evaluate with code-required entries only
- [ ] 3.3 Duplicate detection across origins for the same kind and quantity
- [ ] 3.4 Dominant-entry identification with ties reported rather than broken arbitrarily

## 4. Gates

- [ ] 4.1 CI gate: every code path that multiplies or divides a demand or capacity by a
      factor records a ledger entry — detected structurally over the source, not by name
- [ ] 4.2 The gate carries a population floor and an enumerated exclusion list with a
      stated cause per exclusion, so it cannot pass by finding nothing

## 5. Rendering

- [ ] 5.1 Ledger table in the calculation report: entry, kind, value, origin, authority
- [ ] 5.2 Cumulative factor and physics-limited comparison beside the verdict
- [ ] 5.3 Possible-double-count entries rendered with both origins

## 6. Tests

- [ ] 6.1 A part with five separately defensible factors reports its cumulative factor,
      and the number is the product — the defect class this capability exists to expose
- [ ] 6.2 An unattributed factor is refused
- [ ] 6.3 A code-required factor and an elected one never render identically
- [ ] 6.4 Removing a factor from the code changes the ledger, not only the verdict

## 7. Docs & examples

- [ ] 7.1 Worked example: the same bracket at code-minimum and as delivered, side by side
- [ ] 7.2 Explanation page: why the tool reports conservatism and never removes it
