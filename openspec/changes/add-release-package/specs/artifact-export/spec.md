# Artifact Export Specification (delta)

## ADDED Requirements

### Requirement: A product STEP keeps its tree, names and properties

A product SHALL export as one STEP AP242 file holding its hierarchy, with each product
named by its part number and each instance by a unique, non-empty, ASCII-safe name from
its path. Each part SHALL be one solid, with its color on the part, and its part
number, revision, material, mass and make/buy as user-defined attributes, plus validation
properties. No empty product SHALL be written.

#### Scenario: The tree survives import

- **WHEN** the exported linear stage is opened in a target CAD system
- **THEN** the drive modules appear as sub-assemblies, every component is named by part
  number, and no generic or duplicate names appear

### Requirement: Per-part STEP files keep stable names

Beside the assembly, every made part SHALL be written as its own STEP file named
`<part number>_<revision>.step`. The name SHALL depend only on part number and revision,
so a regenerated part replaces the previous file in the user's CAD at the same name. An
external-reference assembly SHALL be available on request and SHALL NOT be the default.

#### Scenario: Replace in place

- **WHEN** a part is regenerated at the same revision with changed geometry
- **THEN** its file name is unchanged, so the engineer's assembly referencing it updates
  on reload
