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
| A spent budget has no headroom | Every headroom is unavailable with the overrun stated, never a negative allowance. |
| An assumed limit says so | A `working_assumption` limit is labeled on the scorecard entry. |

Angles are dimensionless to the unit layer, so a microradian budget cannot tell an angle from
a strain; the contributor's name and source are what distinguish them.

## Status

This is the budget's contract and evaluation (`openspec/changes/add-performance-budgets`,
groups 1-3). Nested budgets and growth allowances are not built, and the calculation report
does not itemize a budget.
