# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Every check cites its source

Every analysis function that produces an engineering verdict or sized quantity SHALL carry a citation — handbook (author, title, edition, section) or standard (designation, edition, clause) — and that citation SHALL travel with the result into scorecards, evidence, and reports; a function without a citation MUST NOT ship in the public API.

#### Scenario: Citation travels to the scorecard

- **WHEN** a sheave-bending screen contributes to a scorecard
- **THEN** the entry carries the citation the function declares, without the caller re-supplying it

#### Scenario: Uncited function rejected

- **WHEN** a new public analysis function is submitted without a citation
- **THEN** CI rejects it naming the function

### Requirement: Unit-typed API surface

Public analysis functions SHALL accept and return unit-carrying quantities only; raw floats for physical quantities are prohibited in the public API, and dimensional mismatches SHALL be rejected at call time naming the parameter and expected dimension.

#### Scenario: Wrong dimension rejected at the boundary

- **WHEN** a caller passes a force where a stress is expected
- **THEN** the call fails immediately naming the parameter, received dimension, and expected dimension

### Requirement: Worked-example regression anchoring

Every analysis function SHALL be tested against at least one published worked example (Roark/Shigley/AISC/ASME-class) reproducing the source's result within a stated tolerance, with the source identified in the test; refactors that drift a worked-example result SHALL fail CI.

#### Scenario: Textbook anchor holds

- **WHEN** the test suite runs
- **THEN** each function reproduces its cited worked example within tolerance, and a numerical drift fails the build naming the function and source

### Requirement: Design inverses pair with forward checks

Where the library provides a design inverse (solve for the dimension, count, or rating that satisfies a check), the inverse SHALL be paired with its forward check and round-trip tested: the inverse's output, fed to the forward check, satisfies the required margin at the declared tolerance; inverses SHALL be discoverable from their forward checks for repair-hint binding.

#### Scenario: Round trip closes

- **WHEN** the bearing-rating inverse computes the dynamic rating for a target life
- **THEN** the forward life check at that rating meets the target within the declared tolerance, verified in CI

### Requirement: Runnable example per module

Every analysis module SHALL ship at least one runnable example that demonstrates an engineering decision (not just an API call) — a governing check identified, a trade-off surfaced, or a failure caught — executed in CI so examples cannot rot.

#### Scenario: Example teaches a decision

- **WHEN** a new analysis module merges
- **THEN** it includes a CI-executed example whose output shows a scorecard verdict a practicing engineer would act on

### Requirement: Public API stability

The public analysis surface SHALL follow semantic versioning: breaking changes only at major versions, deprecations announced with a documented replacement and retained for at least one minor release with a warning; the public surface SHALL be explicitly enumerated so additions are deliberate.

#### Scenario: Deprecation is survivable

- **WHEN** a public function is renamed
- **THEN** the old name keeps working with a deprecation warning naming the replacement for at least one minor release before removal

### Requirement: User-supplied allowables doctrine

Where a check's governing values come from copyrighted compilations (code allowable-stress tables, reference design values, proprietary coefficients), the library SHALL accept them as user-supplied inputs carrying user provenance, cite the clause that consumes them, and MUST NOT bundle the copyrighted values; results SHALL state that the allowable was user-supplied.

#### Scenario: Copyrighted table never bundled

- **WHEN** a check requires an allowable stress published only in a copyrighted table
- **THEN** the function takes the allowable as a parameter, the result records user provenance for it, and no bundled data ships the table's values

#### Scenario: Provenance in the report

- **WHEN** a scorecard entry used a user-supplied allowable
- **THEN** the rendered report marks that value as user-supplied alongside the clause citation
