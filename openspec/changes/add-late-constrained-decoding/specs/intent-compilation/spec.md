# Intent Compilation Specification (delta)

## ADDED Requirements

### Requirement: Reason unconstrained, package under constraint

Spec compilation SHALL separate reasoning from packaging: an unconstrained pass produces
the model's working-out, and a subsequent constrained pass produces the schema-valid Spec
IR from it. Grammar or schema constraints MUST NOT be applied to the reasoning pass. The
packaged output remains subject to the existing schema validation before use, and the
reasoning pass's output MUST NOT cross a subsystem boundary or reach any downstream stage
— it is retained only for provenance and debugging.

#### Scenario: Two passes, one validated artifact

- **WHEN** a prose description is compiled
- **THEN** the reasoning pass runs unconstrained, the packaging pass emits schema-valid
  Spec IR, and only the validated Spec IR proceeds downstream

#### Scenario: Reasoning never leaks

- **WHEN** the compiler finishes
- **THEN** the reasoning text is recorded in provenance and is not consumed by geometry,
  validation, or export

#### Scenario: Single-pass fallback is explicit

- **WHEN** a backend cannot support the two-pass shape
- **THEN** the compiler may fall back to single-pass constrained generation, and the
  fallback is recorded in provenance so its accuracy characteristics are attributable

### Requirement: Schema naming is a controlled prompt surface

Schema field names and descriptions used in the constrained packaging pass SHALL be
treated as part of the prompt surface, because they act on the model as instructions:
they are version-controlled, changed deliberately, and any change SHALL be evaluated for
its effect on compilation correctness before release.

#### Scenario: Renaming is evaluated

- **WHEN** a Spec IR field name or description used in packaging changes
- **THEN** the compilation evaluation runs and the correctness effect is recorded in the
  release notes

### Requirement: Validity and correctness are reported separately

Compilation quality SHALL be reported as distinct metrics — schema validity, field-level
correctness against reference specs, and the rate of outputs that are schema-valid but
materially wrong — and MUST NOT be collapsed into a single success figure. A wrong-but-
valid output is a defect of the same class as a malformed one and SHALL be counted as
such.

#### Scenario: Wrong-but-valid is visible

- **WHEN** compilation evaluation reports results
- **THEN** schema validity, field-level correctness, and wrong-but-valid rate appear as
  separate numbers

#### Scenario: A perfect validity score is not a passing grade

- **WHEN** a backend achieves 100% schema validity with materially wrong field values
- **THEN** the report shows the correctness shortfall and the backend is not presented as
  performing well
