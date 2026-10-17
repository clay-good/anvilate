# Input Ingestion Specification (delta)

## ADDED Requirements

### Requirement: An existing STEP assembly is read as a reference item

The system SHALL read a STEP assembly in the context folder and report its tree: each
product's name, each instance's name and placement, and each solid's envelope, in the
file's unit and in millimeters. A product SHALL be able to place that assembly as a
reference item, mate to its measured faces and holes, and check interference and clearance
against it. A reference item SHALL NOT appear in manufactured outputs and SHALL appear on
the BOM only as a reference line.

#### Scenario: A new guard on an existing machine

- **WHEN** an agent places the machine's STEP assembly as a reference and designs a guard
  mated to its frame
- **THEN** the guard is checked for clearance against every solid in the machine, and the
  release package contains the guard alone

#### Scenario: Duplicate names in the source

- **WHEN** the assembly file carries two instances with the same name
- **THEN** both are reported with distinct paths, and the duplication is named
