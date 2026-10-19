# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Checks that compute a life publish it as a typed life quantity

Every public check SHALL publish a typed life quantity when its result is a life, a rate of
consumption, or a retention over time: at minimum bearing rating life, fatigue life and
duty-cycle damage, wear allowance consumption, corrosion allowance consumption, elastomer
compression set over life, and creep or relaxation retention. The quantity SHALL be in
hours, cycles, distance, or time at a declared temperature, with its basis and the
reliability the method states where it states one. CI SHALL report the checks of these
classes that publish no life quantity.

#### Scenario: Rating life is a life quantity

- **WHEN** the bearing rating-life check runs
- **THEN** its result carries a typed life in hours with the method's stated reliability,
  consumable by the service-life plan without parsing the entry's text

#### Scenario: A life check that forgot

- **WHEN** a new wear check merges without publishing its allowance-consumption time
- **THEN** CI reports it by name
