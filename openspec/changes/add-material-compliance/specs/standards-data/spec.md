# Standards Data Specification (delta)

## ADDED Requirements

### Requirement: Polymer and elastomer records carry temperature and time

The materials database SHALL include records for common engineering plastics and
elastomers. Each property SHALL be stated at its test temperature, and time-dependent
properties (creep modulus, stress relaxation) at their stated durations, each with a
source. A check that needs a property at a temperature or time the record does not carry
SHALL be not evaluated rather than extrapolate.

#### Scenario: A snap-fit at 85 °C

- **WHEN** a snap-fit in glass-filled nylon is checked at a declared 85 °C and the record
  carries allowable strain only at 23 °C
- **THEN** the snap-fit strain check is not evaluated, naming the temperature it needs

### Requirement: Composite lamina records carry their basis

The materials database SHALL accept lamina records with in-plane stiffnesses, strengths
in tension, compression and shear, ply thickness, and the basis of each strength (A, B,
mean, or user-declared). A laminate check SHALL report the basis of the strengths it used.

#### Scenario: Mean strengths are named

- **WHEN** a laminate is screened with lamina strengths declared as mean values
- **THEN** every laminate entry states that its strengths are mean values, not
  design allowables
