# Release Package Specification

## Purpose

The files a product is handed over as, in the forms the engineer's CAD, PLM, ERP, shops
and purchasing already accept, gated on the product's card.

## ADDED Requirements

### Requirement: A release is gated, a draft is marked

A release export SHALL be refused while the product's card fails, while any item is a
placeholder, while any component is unsourced, or while any part number is provisional,
and the refusal SHALL name every blocking item by path. A draft export SHALL be available
at any time and SHALL be marked draft in every file's metadata and on every drawing.

#### Scenario: A placeholder blocks release

- **WHEN** a release is requested for a product whose gearbox is still a placeholder
- **THEN** it is refused naming `reducer/gearbox`, and a draft export succeeds marked
  draft

### Requirement: An indented BOM in the columns PLM and ERP imports expect

Every export SHALL write an indented BOM as CSV and XLSX with, per line: level, find
number, parent part number, part number, revision, description, quantity per parent, unit
of measure, material, finish, make/buy, process, manufacturer, manufacturer part number,
supplier part numbers, unit mass, and the relative path of the line's files. Find numbers
SHALL be the numbers on the assembly drawing's balloons.

#### Scenario: The BOM imports without retyping

- **WHEN** an engineer imports the CSV into a PLM that requires level and parent columns
- **THEN** every line carries both, and the tree it rebuilds matches the product's

### Requirement: Column profiles map the BOM onto the user's template

A user SHALL be able to supply a column profile: a document mapping BOM fields to their
template's column names, order, and value forms (level as an integer or dotted path, make
and buy spellings). Exports SHALL write a BOM per profile supplied. A profile naming a
field the BOM does not carry SHALL be refused naming the field.

#### Scenario: Dotted levels for an ERP

- **WHEN** a profile asks for levels as `1.2.1` and make/buy as `M`/`B`
- **THEN** the profiled BOM uses those forms and the default BOM is unchanged

### Requirement: A buy list sums purchased items across the tree

Every export SHALL write a buy list: one line per purchased designation or manufacturer
part number with its total quantity across all instances and variants exported, its
manufacturer, supplier part numbers, and the paths that use it.

#### Scenario: Fasteners summed across modules

- **WHEN** four drive modules each use eight M5 x 16 cap screws and the frame uses twelve
- **THEN** the buy list has one M5 x 16 line with a quantity of 44 and lists both uses

### Requirement: Manufactured parts are routed by process

Every export SHALL place each manufactured part's files in a folder for its declared
process. Profile-cut parts SHALL get one DXF each at 1:1 in a stated unit, closed contours
on one cut layer, bend lines on their own layer, and no text, with a cut list of part
number, material, thickness and quantity. Printed parts SHALL be gathered on one 3MF plate
with one object per part and its quantity. Machined parts SHALL get their STEP file and
drawing.

#### Scenario: A sheet-metal shop's folder

- **WHEN** a product with three laser-cut parts is exported
- **THEN** the laser folder holds three single-part DXFs and a cut list, and nothing
  else

### Requirement: Driving parameters are exported in design-table shape

Every export SHALL write a CSV per item definition listing its driving parameters by
name, value and unit, one column per variant exported, so an engineer can link or rebuild
the item in native CAD.

#### Scenario: Two variants side by side

- **WHEN** a stage with base and long variants is exported
- **THEN** the carriage plate's parameter table has a column for each variant

### Requirement: A manifest lists every file and what gated it

Every export SHALL write a manifest naming the product, its revision, whether it is a
release or a draft, the card verdict and evidence bundle it was gated on, and every file
with its relative path, role and SHA-256. A file listed whose content no longer matches
its hash SHALL be reported by `anvilate verify`.

#### Scenario: A file edited after export

- **WHEN** a DXF in the package is changed after export
- **THEN** verifying the package reports that file as altered, by path and both hashes
