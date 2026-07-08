# Cost Estimation Specification

## Purpose

Cost estimation gives the user an order-of-magnitude manufacturing cost alongside the physics verdict, so trade-offs (mass vs cost vs safety factor) are visible during design, not after quoting. Estimates are screening-level, locally computed, configurable to the user's shop rates, and never require a cloud quoting service.

## Requirements

### Requirement: Additive manufacturing cost from slicing

For additive processes, the system SHALL estimate cost by headless slicing of the exported mesh — obtaining print time and material mass — combined with a user-editable rate configuration (machine rate, material cost per kg, setup fee); the slicer runs as an isolated subprocess.

#### Scenario: FDM cost estimate

- **WHEN** a part with an FDM manufacturing process completes validation
- **THEN** the report shows estimated print time, material mass, and cost computed from the active rate configuration

#### Scenario: Rates are local configuration

- **WHEN** the user edits the machine hourly rate
- **THEN** cost estimates update without any network call

### Requirement: Machining cost from a feature-based parametric model

For CNC processes, the system SHALL estimate cost with a documented feature-based parametric model — material stock cost, setup count, and per-feature machining time from removal volumes and feature classes — with every model coefficient user-editable and the model's methodology and sources cited in the report.

#### Scenario: Bracket machining estimate

- **WHEN** a CNC-milled bracket completes validation
- **THEN** the report shows an itemized estimate (stock, setups, roughing, finishing, drilling/tapping) with a stated uncertainty band

#### Scenario: No black-box numbers

- **WHEN** any cost estimate is displayed
- **THEN** the user can expand it to see the formula inputs and coefficients that produced it

### Requirement: Cost as an optional constraint

The Spec IR SHALL accept an optional cost budget constraint; when present, the estimated cost becomes a scorecard check and participates in repair-loop trade-offs and Pareto presentations.

#### Scenario: Cost in the Pareto set

- **WHEN** mass, safety factor, and cost constraints cannot all be met
- **THEN** the Pareto presentation includes cost as a dimension (e.g., "meets cost at SF 1.8" vs "exceeds budget 12% at SF 2.0")

### Requirement: Estimates are labeled screening-grade

Every cost figure SHALL be labeled as a screening estimate with its uncertainty band; the system MUST NOT present estimates as quotes.

#### Scenario: Label on report

- **WHEN** a cost estimate appears in the UI or evidence bundle
- **THEN** it carries the "screening estimate" label and band, never a bare precise-looking number
