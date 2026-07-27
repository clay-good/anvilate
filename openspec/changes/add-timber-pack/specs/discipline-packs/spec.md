# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Timber pack

The timber pack SHALL provide, when shipped: the NDS adjustment-factor chain computed as a typed, itemized product (load duration, wet service, temperature, beam stability, size, flat use, incising, repetitive member, and column stability factors as applicable), and member screens for bending, shear, compression with column stability, bearing, and combined bending plus axial loading — each check citing its NDS section and edition; reference design values SHALL be user-supplied with provenance (the NDS Supplement's values are never bundled), and every applied adjustment factor SHALL be individually visible in the result with its governing condition stated.

#### Scenario: Factor chain is itemized, never a lump

- **WHEN** a bending screen runs on a member with wet service and a snow-governed load duration declared
- **THEN** the result lists each applied factor with its value and triggering condition, the adjusted design value, and the demand comparison, with sections cited

#### Scenario: Reference values are user-supplied

- **WHEN** a user declares a sawn-lumber member without supplying reference design values
- **THEN** the screen reports not evaluated naming the missing values, and accepts them as user-provenance inputs when supplied

#### Scenario: Column stability computed, not assumed

- **WHEN** a compression member is screened with slenderness requiring the column stability factor
- **THEN** the factor is computed per the cited section from the member's declared geometry and modulus, and the screen fails members exceeding the slenderness limit rather than extrapolating
