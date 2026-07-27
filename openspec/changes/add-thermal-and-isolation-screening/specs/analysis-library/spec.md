# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Thermal screening set

The library SHALL provide cited closed-form thermal screening: series/parallel thermal resistance networks (conduction, contact, convection, spreading), fin efficiency and fin-array heatsink sizing, natural- and forced-convection correlations with their validity ranges declared and enforced, and junction- or surface-temperature margin checks against user-declared limits; every correlation SHALL cite its source (Incropera-class heat transfer references or handbook data), and an input outside a correlation's declared validity range SHALL report not evaluated with the violated range named — never a silently extrapolated coefficient.

#### Scenario: Heatsink margin screened

- **WHEN** a user declares a heat source, an ambient temperature, a finned heatsink geometry, and a junction-temperature limit
- **THEN** the screen composes the resistance network, reports the predicted junction temperature against the limit with the margin, and cites each correlation used

#### Scenario: Out-of-range correlation refuses

- **WHEN** a natural-convection correlation receives a Rayleigh number outside its cited validity range
- **THEN** the check reports not evaluated naming the correlation, its range, and the computed value, rather than extrapolating

### Requirement: Vibration isolation and shock screening set

The library SHALL provide cited closed-form isolation and shock screening: transmissibility as a function of frequency ratio and damping with an isolation-effectiveness margin check, isolator selection screening composing the existing static-deflection inverse, and base-excitation half-sine shock response screening (peak response versus pulse duration and system frequency) against user-declared fragility limits; each check SHALL cite its source and follow the two-sided reporting pattern where amplification regions are flagged, not just insufficient isolation.

#### Scenario: Isolator actually isolates

- **WHEN** a user declares a machine mass, excitation frequency, and target transmissibility, and selects an isolator stiffness
- **THEN** the screen reports the frequency ratio, transmissibility, and margin against the target, citing the source, and fails isolators operating in the amplification region with that condition named

#### Scenario: Shock screening against fragility

- **WHEN** a half-sine shock input (peak, duration) and an equipment fragility limit are declared
- **THEN** the screen reports the predicted peak response against the fragility limit with the governing regime (impulsive, quasi-static, or resonant amplification) identified and cited
