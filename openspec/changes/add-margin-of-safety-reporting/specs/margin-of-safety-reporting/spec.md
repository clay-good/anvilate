# Margin-of-Safety Reporting Specification

## Purpose

Margins of safety computed and reported the way aerospace and other regulated programs
review them: limit and ultimate loads kept apart, factors from a named set, allowables
with their basis, and one governing row per check across every load case.

## ADDED Requirements

### Requirement: Every load says whether it is limit or ultimate

A load used in a margin report SHALL be tagged limit or ultimate. Factors of safety SHALL
apply to limit loads, and an ultimate load SHALL NOT be multiplied by an ultimate factor
again. An untagged load SHALL be refused from a margin report, naming the load.

#### Scenario: An ultimate load is not factored twice

- **WHEN** a fitting load is declared as 15 kN ultimate under a set with an ultimate
  factor of 1.5
- **THEN** the ultimate margin uses 15 kN, and the factor column shows the load was
  already ultimate

### Requirement: Factor sets are named, cited, and bound per product

A margin report SHALL be computed under a named factor set: yield and ultimate factors,
special factors (fitting, casting, bearing) and their stacking rule, and the allowable
basis each structural class requires. Bundled sets SHALL contain only values read from
public-domain documents, each with its clause. Users SHALL be able to declare their own
set with a source.

#### Scenario: A protoflight metallic part

- **WHEN** a bracket is reported under the NASA-STD-5001B protoflight metallic set
- **THEN** yield and ultimate margins use factors of 1.25 and 1.4, each citing its table

#### Scenario: A company set

- **WHEN** a user binds their company's factor set with its document number as source
- **THEN** every margin row names that set and source

### Requirement: Margins are computed for yield and ultimate with every factor shown

For each check in a margin report, the system SHALL compute MS = allowable / (applied ×
FS × special factors) − 1 for yield and for ultimate, and pass at MS ≥ 0. Each factor
SHALL appear in its own column, and the quantity (force, stress, strain) SHALL be stated.

#### Scenario: A fitting factor in its own column

- **WHEN** a lug is reported under a set requiring a 1.15 fitting factor
- **THEN** the row shows FS, the fitting factor and MS separately, and MS reflects both

### Requirement: The allowable basis must meet the set's rule

Each allowable SHALL state its basis (A, B, S, typical or user-declared) and source. Where
the bound set requires a basis for a structural class, a check using a weaker basis SHALL
be not evaluated, naming the basis required. The user SHALL declare the load-path
redundancy that decides the class.

#### Scenario: A typical value on primary structure

- **WHEN** a single-load-path fitting's ultimate check uses a typical yield strength
  under a set requiring A-basis
- **THEN** the margin is not evaluated, naming A-basis as required and the value's
  basis

### Requirement: Verification approach selects the factors

An item SHALL declare whether it is qualified by test or by analysis alone. Where the
bound set prescribes different factors for analysis-only qualification, those factors
SHALL apply. Where the set excludes a material class from analysis-only qualification,
the item's margins SHALL be refused, naming the exclusion and its clause.

#### Scenario: A composite panel with no test

- **WHEN** a composite panel declares analysis-only qualification under a set that
  excludes composites from it
- **THEN** its margins are refused, citing the clause, and the verification plan gains
  the test the set requires

### Requirement: Each check reports its governing load case

Every check in a margin report SHALL be evaluated over every load case that reaches it,
and the report SHALL show the governing case's margin, the case identity, the number of
cases evaluated, and every case within a stated tolerance of the minimum. A case that
could not be evaluated SHALL be counted and named, never dropped.

#### Scenario: Four hundred cases, one row

- **WHEN** a fitting's lug check runs over 400 imported load cases
- **THEN** the row shows the minimum margin, its case identity, "400 evaluated", and any
  cases within the tie tolerance

### Requirement: The margin table is the review artifact

Every margin report SHALL write a margin table as CSV, XLSX and a report section. Each row
holds the item path, the failure mode, the method and its citation, the governing case,
the applied load, the allowable with basis and source, each factor, and MS. Rows SHALL be
sorted by margin. The lowest margin per subsystem SHALL be summarized.

#### Scenario: A design-review summary

- **WHEN** a product's margin table is generated
- **THEN** it opens with each subsystem's lowest margin and its row, followed by every row
  in ascending margin
