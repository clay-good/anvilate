# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Process piping pack

The process piping pack SHALL provide, when shipped: pressure-design wall-thickness screening for straight pipe (ASME B31.3 §304.1.2 including mill tolerance and corrosion allowance), branch-connection reinforcement area screening, miter-bend pressure screening, and displacement-stress-range screening against the computed allowable range — each check citing its B31.3 paragraph and edition; allowable stresses SHALL be user-supplied with provenance (the code's stress tables are never bundled), while standard pipe dimensions (B36.10M/B36.19M schedules) resolve from the bundled standards database with citations.

#### Scenario: Wall thickness with user-supplied allowable

- **WHEN** a user requests a wall-thickness screen for NPS 4 Schedule 40 pipe at a stated design pressure and temperature, supplying the allowable stress for their material at that temperature
- **THEN** the pack resolves the schedule dimensions from the standards database, computes required thickness per the cited paragraph including mill tolerance and corrosion allowance, and reports pass/fail with the allowable marked user-supplied

#### Scenario: Missing allowable never guessed

- **WHEN** a piping check runs without an allowable stress supplied
- **THEN** the check reports not evaluated with the required input named, rather than substituting a remembered or estimated value

#### Scenario: Branch reinforcement screened

- **WHEN** a branch connection is declared with run and branch sizes, thicknesses, and the user-supplied allowables
- **THEN** the reinforcement-area check reports required versus available area with each term traceable and the paragraph cited
