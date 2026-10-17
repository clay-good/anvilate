# Component Library Specification

## Purpose

Bought parts as typed records with cited dimensions, interfaces and ratings, so a product
is checked where it depends on something nobody here draws.

## ADDED Requirements

### Requirement: A purchased component is a typed, cited record

A purchased component SHALL be a record holding: manufacturer and manufacturer part
number, or a standard designation; optional supplier part numbers; an envelope solid; the
interfaces it offers; its ratings with units; and the provenance of every value. A value
without provenance SHALL be refused naming the field.

#### Scenario: A motor record from its datasheet

- **WHEN** a user writes a record for a stepper motor, citing the datasheet page for its
  flange pattern, shaft diameter and holding torque
- **THEN** the record validates, and each value carries its page reference to the card

#### Scenario: A value with no source

- **WHEN** a record states a bearing's dynamic load rating with no provenance
- **THEN** the record is refused naming the rating

### Requirement: Common families resolve from bundled tables

The library SHALL ship family generators that build component records from bundled
dimension tables with provenance: motor frames by size, deep-groove ball bearings by
designation, profile rail guides by size class, rigid and jaw couplings by bore, and fans
by frame. A designation the tables lack SHALL be refused with the nearest designations,
and nothing SHALL be drawn from a guess.

#### Scenario: A frame size that does not exist

- **WHEN** an agent asks for a NEMA 21 motor
- **THEN** the request is refused, listing the frame sizes the tables carry

#### Scenario: A bearing by designation

- **WHEN** a product places a 6204 bearing
- **THEN** its bore, outside diameter, width and ratings come from the bundled table with
  their source

### Requirement: Vendor models are used by reference

A component record SHALL be able to name a vendor STEP file inside the context folder by
relative path and SHA-256. The system SHALL measure that file for the envelope and SHALL
NOT copy it into bundled data, examples or published packages. A referenced file whose
hash no longer matches SHALL make the record's geometry not evaluated until the hash is
updated.

#### Scenario: The vendor changed the file

- **WHEN** a motor's vendor STEP is replaced with a different file under the same name
- **THEN** checks reading its envelope report not evaluated, naming the file and both
  hashes

### Requirement: Ratings are compared with what the product asks

Each component family SHALL declare which product quantity each of its ratings is
compared with, and each comparison SHALL be a cited card entry: bearing rating life
against required life, motor torque against required torque, guide stroke and load
against the product's, gas spring force against required force. A comparison whose
quantity the product does not supply SHALL be not evaluated, naming the quantity.

#### Scenario: A bearing that will not last

- **WHEN** the shaft's bearing load and speed give an L10 life of 4,000 hours against a
  declared 20,000
- **THEN** the bearing-life entry fails, citing the life equation and both values

#### Scenario: No load declared

- **WHEN** a product places a bearing and declares no load on its shaft
- **THEN** the bearing-life entry is not evaluated, naming the load it needs

### Requirement: A component carries what a buyer needs

Every component SHALL carry its manufacturer, manufacturer part number or standard
designation, unit of measure, and any supplier part numbers. A component with neither a
manufacturer part number nor a standard designation SHALL be marked unsourced on the
parts list and SHALL block a released export.

#### Scenario: An unsourced gas spring

- **WHEN** a product uses a gas spring record with no part number
- **THEN** the parts list marks it unsourced, and the release export is refused naming it
