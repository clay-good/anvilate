# Input Ingestion Specification

## Purpose

Input ingestion turns engineering source documents — mating STEP files, DXF drawings, datasheet PDFs, and (roadmap) raster drawings — into confirmed, typed interface data for the Design Spec. The governing rule: extracted dimensions are drafts until the user confirms them; no extracted value silently becomes load-bearing.

## Requirements

### Requirement: Mating STEP import with deterministic feature detection

The system SHALL import STEP files of mating parts and deterministically detect interface candidates — planar mating faces, holes and their patterns (coaxial cylinder grouping, bolt-circle fitting), bosses and pilot bores — without LLM involvement; STEP mate/constraint semantics MUST NOT be relied upon, as real-world exports do not carry them.

#### Scenario: Motor face detection

- **WHEN** the user drops the STEP of a gearbox housing
- **THEN** detected hole patterns and mating planes are listed as interface candidates with their measured geometry

#### Scenario: Geometric inference only

- **WHEN** an imported assembly STEP lacks constraint data (the normal case)
- **THEN** interfaces are still detected from geometry alone

### Requirement: DXF dimension reading

The system SHALL read dimension entities from imported DXF drawings — including their measured values and text overrides — and offer them as typed dimension inputs, flagging any dimension whose text override disagrees with its measured geometry.

#### Scenario: Mounting plate DXF

- **WHEN** the user drops a DXF of a mounting plate with dimensioned hole spacing
- **THEN** the hole-spacing dimensions are extracted with values and offered as interface data

#### Scenario: Override disagreement flagged

- **WHEN** a DXF dimension's text override differs from the geometry it measures
- **THEN** the conflict is surfaced to the user for resolution rather than either value being silently trusted

### Requirement: Datasheet table extraction with confirmation

The system SHALL extract candidate interface dimensions from datasheet PDF tables locally, presenting each extracted value with its source location for explicit per-value user confirmation; unconfirmed extracted values MUST NOT enter the Spec IR as load-bearing dimensions.

#### Scenario: Motor datasheet

- **WHEN** the user drops a stepper datasheet PDF
- **THEN** extracted mounting dimensions appear as a confirmation checklist, each linked to its page location
- **AND** only confirmed values enter the spec, tagged with document provenance

#### Scenario: Known part short-circuits extraction

- **WHEN** the datasheet's component matches a standards-database record
- **THEN** the database record is offered first, with extraction as fallback

### Requirement: Vision-based drawing extraction is confirmation-gated and provenance-tagged

Raster drawing and drawing-figure extraction (dimension callouts, GD&T), when shipped, SHALL run locally, present per-value confidence, require the same per-value confirmation flow, and record extractor identity and version in provenance; zero-shot general-purpose vision models MUST NOT be the sole extractor for dimensional data.

#### Scenario: Scanned drawing ingestion

- **WHEN** the user drops a scanned part drawing
- **THEN** extracted dimensions render as overlays on the drawing for visual verification and individual confirmation

### Requirement: Binary inputs never reach cloud models by default

Imported CAD payloads and documents SHALL be processed locally; no binary input content may be transmitted to a cloud LLM unless the user explicitly enables it per source.

#### Scenario: Cloud backend with local files

- **WHEN** a user with a cloud LLM configured drops a proprietary STEP file
- **THEN** the file is processed by local deterministic code and its geometry is never uploaded unless the user opts in for that file
