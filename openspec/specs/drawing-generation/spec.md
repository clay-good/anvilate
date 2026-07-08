# Drawing Generation Specification

## Purpose

Drawing generation produces dimensioned 2D engineering drawings — DXF and rendered PDF/SVG — from the validated part, with auto-dimensioning driven by semantic tags, tolerance callouts, and populated title blocks. Drawings are derived artifacts of the spec and code, regenerated on every change.

## Requirements

### Requirement: Projected views from the B-Rep

The system SHALL generate standard orthographic views (plus optional section and isometric views) via hidden-line-removal projection of the actual B-Rep, laid out on ISO A-series and ANSI sheet templates selected by user preference.

#### Scenario: Default three-view drawing

- **WHEN** a validated bracket is exported as a drawing
- **THEN** front, top, and side views are projected and placed on the selected template with correct scale noted

### Requirement: Tag-driven auto-dimensioning

Auto-dimensioning SHALL be driven by semantic tags: overall envelope, hole callouts with thread specifications and counts (e.g., "4× M5 ISO 4762 clearance"), critical thicknesses, and interface-pattern dimensions; every spec-constrained dimension MUST appear on the drawing.

#### Scenario: Hole callout from interface

- **WHEN** the part carries the `motor_mount_pattern` interface of 4 M5 clearance holes on a standard bolt circle
- **THEN** the drawing shows a single grouped callout with count, diameter, and pattern dimensions traceable to the standards record

#### Scenario: Constraint dimensions always present

- **WHEN** the spec constrains a wall thickness
- **THEN** that thickness is dimensioned on the drawing, not left to the reader to measure

### Requirement: Tolerance callouts

Dimensions with explicit tolerances in the spec SHALL render with their ± or limit values; dimensions without explicit tolerances SHALL fall under the drawing's stated general-tolerance note (per the tolerance-management capability), and the general-tolerance class MUST be printed in the title block.

#### Scenario: General tolerance note

- **WHEN** a drawing is generated with the default general-tolerance class
- **THEN** the title block states the ISO 2768 class applied to otherwise-untoleranced dimensions

#### Scenario: Explicit fit dimension

- **WHEN** a bore carries an explicit fit specification
- **THEN** the drawing renders the dimension with its limit deviations

### Requirement: Feature control frames where specified

Where the spec declares geometric tolerances (flatness on a mount face, position on a hole pattern), the drawing SHALL render standards-conformant feature control frames attached to the toleranced features.

#### Scenario: Position tolerance on bolt pattern

- **WHEN** the spec assigns a position tolerance to the mounting hole pattern with a datum reference
- **THEN** the drawing shows a feature control frame with the correct symbol, value, and datum letters on that pattern

### Requirement: Populated title block

The title block SHALL populate automatically from spec metadata: part name, material with temper, mass, scale, units, general-tolerance class, spec revision identifier, date, and validation status; unvalidated drawings MUST carry the unvalidated watermark.

#### Scenario: Title block traceability

- **WHEN** a drawing is regenerated after a spec change
- **THEN** the revision identifier and mass update automatically and match the evidence bundle

### Requirement: DXF and rendered output fidelity

Drawings SHALL export as DXF (readable by AutoCAD-class tools without repair) and as rendered PDF/SVG that are visually identical to the DXF content; dimension values MUST come from the model geometry, never from re-measured raster output.

#### Scenario: DXF opens in AutoCAD-class tools

- **WHEN** the exported DXF is opened in a DXF-conformant CAD tool
- **THEN** views, dimensions, and text render without errors or proxy entities

#### Scenario: Model-derived measurements

- **WHEN** any dimension is placed
- **THEN** its value is computed from the B-Rep geometry so a geometry change can never leave a stale dimension
