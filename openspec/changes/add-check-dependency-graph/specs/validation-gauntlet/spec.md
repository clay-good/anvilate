# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: Checks evaluate in dependency order, and cycles are refused

The gauntlet SHALL evaluate checks within a tier in an order consistent with their
declared consumptions, so no check runs before an input it consumes has been produced.
Checks with no ordering relation SHALL evaluate in a stable, recorded order so that a run
is reproducible. A cycle among declared consumptions SHALL be refused before evaluation
begins, naming every member of the cycle rather than only the edge that closed it; the
system MUST NOT break a cycle by choosing a starting point.

#### Scenario: Declaration order does not decide evaluation order

- **WHEN** a chain of six checks is declared in an order unrelated to its dependencies
- **THEN** evaluation follows the dependencies, and the realized order is recorded in the
  evidence bundle

#### Scenario: A cycle names all of its members

- **WHEN** three checks consume each other in a loop
- **THEN** the build refuses naming all three, and no partial result is reported

#### Scenario: Order is stable across runs

- **WHEN** the same spec is evaluated twice with identical inputs and versions
- **THEN** the recorded evaluation order is identical

### Requirement: Not-evaluated propagates downstream, and defaults never fill the gap

A check SHALL report "not evaluated" naming the upstream check it waited on whenever an
input it consumes was not produced, and the reason SHALL travel the full chain so the card
names the original cause rather than only the immediate one. A check MUST NOT substitute a
default, a nominal, or a remembered value for an input an upstream check failed to
produce, because a verdict computed from a filled gap is the silent green this system
exists to refuse.

#### Scenario: The original cause reaches the card

- **WHEN** a material property is missing, its thermal check does not evaluate, and four
  checks downstream consume that chain
- **THEN** all five entries are not-evaluated and each names the missing property as the
  root cause, not merely its immediate upstream

#### Scenario: No fallback verdict

- **WHEN** a downstream check has a plausible default for a consumed input
- **THEN** it still reports not-evaluated rather than computing a verdict from the default

### Requirement: A scorecard never mixes two evaluations of one chain

Changing an upstream result SHALL invalidate the full transitive closure downstream of it,
and the gauntlet SHALL either recompute that closure or mark every member stale. A
scorecard MUST NOT present some values from a chain's previous evaluation beside others
from its current one, because a card internally inconsistent about one chain is worse than
one that says it is stale.

#### Scenario: Partial invalidation is not permitted

- **WHEN** an upstream input changes and only the immediate consumer is recomputed
- **THEN** the card is rejected as inconsistent, or every transitive consumer is marked
  stale — never a mixture rendered as current

#### Scenario: Stale is visible, not inferred

- **WHEN** a chain is stale
- **THEN** every stale entry says so on the rendered card, not only in metadata

### Requirement: A downstream result carries the chain that produced it

A downstream check's result SHALL name the chain of upstream checks its inputs came from,
and its rendered derivation SHALL show that chain rather than only the final substitution.
Margin-ledger entries applied anywhere in the chain SHALL be inherited by the downstream
result so its cumulative conservatism reflects the whole chain, not the last link.

#### Scenario: The derivation shows where the number came from

- **WHEN** a displacement verdict is rendered at the end of a six-link chain
- **THEN** the derivation names each upstream check and the value it supplied

#### Scenario: Upstream conservatism is not lost downstream

- **WHEN** a factor is applied to a temperature that a downstream displacement consumes
- **THEN** the displacement result's cumulative factor includes that entry, attributed to
  the upstream check
