# Change: Performance budgets — the allocation a scorecard of independent checks cannot see

## Why

The gauntlet answers "does each check pass." Real systems fail on the sum. A line-of-sight
requirement of 0.1 mrad is not blown by one contributor; it is blown by eight small ones —
thermal soak, mount compliance under shock, assembly eccentricity, preload relaxation,
bearing runout — each of which passes its own screen. Anvilate can today report every one
of those as green and hand back a design that misses its top-level requirement, which is
the exact silent green the project exists to refuse.

`tolerance-management` solves this for *dimensions*. Nothing solves it for *performance
quantities*, and the shape is identical: an allocated limit, a set of contributors, a
declared combination rule, and a margin. Mass budgets, power budgets, thermal rise
budgets, positioning-error budgets, and optical wavefront budgets are all one primitive.

It belongs in the foundation and not in a module, because the first module that needs it
would otherwise build a private version that no other module can read, and because the
combination rule is the part engineers most often get wrong: root-sum-square across terms
that are actually correlated understates the total, and no tool that defaults the rule
silently can be trusted with the result.

## What Changes

- New capability spec `performance-budgets`: a typed budget with an allocated limit,
  ordered contributors each carrying a value and its source, an **explicitly declared**
  combination rule with correlated terms summed rather than RSS'd, a computed total, a
  margin, and a named governing contributor.
- Contributors bind to scorecard check ids, so a budget recomputes when its screens do,
  and a contributor whose screen did not run makes the budget "not evaluated."
- The inverse pairs with the forward, as the analysis library already requires: given a
  budget and its contributors, report each contributor's headroom — how far it may grow
  before the budget is spent.
- `spec-ir` gains a typed budget declaration so a budget is part of the document, diffable
  and versioned, rather than assembled ad hoc in a script.
- `validation-gauntlet` gains budgets as first-class scorecard entries, itemized in the
  report, and subject to no-silent-green.

- **ADDED** budgets nest (a contributor may be a budget, cycles refused); double counting
  refused by bound-source identity rather than by name; contributors carry a basis
  (measured / calculated / estimated) with the growth allowance that follows from it, per
  established mass-properties practice; compensating terms declared rather than netted;
  the allocated limit carries its own provenance so an assumed limit never reads as a
  requirement; and the governing contributor is computed under the declared rule with
  ties reported.

## Impact

- Affected specs: new `performance-budgets`; `spec-ir` (ADDED); `validation-gauntlet`
  (ADDED). Interacts with `tolerance-management` (dimensional stack-ups stay where they
  are and may feed a budget as one contributor), `uncertainty-quantification` (a
  contributor may carry a band), and `calculation-report` (itemized rendering).
- Affected code (when implemented): a budget model, a combination-rule evaluator, a
  binding from contributors to scorecard ids, and report rendering.
- Explicitly out: statistical tolerancing methods beyond declared worst-case and RSS;
  Monte Carlo budget propagation; automatic allocation optimization.
