# Benchmarking & Quality Assurance Specification (delta)

## ADDED Requirements

### Requirement: An unconservative correlation opens an escaped-defect candidate

The escaped-defect process SHALL accept candidates filed by the model-credibility
correlation — a check that passed and a recorded test that was unconservative beyond the
declared band — alongside user-reported field failures. A candidate SHALL be
dispositioned by a person as an escaped defect (post-mortem and permanent regression,
as today), a test or instrument issue, or a correct conservatism of the test, with the
reason recorded; the count of undispositioned candidates SHALL be reported at every
release beside the count of unresolved escaped defects.

#### Scenario: A candidate becomes a regression

- **WHEN** a correlation candidate is dispositioned as an escaped defect
- **THEN** a regression reproducing the predicted-versus-measured case is added and the
  post-mortem is published before the next release, as the existing process requires

#### Scenario: Candidates are counted, not hidden

- **WHEN** a release is prepared with two undispositioned candidates
- **THEN** the release notes state the count and name the checks
