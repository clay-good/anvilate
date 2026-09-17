# Performance budgets

Every check on a card can pass while the part still fails. Four alignment errors, each
inside its own tolerance, can combine past the line-of-sight requirement, and no per-check
screen sees it because the requirement belongs to the combination. A budget states that
requirement as data and screens it.

## What you get

```python
from anvilate.budget import Budget, CombinationRule, Contributor, ContributorBasis, LimitBasis
from anvilate.units import Quantity

def term(name, value, **fields):
    return Contributor(name=name, value=Quantity(magnitude=value, unit="µrad"),
                       source=f"check {name}", basis=fields.pop("basis", "calculated"), **fields)

budget = Budget(
    name="line of sight", quantity="pointing error",
    limit=Quantity(magnitude=100.0, unit="µrad"),
    limit_basis=LimitBasis.REQUIREMENT, limit_source="SRD §4.2",
    rule=CombinationRule.HYBRID,
    contributors=(
        term("mount", 30.0, correlation_group="thermal"),
        term("bench", 20.0, correlation_group="thermal"),
        term("jitter", 40.0, basis=ContributorBasis.ESTIMATED),
        term("alignment", 25.0, basis=ContributorBasis.MEASURED),
    ),
)
result = budget.evaluate()
result.total              # 68.74 µrad — the thermal pair summed to 50, then root-sum-square
result.governing          # ("mount",) — not jitter, the largest single value
result.estimated_share    # 0.339 — how much of the total rests on an estimate
result.to_entry()         # a scorecard entry: total against limit, governing term named
```

`mount` governs although `jitter` is larger, because the governing contributor is found by
re-evaluating the rule without each term: removing `mount` also shrinks the correlated
group it is summed into. Headroom is the inverse: `mount` could grow to 68.18 µrad, the
others held, before the limit is spent.

## Bound to the screens that produced them

A contributor that names a `check` takes its value from the scorecard, not from the
document: `budget.bind(card)` reads each bound entry's measured quantity, so a rerun screen
moves the total with it. A check that is missing from the card, appears on it twice, did not
run, or measured nothing leaves the contributor unresolved with that reason, and the budget
is not evaluated. A value declared beside a binding is not kept, because a stale number is
worse than none. A bound check of the wrong dimension is refused like any other contributor.

## Declared in a spec, evaluated on the card

A Design Spec (1.8.0 and later) declares budgets under a top-level `budgets:` list, with the
same fields as `Budget`. `screen_spec` evaluates each one last, after the checks its
contributors bind to have run, and emits it as an ordinary scorecard entry — so a budget can
fail a card whose every other check passes, and it is eligible to be the governing check and
gates export like any other failure. A declared budget the screen could not evaluate is a
`not_evaluated` entry naming it; a budget is never missing from the card.

## The rules

| Rule | What it means |
| --- | --- |
| No default rule | `worst_case`, `rss` and `hybrid` give different totals. A budget declared with `rule=None` is `not_evaluated`, naming the missing rule. |
| Correlated terms are never RSS'd | Two contributors in one correlation group under `rss` are refused, naming the group and pointing at `hybrid`, which sums each group before quadrature. |
| A missing term is not zero | A contributor with no value carries the reason, and the whole budget is `not_evaluated` naming it. |
| One dimension | A contributor whose dimension differs from the limit's is refused, naming both. Offset temperature scales are refused; state a difference. |
| One check, one term | Two contributors bound to the same `check` id are refused, naming both. |
| Compensation is declared | A negative value must be `compensating=True`, the result reports the total with and without it, and compensation is refused under quadrature, where its sign is squared away. |
| Shares sum to one | Linearly under worst case; as a share of the squared total under quadrature. |
| A budget can be a term | `sub_budget=` makes a contributor another budget, evaluated under its own rule and entering as one value, with both rules shown. Nesting is bounded at eight levels, and a sub-budget carrying an ancestor's name is refused naming the chain. A sub-budget that did not evaluate leaves its parent not evaluated. |
| A growth allowance is ledgered, not folded in | `growth=(GrowthAllowance(basis=..., factor=..., authority=...),)` applies a factor to every contributor of one basis — practice expects an estimate to grow more than a measurement — and `result.ledger()` returns the applied allowances as [margin-ledger](margin-ledger.md) entries of kind contingency-or-growth. At most one allowance per basis, and a factor below 1 is refused. |
| A spent budget has no headroom | Every headroom is unavailable with the overrun stated, never a negative allowance. |
| An assumed limit says so | A `working_assumption` limit is labeled on the scorecard entry. |

Angles are dimensionless to the unit layer, so a microradian budget cannot tell an angle from
a strain; the contributor's name and source are what distinguish them.

## In the calculation report

`CalculationReport(budgets=...)` takes evaluated budgets and renders each one as a headline
— total against the allocation, margin, rule and governing contributor — over a table of
its contributors with each one's value, source and share of the total. Every figure is
rendered in the report's declared unit system, and a budget that was not evaluated states
its reason and itemizes nothing. With no budgets the heading stays and says `none declared`.
The calc record carries them from schema 1.3.

[`examples/optical_bench_budgets.py`](../examples/optical_bench_budgets.py) puts a mass
budget and a pointing budget on one part: the mass budget passes with headroom, and the
pointing budget fails on the hybrid rule while every screen behind it passes — the same four
numbers combine to 59.4 µrad uncorrelated and 68.7 µrad with the thermal pair summed first.

An allowance is applied to the value the rule combines, and recorded rather than absorbed:
pass `result.ledger().entries` into `CalculationReport(margins=...)` and the allowance appears
in the report's margin ledger with its authority, beside the budget it came from.

## Status

This is the budget's contract and evaluation (`openspec/changes/add-performance-budgets`,
groups 1-4, 6.1, per-basis growth allowances and nested budgets). A top-level performance
limit declared with no budget allocated against it is not yet reported as such.
