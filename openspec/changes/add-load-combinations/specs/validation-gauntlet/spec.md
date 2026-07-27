# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: Combination-aware evaluation with a named governing combination

When a spec declares a combination set, the gauntlet SHALL evaluate applicable checks
under every combination in the set, report the enveloped (worst-case) result per check,
and name the governing combination in the scorecard entry and evidence bundle; results
under non-governing combinations SHALL remain retrievable. Evaluating a subset of the
declared combinations SHALL render the affected checks "not evaluated" for the skipped
combinations — never a pass computed from a silent subset. When no combination set is
declared, per-load-case evaluation proceeds exactly as today.

#### Scenario: Governing combination named

- **WHEN** a beam check runs under a declared LRFD set where 1.2D + 1.6L governs
- **THEN** the scorecard entry reports the enveloped margin and names 1.2D + 1.6L as
  governing, with the per-combination results retrievable

#### Scenario: Counteracting combination catches uplift

- **WHEN** a wind case opposes gravity and the 0.9D + 1.0W combination produces the
  worst margin
- **THEN** the envelope reflects it — minimum-load combinations are evaluated, not only
  additive maxima

#### Scenario: No silent subset

- **WHEN** a run evaluates only 3 of 7 declared combinations
- **THEN** affected checks show "not evaluated" for the remainder and cannot render an
  unqualified pass
