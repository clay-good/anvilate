# Margin ledger

No-silent-green refuses a pass that was not earned. The margin ledger is its mirror: it
refuses to let a pass be *over*-earned in silence. A code factor, an elected factor on top,
a load contingency and a plate snapped up to stock are each defensible alone. Their product
is the number nobody states, so the ledger states it.

## What you get

```python
from anvilate.margin import MarginAction, MarginEntry, MarginKind, MarginLedger

q = "bracket bending stress"
ledger = MarginLedger(entries=(
    MarginEntry(label="ASD factor", kind=MarginKind.CODE_REQUIRED, value=1.67, quantity=q,
                action=MarginAction.LOWERS_CAPACITY, origin="check: bracket bending",
                authority="AISC 360-22 §F1"),
    MarginEntry(label="project factor", kind=MarginKind.USER_ELECTED, value=1.2, quantity=q,
                action=MarginAction.LOWERS_CAPACITY, origin="spec: design_factor",
                authority="user election: engineering judgment"),
    MarginEntry(label="load growth", kind=MarginKind.CONTINGENCY, value=1.1, quantity=q,
                action=MarginAction.RAISES_DEMAND, origin="spec: loads.growth",
                authority="company practice DP-104"),
    MarginEntry(label="future allowance", kind=MarginKind.CONTINGENCY, value=1.15, quantity=q,
                action=MarginAction.RAISES_DEMAND, origin="pack: bracket",
                authority="company practice DP-104"),
    MarginEntry.rounding(label="plate thickness", nominal=9.1, delivered=9.525, quantity=q,
                         origin="stock snap", authority="ASTM B209 stock gauge list"),
))

stack = ledger.stack(q)
stack.multiplication()                  # "1.67 x 1.2 x 1.1 x 1.15 x 1.047 = 2.653"
stack.physics_limited                   # 1.67  — code-required factors only
stack.elected                           # 1.589 — everything no cited code obliges
stack.physics_limited_utilization(0.62) # 0.41  — the same plate at code minimum
stack.dominant()                        # (the ASD factor,) — ties come back together
ledger.double_counts()                  # two contingencies from two origins, x1.265 combined
ledger.stack("anchor bolt tension")     # "anchor bolt tension: no conservatism recorded"
```

## The rules

| Rule | What it means |
| --- | --- |
| Every entry is attributed | A blank `origin` or `authority` is refused. "Engineering judgment" is accepted as a `USER_ELECTED` entry whose authority says so. |
| A margin is at least 1 | A factor below 1 makes a result less conservative; NaN and infinity are refused. A factor of exactly 1 is recorded as moving nothing. |
| Kinds never render alike | `code_required`, `user_elected`, `statistical_basis`, `contingency_or_growth`, `rounding`, `derating`. Every kind is described in one total table; adding a kind without describing it fails at import. |
| Duplicates are named, not resolved | Two entries of the same kind on the same quantity from different origins are a possible double count, found by kind and quantity, never by wording. Both stay in the product. |
| Ties are ties | The dominant entry is the largest factor; equal factors are all reported. |
| Empty is a finding | A quantity with no entries says "no conservatism recorded" instead of rendering blank. |

Rounding is recorded as the ratio of delivered to nominal on the dimension itself. How
strongly that ratio moves a stress (as t² or t³) is the check's business, not the ledger's.

A statistical basis is recorded the same way, by `MarginEntry.statistical_basis`: the ratio of
the typical value to the allowable a capacity is designed to, so 6061-T6 taken at its
240 MPa specification minimum against its 276 MPa typical carries a factor of 1.15. It is
elected conservatism, never code-required, and an allowable above the typical value is
refused, because a floor above the middle of the scatter is not a margin. The library
applies neither of these factors itself: no screen snaps a size to stock or knocks a typical
value down, and the packs refuse a typical value where a code wants a minimum rather than
correcting it. So both are recorded where they happen, in the document or by the caller
that chose the stock size or the basis.

## Why it reports conservatism and never removes it

Stacked conservatism is real and it costs mass, money and stiffness. A part carrying a code
factor, an elected factor, a statistical allowable, a load contingency and a stock-size
rounding can carry far more margin than anyone chose. The ledger exists to make that
visible. It still does not act on it, for three reasons:

- **A factor's reason is not in the number.** An elected 1.25 may cover a load nobody has
  measured, a weld nobody will inspect, or a customer's standing instruction. The ledger
  records who elected it and on what authority. Whether that authority still holds is a
  judgement about the project, and the project is not in the ledger.
- **Removing a factor is a design decision with an owner.** A tool that trimmed a
  "redundant" factor would make the lighter part the default and turn a safety
  argument into a line nobody signed. Surfacing the stack puts the decision in front of
  the engineer who can own it.
- **The asymmetry of the errors.** A factor kept that could have gone costs material. A
  factor removed that was carrying an unstated load costs the part. A screening tool
  should be wrong in the first direction.

So the ledger multiplies the factors out, names the double counts, shows which factor
dominates, and reports the physics-limited utilization beside the delivered verdict. What
to do with that is left to the reader, deliberately.

## What it does not do

The ledger informs and never decides. It does not remove, reduce or recommend relaxing any
factor, and the physics-limited utilization is reported beside the delivered verdict,
never instead of it. It is the delivered part judged at code minimum: each elected
multiplier scales utilization linearly and is divided out, while rounding stays, because a
utilization computed at the stock size already contains it in the geometry.

## Declaring margins in a spec

A Design Spec (1.7.0 and later) states its conservatism under `constraints.margins`, one
entry per factor with the same fields as `MarginEntry`. Reading it back is one line:

```python
from anvilate.margin import MarginLedger

ledger = MarginLedger(entries=spec.constraints.margins)
```

[`examples/bracket_margin_stack.py`](../examples/bracket_margin_stack.py) runs one bracket
plate at code minimum and as delivered, side by side.

`anvilate check` prints that ledger under the card and carries it in `--format json` as
`margins`; the verdict and exit code never read it.
A [calculation report](calculation-reports.md) renders the same ledger as a table from
`CalculationReport(margins=...)`.

A [performance budget](performance-budgets.md) records its per-basis growth allowances here
too: `budget.evaluate().ledger()` returns them as contingency-or-growth entries.

## Status

This is the ledger's contract and arithmetic (`openspec/changes/add-margin-ledger`, groups 1
and 3), a worked example, the spec field that declares entries, and its rendering on
`anvilate check` and in the calculation report. `ledger_for(card, spec)` adds every factor a
check applied to the ones the document declares: a check judged against a required safety
factor above 1 is entered as the user's election when that factor is the document's own
`min_safety_factor`, as code-required when the check cites the clause, and as an uncited
election otherwise. A test screens every shipped example spec and fails if any applied
factor is missing from its ledger. Not built yet: detecting, over the source rather than the
screened results, every place a factor is applied, with its exclusions stated (4.1, 4.2),
and re-evaluating a check at code-required factors only (3.2).
