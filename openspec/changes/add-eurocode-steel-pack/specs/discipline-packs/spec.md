# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Eurocode 3 steel pack

The system SHALL provide, when shipped, an optional Eurocode 3 steel pack with member
screens to EN 1993-1-1 — cross-section classification by the cited width-to-thickness
limits, cross-section resistance in tension, compression, bending and shear with their
interactions, flexural buckling by the cited buckling curves, lateral-torsional buckling,
and combined bending and axial compression by an interaction method the document
declares — each citing its clause and the edition it implements. Partial factors and
every other nationally determined parameter SHALL be typed inputs: the standard's
recommended values ship with their clause, and a national annex value is user-supplied
with its citation and overrides them, marked as user-supplied wherever it governs. The
pack MUST NOT select a national annex by inference.

#### Scenario: Governing limit state under a declared basis

- **WHEN** an IPE beam is screened under a design basis declaring EN 1993-1-1:2005+A1:2014
  with the recommended partial factors
- **THEN** classification, cross-section bending resistance and lateral-torsional buckling
  are each reported with their clause and edition, the governing limit state is named, and
  the card states that the recommended γM values were used

#### Scenario: An annex value overrides, visibly

- **WHEN** the user supplies γM1 from a national annex with its citation
- **THEN** every buckling verdict uses it, names it as user-supplied, and the margin change
  against the recommended value is retrievable

#### Scenario: No annex is guessed

- **WHEN** a document declares a Eurocode design basis and no national annex
- **THEN** the recommended values apply and the card says so, rather than the pack choosing
  an annex from the project's location or language

### Requirement: Eurocode 3 joints

The Eurocode 3 steel pack SHALL screen bolted connections to EN 1993-1-8 by their declared
category — bearing type and slip-resistant, in shear and in tension — covering bolt shear,
bearing, tension, punching shear and combined shear and tension, and SHALL screen fillet
welds by either the directional method or the simplified method as the document declares,
each check citing its clause and edition. Slip resistance SHALL require a declared slip
factor with its source; a slip-resistant category with no slip factor SHALL be not
evaluated naming it. A weld check with no declared method SHALL be not evaluated naming
the two methods.

#### Scenario: A category C connection without a slip factor

- **WHEN** a bolted splice is declared slip-resistant at the ultimate limit state and no
  slip factor is supplied
- **THEN** the slip check is not evaluated naming the slip factor and its accepted sources,
  and the bearing and shear checks still run and cite their clauses

#### Scenario: Weld method is a declaration

- **WHEN** a fillet weld is declared with the directional method
- **THEN** the weld check reports the normal and shear stress components on the throat, the
  cited correlation factor for the declared steel grade, and the clause

### Requirement: Both Eurocode generations are evaluable through the design basis

The Eurocode 3 steel pack SHALL implement the first-generation editions (EN 1993-1-1:2005
with its amendment, EN 1993-1-8:2005) and the second-generation editions (EN 1993-1-1:2022,
EN 1993-1-8:2024) as distinct, pinned editions selected by the document's design basis.
Where a governing provision differs between the two generations and the difference is
registered, the pack SHALL be able to evaluate under both and report the difference; where
a provision is implemented for one edition only, a document pinning the other SHALL
receive not evaluated naming the edition implemented, never a verdict computed under an
edition the document did not declare.

#### Scenario: Two generations on one desk

- **WHEN** the same beam is screened under design bases pinning EN 1993-1-1:2005 and
  EN 1993-1-1:2022 and the governing provision is registered as different
- **THEN** each card cites its own edition, and the edition-difference report names the
  provision and both results

#### Scenario: An edition not yet anchored

- **WHEN** a joint check is implemented for EN 1993-1-8:2005 only and the document pins
  EN 1993-1-8:2024
- **THEN** the entry is not evaluated naming the edition implemented and the edition
  requested, and the card does not pass

### Requirement: European profiles resolve from open geometry

The Eurocode 3 steel pack SHALL resolve European profile designations (IPE, HE, UPN and
UPE, equal and unequal angles, and hollow sections) from open profile geometry with
section properties computed at build time, under the license-clean section library rule;
a designation absent from the open data SHALL be refused asking for the governing
dimensions or a local data file, with user provenance recorded when supplied.

#### Scenario: An IPE resolves offline

- **WHEN** a document names IPE 300 and the open profile data is installed
- **THEN** the profile resolves with no network call, its properties are computed from the
  stored geometry, and the data source and version are recorded on the card

#### Scenario: A profile the data does not hold

- **WHEN** a document names a profile absent from the open data
- **THEN** the pack refuses naming the designation and the dimensions it needs, and never
  estimates a section from a similar name
