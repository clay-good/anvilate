# Verification Planning Specification (delta)

## ADDED Requirements

### Requirement: The verification plan exports as a DVP&R

The verification plan SHALL export as CSV and XLSX with one row per verification item and
these columns: requirement, item path, test archetype, procedure reference, acceptance
criterion, sample size, timing, owner and recorded result. The acceptance criterion
SHALL come from the driving check. Sample size, timing and owner SHALL be left for the
user when not declared.

#### Scenario: A plan a validation engineer can run

- **WHEN** the plan for a bracket with a fatigue requirement is exported
- **THEN** the durability row names its requirement, the cycle count from the fatigue
  check as its acceptance criterion, and empty owner and timing columns
