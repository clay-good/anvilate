# Sustainability Screening Specification (delta)

## ADDED Requirements

### Requirement: Cradle-to-gate estimate from mass, material, and process

The system SHALL compute a per-part cradle-to-gate greenhouse-gas estimate as the sum of
material contribution (part mass × material factor), primary-process contribution, and a
material-loss contribution reflecting the difference between stock and finished mass
where the process implies one. Each contribution SHALL be reported separately with the
factor used, so the user can see which term dominates.

#### Scenario: Contributions itemized

- **WHEN** a machined steel bracket's estimate is computed
- **THEN** the result reports material, process, and material-loss contributions
  separately with their factors, and their total

#### Scenario: Mass reduction moves the number

- **WHEN** a revision reduces part mass
- **THEN** the estimate falls correspondingly and the change is reportable alongside the
  mass and margin changes

### Requirement: Every factor carries provenance and an uncertainty band

A carbon factor SHALL carry its source dataset identity, dataset version or publication
date, geographic scope, and the standard's declared module scope; generic factors SHALL
carry an uncertainty band reflecting their spread against product-specific data. A
factor without provenance MUST NOT be used, and a material with no available factor
SHALL report "not evaluated," never a zero or an assumed default.

#### Scenario: Unknown material is honest

- **WHEN** a part's material has no carbon factor in the bundled tables and no imported
  EPD
- **THEN** the estimate reports "not evaluated" naming the material — never zero

#### Scenario: Band travels with the number

- **WHEN** a generic factor is used
- **THEN** the reported estimate includes its uncertainty band and the band's basis

### Requirement: Product-specific EPD import overrides generic factors

The system SHALL import environmental product declarations in the openEPD schema from
local files, allow a user to bind an imported declaration to a material in their spec,
and use it in preference to the generic factor; the binding SHALL be recorded in
provenance with the declaration's identity, and imported declarations MUST NOT be
redistributed in the repository.

#### Scenario: Real EPD replaces the estimate

- **WHEN** a user imports an openEPD document for their supplier's aluminum and binds it
- **THEN** subsequent estimates use it, the result names the declaration as the source,
  and the generic-factor uncertainty band is replaced by the declaration's own stated
  values

#### Scenario: Provenance survives export

- **WHEN** an evidence bundle is produced after an EPD binding
- **THEN** the bundle records which factor came from which declaration

### Requirement: Screening framing and licensing discipline

Every result SHALL be labeled a screening-grade, cradle-to-gate, partial figure in the
governing standard's language, SHALL name the modules covered, and MUST NOT be presented
as a product carbon footprint, an EPD, a verified declaration, or a regulatory
disclosure. Bundled factor data SHALL be limited to sources whose licenses permit
redistribution; sources that prohibit commercial use, caching, or redistribution MUST NOT
be bundled, and any integration with such a service SHALL be optional, user-credentialed,
off by default, and subject to the air-gapped-mode prohibition on network calls.

#### Scenario: Label is non-negotiable

- **WHEN** an estimate is rendered anywhere in the product or a report
- **THEN** it carries the screening and partial-scope labels and the modules covered

#### Scenario: Restricted source stays out

- **WHEN** a data source's license prohibits redistribution or commercial use
- **THEN** its data is not bundled, and any optional integration requires the user's own
  credentials and explicit opt-in

#### Scenario: Air-gapped estimate still works

- **WHEN** the system runs in air-gapped mode
- **THEN** estimates compute from bundled and imported data with zero network calls

### Requirement: Carbon may serve as a trade-off objective

The estimate SHALL be usable as an optional objective or constraint alongside mass, cost,
and utilization, and MUST NOT alter any physics verdict; a design MUST NOT be reported as
improved on carbon grounds if any check regressed to a failing state.

#### Scenario: Carbon in the trade-off

- **WHEN** alternatives are compared
- **THEN** each carries its estimate with its band, and a lower-carbon alternative that
  fails a check is reported as failing, not as an improvement
