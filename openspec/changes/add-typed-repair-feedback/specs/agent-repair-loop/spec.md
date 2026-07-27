# Agent Repair Loop Specification (delta)

## ADDED Requirements

### Requirement: Inverse-first repair

When a failed check carries a repair hint with a corrective value from a design inverse, the deterministic planner SHALL apply that value directly (clamped to pattern parameter bounds) and revalidate, before any bounded numeric search and before any LLM involvement; hint-driven repairs SHALL be recorded in iteration provenance as inverse-solved.

#### Scenario: One-solve repair

- **WHEN** the only failure carries a corrective thickness from a design inverse within pattern bounds
- **THEN** the planner applies it and revalidates in a single iteration, with no search and no LLM call

#### Scenario: Hint out of bounds escalates honestly

- **WHEN** a corrective value falls outside the pattern's declared parameter bounds
- **THEN** the planner escalates per the existing cost-ordered strategy and the iteration record states that the inverse solution was infeasible within bounds
