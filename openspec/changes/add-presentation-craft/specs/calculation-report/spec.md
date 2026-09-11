# Calculation Report Specification (delta)

## ADDED Requirements

### Requirement: The report is typeset to be read on paper

The calculation report SHALL be typeset to the presentation-craft rules for print: values
set in fixed-width figures aligned on the decimal, derivations never split across a page
break, tables repeating their headers, every verdict legible without colour, and page
furniture carrying part identity, revision, and page numbering. A reviewer's copy is
frequently paper or a PDF read at a desk, and a report that only works on a screen is a
report that fails at the moment it is being relied upon.

#### Scenario: The margin summary scans on paper

- **WHEN** the margin summary table is printed
- **THEN** its values align on the decimal and the governing check is identifiable without
  colour

#### Scenario: Pagination respects the content

- **WHEN** the document paginates
- **THEN** no derivation is split, and every continued table repeats its headers
