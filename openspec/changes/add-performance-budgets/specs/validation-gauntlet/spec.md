# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: Declared budgets are evaluated and itemized on the card

When a spec declares performance budgets, the gauntlet SHALL evaluate each one after the
checks its contributors bind to have run, emit it as a standard scorecard entry, and
itemize its contributors in the rendered report. A declared budget that the gauntlet did
not evaluate SHALL be reported as "not evaluated" naming the budget — a budget in the
document and absent from the card is the silent green this rule forbids.

#### Scenario: Budget appears on the card

- **WHEN** a build completes on a spec declaring two budgets
- **THEN** the scorecard carries two budget entries with their totals, limits, rules, and
  governing contributors, and the report itemizes each budget's contributors

#### Scenario: Budget participates in the verdict

- **WHEN** a budget fails while all other checks pass
- **THEN** the card fails, the budget is eligible to be named the governing check, and the
  part is export-gated exactly as any other failure gates it

#### Scenario: A budget skipped is a budget named

- **WHEN** a declared budget's evaluation is skipped for any reason
- **THEN** the card carries a not-evaluated entry naming the budget and the reason, and
  does not pass
