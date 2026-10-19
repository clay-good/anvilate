# verification-planning Specification (delta)

## ADDED Requirements

### Requirement: A recorded outcome with a measured value reaches correlation

A recorded verification outcome SHALL be able to carry the measured value of the quantity
its item was planned to verify, with its unit and the instrument's stated uncertainty
where known, and recording such an outcome SHALL make it available to the
model-credibility correlation. An outcome recorded without a measured value SHALL remain
a valid record and SHALL be shown as uncorrelated, never as agreeing.

#### Scenario: A measured value flows on

- **WHEN** a torque-verification outcome records a measured preload of 41.2 kN
- **THEN** the value, its unit and the instrument's uncertainty are available to the
  correlation, and the plan shows the item as performed and correlated

#### Scenario: Pass with no number

- **WHEN** an outcome records "passed" with no measured value
- **THEN** the item shows as performed and uncorrelated, and no agreement is implied
