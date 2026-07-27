# Benchmarking Specification (delta)

## ADDED Requirements

### Requirement: Local-model recommendation gated on correctness, not validity

The published local-model recommendation SHALL be derived from separately measured schema
validity, field-level correctness, and wrong-but-valid rate on a versioned compilation
task set, and SHALL NOT be derived from schema validity alone. A model whose wrong-but-
valid rate exceeds the declared threshold MUST NOT be recommended regardless of its
validity score, and the published recommendation SHALL state all three figures with the
task-set version and the constrained-decoding configuration used.

#### Scenario: High validity, poor correctness, not recommended

- **WHEN** a candidate model produces schema-valid output nearly always but exceeds the
  wrong-but-valid threshold
- **THEN** it is not recommended, and the published table shows why

#### Scenario: Configuration is part of the result

- **WHEN** a recommendation is published
- **THEN** it names the task-set version, the decoding configuration, and whether the
  two-pass compilation shape was used — results are never presented as properties of the
  model alone
