# Material Compliance Specification

## Purpose

Screening a product's declared materials against public substance lists, against the
material needs its industry declares, and against each other where they touch.

## ADDED Requirements

### Requirement: Compositions are screened against pinned substance lists

A material record SHALL be able to declare its composition as substances with CAS
numbers and mass fractions, with a source. The system SHALL screen every BOM line's
compositions against the substance lists the user has fetched, and report each hit with
the line, the substance, its concentration in the article, the threshold, and the list
version and hash.

#### Scenario: A lead-bearing brass

- **WHEN** a fitting's brass declares 2.5% lead and the RoHS Annex II list is loaded
- **THEN** the fitting's line reports a hit above the 0.1% threshold, naming the list
  version, and an exemption applies only if the user declares it with its reference

#### Scenario: No composition declared

- **WHEN** a BOM line's material declares no composition
- **THEN** its substance screen is not evaluated, naming the composition as missing

### Requirement: Restricted lists are fetched with consent, never bundled

Substance lists published under restrictive terms SHALL be fetched only on the user's
consent through the existing digest-pinned fetch, with their terms recorded. Lists that
are public law SHALL be fetchable the same way. A screen against a list older than the
one the user has cached SHALL name both versions.

#### Scenario: A list that may not be redistributed

- **WHEN** a user asks for the automotive declarable-substance list
- **THEN** the fetch asks for consent and records its terms, and the list never enters
  the repository or a package

### Requirement: Composition and recycled content export per part

For every made part and every component, the system SHALL export material composition by
mass: the material, its substances and fractions, the part mass, and the declared recycled
fraction with its source. The export SHALL roll recycled plastic content up the product
by mass.

#### Scenario: A recycled-content roll-up

- **WHEN** a product has 4.2 kg of plastic, 0.9 kg of it declared recycled
- **THEN** the roll-up reports 21% recycled plastic content, listing each contributing
  line

### Requirement: Declared material needs are screened

A product or item SHALL be able to declare material needs: body-contact category and
duration, sterilization method, vacuum exposure, flammability rating, service temperature
range. Each needs-to-attribute comparison SHALL be a card entry citing the attribute's
source. An attribute the material does not declare SHALL be not evaluated.

#### Scenario: A plastic that will not survive the autoclave

- **WHEN** an instrument handle declares steam sterilization at 134 °C and its material
  declares a 100 °C service limit
- **THEN** the entry fails, naming the material, the method and both temperatures

#### Scenario: Outgassing in vacuum

- **WHEN** a space item declares vacuum exposure and its adhesive declares 1.4% total mass
  loss
- **THEN** the entry fails against the 1.0% screen, citing the test standard and the
  value's source

### Requirement: Dissimilar metals in contact are screened for galvanic risk

For every connection between items of different metals, the system SHALL report the
pair's compatibility from a bundled table of public-release data, given the declared
environment severity, and SHALL name any declared isolation (coating, washer, sealant).
A connection with no declared environment SHALL be not evaluated.

#### Scenario: Aluminum on stainless in salt spray

- **WHEN** an aluminum bracket is bolted to a stainless plate in a declared marine
  environment with no isolation
- **THEN** the entry reports an incompatible pair, naming both materials and the
  connection, and the isolation that would clear it
