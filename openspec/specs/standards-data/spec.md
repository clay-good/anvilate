# Standards & Materials Data Specification

## Purpose

Anvilate bundles curated, provenance-tagged databases of standard component dimensions (fasteners, motors, bearings, extrusion profiles, fits) and engineering material properties. These databases are the sole source of standard dimensions and material values in the pipeline — the "retrieval, not recall" rule that eliminates the most dangerous class of hallucination.

## Requirements

### Requirement: Single source of truth for standard dimensions

All dimensions of standard components (bolt circles, thread specs, bearing envelopes, extrusion profiles, motor mount patterns) SHALL be resolved from the bundled standards database; no subsystem, including any LLM, MUST ever emit standard-component dimensions from model memory.

#### Scenario: NEMA 23 resolution

- **WHEN** any part of the pipeline needs the NEMA 23 mounting geometry
- **THEN** the bolt-square spacing, pilot-bore diameter, and face dimensions come from the standards database record `NEMA23`

#### Scenario: Coverage gap surfaces to user

- **WHEN** a needed component has no database record
- **THEN** the system asks the user for the governing dimensions or a source file instead of estimating
- **AND** the resulting user-supplied record is marked with user provenance

### Requirement: Launch coverage of common mechanical standards

The standards database SHALL cover, at launch: ISO metric fasteners (ISO 4762, 4014, 4017, 4032, 7089 families), metric thread geometry (ISO 261/724 with tap and clearance hole tables), DIN 625 ball bearings, NEMA motor frames (8, 11, 14, 17, 23, 34), common T-slot extrusion profiles (20/30/40/45 series), and dowel pins (ISO 2338).

#### Scenario: Clearance hole lookup

- **WHEN** a pattern needs the clearance hole for an M5 cap screw at normal fit
- **THEN** the database returns the standard clearance diameter with its source citation

### Requirement: Data provenance on every record

Every record in the standards and materials databases SHALL carry provenance metadata: source, publication or dataset identifier, retrieval date, and license; standard documents themselves MUST NOT be redistributed — only dimension data with citations.

#### Scenario: Provenance in evidence bundle

- **WHEN** a part using `AA-6061-T6` and `ISO4762-M5` is exported
- **THEN** the evidence bundle lists each database record used, with its source and license

### Requirement: Materials database with mechanical properties

The materials database SHALL provide, per material record: elastic modulus, Poisson ratio, density, yield strength, ultimate strength, and (where available) thermal properties and fatigue parameters — each property individually provenance-tagged with source, condition, and temper; a property without provenance MUST NOT be used in validation.

#### Scenario: Yield strength with temper

- **WHEN** FEA compares von Mises stress against yield for `AA-6061-T6`
- **THEN** the yield value used is the T6-temper value with its citation
- **AND** the report states the temper and source alongside the safety factor

#### Scenario: Missing property blocks the check

- **WHEN** a validation check requires a property the material record lacks
- **THEN** the check reports "not evaluated — property unavailable" rather than substituting an unsourced value

### Requirement: Derived fatigue parameters are labeled as estimates

Where fatigue parameters are estimated from static properties (e.g., FKM-guideline estimation from hardness or ultimate strength), the database SHALL label them as derived estimates with the estimation method named, and any check consuming them SHALL propagate that label to the report.

#### Scenario: FKM-estimated endurance limit

- **WHEN** fatigue screening runs on a material with an FKM-estimated endurance limit
- **THEN** the scorecard entry is annotated "estimated per FKM method, not test data"

### Requirement: Ingestion from open datasets with license tracking

The database build pipeline SHALL support ingesting open dimension datasets (e.g., archived BOLTS BLT tables, cq_warehouse fastener CSVs, FreeCAD FastenersWB FsData) with per-dataset license records, and the build MUST fail if any ingested dataset lacks a recorded license compatible with redistribution.

#### Scenario: Ingest with license

- **WHEN** the database build ingests an open fastener table
- **THEN** the output records the dataset version and license
- **AND** an unlicensed source aborts the build

### Requirement: Fetch-on-first-use for license-restricted datasets

Datasets that are free to download but not licensed for redistribution (e.g., publisher-hosted section or component databases) SHALL be fetched to the user's machine on first use with explicit consent and checksum verification, cached locally with fetch provenance, and MUST NOT be bundled in Anvilate releases; all lookups after the fetch SHALL work offline.

#### Scenario: Restricted dataset fetched once

- **WHEN** a spec first references a component whose data lives in a non-redistributable dataset
- **THEN** the user is asked once to approve the download from the publisher's source, the file's checksum is verified, and the dataset is cached with source, date, and license recorded

#### Scenario: Release contains no restricted data

- **WHEN** a release artifact is audited
- **THEN** it contains no non-redistributable dataset content — only the fetch recipes and checksums

### Requirement: Versioned, offline, user-extensible databases

The databases SHALL version independently of the application, work fully offline, and accept user- or team-local extension records (company standard parts, approved materials) that override or extend bundled data without forking it; extension records SHALL be distinguishable from bundled records in every report.

#### Scenario: Company part library

- **WHEN** a team adds a local record for an internal standard bracket insert
- **THEN** specs can reference it like any bundled component
- **AND** reports mark it as a team-local record

#### Scenario: Air-gapped lookup

- **WHEN** Anvilate runs air-gapped
- **THEN** all standards and materials lookups succeed with zero network calls
