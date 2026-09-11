# Tasks: Performance budgets

## 1. Contracts

- [ ] 1.1 Budget type: allocated limit, contributors, combination rule, total, margin
- [ ] 1.2 Contributor type: name, value, unit, source (check id / measurement /
      user-declared with provenance), correlation group, optional band
- [ ] 1.3 Combination-rule enumeration with no default value

## 2. Evaluation

- [ ] 2.1 Worst-case linear sum; RSS; hybrid with correlated groups summed then RSS'd
- [ ] 2.2 Unit and dimension checking across contributors and the allocated limit
- [ ] 2.3 Governing-contributor identification
- [ ] 2.4 Headroom inverse: per-contributor allowable growth at the current total

## 3. Wiring

- [ ] 3.1 Spec IR budget declaration, schema-validated and diffable
- [ ] 3.2 Contributor binding to scorecard check ids; recompute on screen change
- [ ] 3.3 Scorecard entry emission; not-evaluated propagation from any unevaluated
      contributor

## 4. Rendering

- [ ] 4.1 Itemized budget table in the calculation report: each contributor, its source,
      its share of the total, the rule, the margin
- [ ] 4.2 Render in the reader's declared unit system, angular units included

## 5. Tests

- [ ] 5.1 RSS of correlated terms is refused, not silently computed
- [ ] 5.2 One unevaluated contributor makes the budget not-evaluated, never a pass
- [ ] 5.3 A budget whose contributors are all passing checks can still fail, with the
      governing contributor named — the defect class this capability exists to catch
- [ ] 5.4 Headroom inverse round-trips against the forward evaluation

## 6. Docs & examples

- [ ] 6.1 Worked example: a mass budget and an angular-error budget on the same part
- [ ] 6.2 Explanation page: why the combination rule is declared and never defaulted
