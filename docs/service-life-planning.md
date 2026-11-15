# Service-life planning

**Nothing here invents an interval.** An interval is a life a check computed times a rule
your document declared, with the rule's source beside it. A life no declared rule reaches
becomes an item reading `interval not set` — never a quietly shorter schedule, and never a
fraction this library picked for you.

A design that passes is not a design that lasts without attention. The bearing check
reports a rating life. The duty-cycle check reports damage per life. Each of those numbers
is a date, and until now somebody retyped it into a schedule by hand.

```python
from anvilate.service_life import IntervalRule, TaskType, plan_service_life

rule = IntervalRule(
    name="replace rolling bearings at half of rating life",
    task=TaskType.TIME_DIRECTED,
    source="the plant's rotating-equipment maintenance policy, rev 4 §5.2",
    applies_to=("bearing rating life",),
    fraction_of_life=0.5,
)
plan = plan_service_life(card, rules=(rule,), product_items=everything)
print(plan.summary())
# 1 scheduled items, 0 with no interval set, 3 items with no life basis,
# 0 tasks performed — plan status not_evaluated
```

## The four tasks

| Task | What sets the interval |
| --- | --- |
| `time_directed` | A declared fraction of the computed life. Replace or restore. |
| `on_condition` | A declared fraction of the declared **P-F interval** — the time between a detectable potential failure and the functional one. Inspecting less often than that is inspecting after the fact. |
| `failure_finding` | A declared fraction of the life, for a hidden function nobody would otherwise notice had failed. |
| `run_to_failure` | Nothing. Accepting a failure is the decision not to schedule, and a rule stating both is refused. |

The names are the NASA *Reliability-Centered Maintenance Guide for Facilities and
Collateral Equipment* (2008). Nothing of a commercial RCM standard is reproduced.

## A life is typed, not parsed

A check whose result is a life publishes a `LifeQuantity`: the value, the method that
produced it, and the reliability where the method states one. The plan reads that; it never
parses the detail line.

```python
LifeQuantity(kind=LifeKind.HOURS, value=Quantity.parse("23000 hour"),
             basis="ISO 281 basic rating life L10", reliability=0.90)
```

A method that states no reliability leaves it unset. Unset is not `1.0`, and nothing fills
it in. Lives come in hours, cycles, distance, or time at a declared temperature — a
compression set over 1,000 hours means nothing without the temperature it was at, so that
kind requires one.

Which checks publish a life, and which do not, is a census CI keeps in
[`docs/api/life-publishing-checks.txt`](api/life-publishing-checks.txt). A new wear check
that ships without one shows up there by name rather than making the plan quietly shorter.

## What the plan says about itself

**Coverage.** Every product item no life-limited check reached is named, with a count.
Three planned items on a product of thirty reads as three planned and twenty-seven without
a life basis — a plan that listed only what it covers reads identically either way.

**A plan is not a maintenance record.** Items carry no result. Record a `PerformedTask`
— date, performer, and any measured condition — and the plan reports `pass` only once
every scheduled item has one. A measured condition goes on to
[model credibility](model-credibility.md) as a referent for the driving check: 0.3 mm of
wear read against a predicted 0.25 mm is a correlation, and it changes no verdict.

**Spares.** With a declared service life (and the duty per year, when the interval is in
running hours and the life is calendar time) each replaceable item gets a count with its
arithmetic shown. It rounds up: a fraction of a replacement is a whole part on the shelf.
Without a declared service life there are no spares, because the count would be a guess.

## Out

`plan.to_csv()`, `plan.to_xlsx()` (Schedule, Spares and Uncovered sheets) and
`plan.section()` for a report. `export_package(..., plan=plan)` writes `maintenance.csv`
and `spares.csv` beside the [release package](release-package.md)'s `buy.csv` — two files
and not one, because a spare is bought on a policy decision and the buy list is what the
product is made of.

## Out of scope

Any default interval, life factor or reliability target. Work-order, CMMS or ERP
integration — files only. Reliability prediction from handbooks or fleet statistics.
Lubrication selection.

Worked end to end in
[`examples/conveyor_bearing_maintenance.py`](../examples/conveyor_bearing_maintenance.py).
