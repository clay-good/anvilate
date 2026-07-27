# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Pressure equipment pack

The pressure equipment pack SHALL provide, when shipped: required-thickness and MAWP screening for ellipsoidal and torispherical formed heads and conical sections, nozzle-opening reinforcement area screening per the UG-37 area-replacement method, and bolted-flange screening per Appendix 2 (bolt loads, gasket seating and operating conditions, flange stresses) composing the existing gasket m/y factors — each check citing its ASME VIII Division 1 paragraph and edition, with allowable stresses user-supplied with provenance and never bundled.

#### Scenario: Head thickness screened

- **WHEN** a 2:1 ellipsoidal head is declared with design pressure, diameter, joint efficiency, and a user-supplied allowable stress
- **THEN** the required thickness and MAWP are reported per the cited paragraph, with pass/fail against the declared nominal thickness

#### Scenario: Nozzle opening reinforced

- **WHEN** a nozzle is declared on a shell with sizes, thicknesses, and allowables supplied
- **THEN** the UG-37 check reports required versus available reinforcement area, itemizing shell surplus, nozzle-wall contribution, and any reinforcing pad, each term traceable

#### Scenario: Flange screened to Appendix 2

- **WHEN** a bolted flange is declared with gasket factors from the existing gasket module and user-supplied allowables
- **THEN** seating and operating bolt loads and the flange stress checks report pass/fail with the Appendix 2 clause cited
