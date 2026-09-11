# Tolerance Management Specification (delta)

## ADDED Requirements

### Requirement: Optical tolerance indications render from the one tolerance model

Optical element tolerances SHALL be declared — surface form, centring, material
imperfection classes, surface imperfection, and birefringence — in the same semantic
tolerance model that carries geometric tolerances, and rendered to the ISO 10110 indication form on
drawings as a fourth consumer alongside drawing feature control frames, STEP semantic PMI,
and QIF characteristics. Consumers MUST render from the model rather than duplicating
tolerance data, so an optical tolerance change propagates to every surface without drift.
Where a user declares an alternative surface-imperfection convention, the rendering SHALL
follow the declared convention and name it — the system MUST NOT convert between
conventions silently, because the conventions are not equivalent.

#### Scenario: One declaration, every surface

- **WHEN** a surface form tolerance on an optical element is tightened in the spec
- **THEN** the regenerated drawing indication, the exported PMI, and the quality
  characteristic all carry the new value from the same model

#### Scenario: Convention is named, never converted silently

- **WHEN** a user declares a surface-imperfection tolerance in a convention other than the
  default
- **THEN** the drawing renders it in the declared convention and names that convention,
  and no automatic cross-convention conversion is performed

#### Scenario: Optical tolerance on a non-optical feature is rejected

- **WHEN** an optical surface tolerance is attached to a feature not tagged as an optical
  surface
- **THEN** validation rejects it naming the characteristic and the feature, before any
  consumer renders it
