# Change: Service-life planning — the maintenance each life-limited check implies

## Why

A design that passes is not a design that lasts without attention. The bearing check
reports a rating life of 23,000 hours. The duty-cycle fatigue check reports damage per
year. The O-ring screen reports compression set over the declared life. The corrosion
screen reports an allowance consumed at a rate. The creep screen reports retention after
1,000 hours at 85 °C. Each of these numbers is a date, and today each sits on its own
card entry while the engineer retypes them into a maintenance schedule by hand, or
nobody does and the product ships with no plan.

`verification-planning` already turns each check into the physical test it implies and
is careful to say that a plan is not evidence. The same inversion applies after the
product is in service: each life-limited check implies an inspection or a replacement,
with an interval that follows from the computed life and a rule the organization
declares. The rule vocabulary is public: NASA's *Reliability-Centered Maintenance Guide
for Facilities and Collateral Equipment* (2008, published by NASA) gives the task types
engineers already use (condition-based, time-directed, failure-finding, and accepted
run-to-failure), and the P-F interval practice that an on-condition task must run more
often than the time between a detectable potential failure and the functional failure.
Anvilate holds the lives; it needs the plan.

This also feeds the release package. A product's spares and consumables are the items
the plan says will be replaced, in the quantity the declared life implies, and today
the buy list cannot know them.

## What Changes

| Area | Change |
| --- | --- |
| Life quantities are typed | Every check that computes a life, a rate of consumption, or a retention over time publishes it as a typed life quantity (hours, cycles, distance, or time at temperature) with its basis and reliability where the method states one. |
| Maintenance items | Each life-limited item resolves to a maintenance item: the task type, the item path, the driving check and its life, the interval, the interval rule the document declared with its source, and the spare or consumable it needs. A life with no declared rule is listed with its life and "interval not set"; the system never invents an interval. |
| P-F intervals | An on-condition task carries the declared P-F interval and its source, and the inspection interval is held to the declared fraction of it. |
| Spares | Replaceable items with the quantity implied by the declared service life, feeding the release package's buy list as a spares list. |
| Coverage | Items with no life-limited check are listed by name with a count, so a plan with three items on a product of thirty is visibly incomplete. |
| Execution | A performed task is recorded like a verification outcome (date, performer, measured condition where any). A measured condition is a correlation point for model credibility. A plan with no recorded tasks is a plan, never evidence. |
| Rendering | A schedule table ordered by interval, as CSV, XLSX and a report section, with each row citing the check and the rule. |

## Impact

- New capability: `service-life-planning`. Delta: `analysis-library` (ADDED).
- Builds on the bearing, fatigue, duty-cycle, wear, corrosion, O-ring, creep and
  retention screens (lives they already compute), `verification-planning` (outcome
  record shape and the "a plan is not evidence" doctrine), `add-product-structure`
  (item paths), `add-release-package` (spares into the buy list),
  `add-failure-mode-coverage` (an unplanned item is a coverage gap of the same kind),
  and `add-model-credibility` (a measured condition correlates with the prediction).
- Licensing: the NASA RCM guide is a NASA publication used for its task vocabulary;
  no commercial RCM standard is reproduced. Interval rules are the user's, with a
  citation.
- Explicitly out:
  - Any default interval, life factor or reliability target.
  - Work-order, CMMS or ERP integration (files only).
  - Reliability prediction from handbooks (MIL-HDBK-217 class) or fleet statistics.
  - Lubrication selection.
