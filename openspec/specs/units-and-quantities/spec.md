# Units & Quantities Specification

## Purpose

Engineers work in the units their discipline and code demand: a US structural engineer designs in kips, ksi, and inches; a European mechanical engineer in newtons, MPa, and millimeters. Units are a correctness surface, not a display preference — a report in the wrong unit system is rejected by any reviewer, and a silently mis-assumed unit is a safety defect. This capability makes SI and US customary units first-class end to end.

## Requirements

### Requirement: Per-project unit system

Every Design Spec SHALL declare a unit system (`SI` or `US`), defaulted from a stored user preference and recorded in the spec with provenance; all UI values, reports, scorecards, and evidence bundles for that spec MUST render in the declared system.

#### Scenario: US structural project

- **WHEN** a spec declares `units: US` and validation reports a bearing stress
- **THEN** the report shows the value in ksi with the threshold in ksi, not an SI value the user must convert

#### Scenario: Preference sets the default

- **WHEN** a user whose preference is SI compiles a new spec without stating units
- **THEN** the spec records `units: SI` tagged as defaulted from user preference

### Requirement: Mixed-unit input is accepted everywhere

Quantity input — in prose, spec files, and UI fields — SHALL accept explicit units from either system regardless of the project unit system (e.g., "75 kip", "3 mm", "50 ksi"), storing the value canonically while preserving the value as entered for display and diffing.

#### Scenario: Imperial prose in one line

- **WHEN** the user writes "base plate for a W12x26 column, 50 ksi steel, 75 kip axial load"
- **THEN** each quantity compiles into the spec with its stated unit, correctly converted internally, and the spec card echoes the values as entered

#### Scenario: Cross-system value in an SI project

- **WHEN** a user working in an SI project types a bolt torque in lbf·ft
- **THEN** the value is accepted, converted, and displayed in the project system with the entered value preserved in provenance

### Requirement: Derived engineering units are first-class

The unit layer SHALL support the derived quantities engineering codes are written in — force (N, kN, lbf, kip), stress (MPa, psi, ksi), moment (N·m, kN·m, lbf·ft, kip·ft, kip·in), distributed load (N/m, kN/m, plf, klf), area moment of inertia (mm⁴, in⁴), and section modulus (mm³, in³) — with dimensional consistency checked on every stored quantity.

#### Scenario: Dimensional error rejected

- **WHEN** a spec field expecting a stress receives a quantity with force dimensions
- **THEN** validation rejects the spec naming the field, the received dimension, and the expected dimension

### Requirement: Unitless physical quantities are never assumed

A numeric input for a physical quantity without a unit SHALL trigger a clarification with the likely unit options for the project system — the system MUST NOT silently assume a unit for a load-bearing value.

#### Scenario: Bare number challenged

- **WHEN** the user writes "design for a load of 75"
- **THEN** the compiler asks one question offering the plausible units (e.g., N, kg, lbf, kip) rather than guessing

### Requirement: Code-conventional precision in reports

Rendered values SHALL use the precision conventional for the quantity and unit system (e.g., kips to one decimal, stresses in ksi to one decimal, millimeter dimensions to two decimals), with full-precision values available in machine-readable outputs; conversions MUST NOT introduce visible drift across regenerations.

#### Scenario: Readable report

- **WHEN** a base-plate report renders a computed bearing stress
- **THEN** it shows a conventionally rounded value (e.g., "1.2 ksi"), and the JSON scorecard carries the full-precision number

#### Scenario: Stable round-trip

- **WHEN** the same spec is rebuilt with no changes
- **THEN** every displayed value is character-identical to the previous build — no conversion jitter

### Requirement: Drawings and sheets follow the unit system

Drawing dimension text SHALL render in the project unit system, the default sheet template SHALL follow it (ISO A-series for SI, ANSI for US), and dual-unit dimensioning SHALL be available as an option with the secondary unit bracketed per drafting convention.

#### Scenario: US project drawing

- **WHEN** a drawing is generated for a `units: US` spec
- **THEN** dimensions render in inches on an ANSI sheet, and the title block states the unit system

#### Scenario: Dual dimensioning

- **WHEN** the user enables dual dimensioning on an SI project
- **THEN** each dimension shows the millimeter value with the inch value bracketed beneath it per the drawing standard
