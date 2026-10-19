# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Walking-working surfaces pack

The system SHALL provide, when shipped, an optional walking-working surfaces pack with
guardrail system, stair system, fixed ladder and platform-edge elements, each screened
to the regulation the document declares as its regime. Under the US general industry
regime (29 CFR 1910 Subpart D) the pack SHALL apply the regulation's loads as load cases —
the top-rail force applied downward and outward at the worst point along the rail, the
intermediate-member force, and the stair load as the greater of the factored live load
and the concentrated load at any point — run the existing member and connection screens
on them, and check the regulation's geometry rules (rail heights, rung spacing and
clearances, stair angle, riser, tread, width, headroom and landing depth) as cited
pass/fail entries. Every entry SHALL cite its paragraph and the date the regulation text
was read. The pack MUST NOT apply one regime's numbers to a document declaring another.

#### Scenario: A guardrail post at the worst point

- **WHEN** a guardrail run of tube posts at 8 ft spacing is screened under the general
  industry regime
- **THEN** the top-rail force is applied outward at the point that maximizes the post
  base moment, the post, the rail and the base connection each report a cited verdict,
  and the top-rail deflection under the downward case is checked against the minimum
  height, with every entry citing its paragraph

#### Scenario: A ship stair too steep for a standard stair

- **WHEN** a stair declared as a standard stair is laid out at 55 degrees
- **THEN** the angle check fails citing the standard-stair range, and the refusal names the
  ship-stair element whose range it falls in

#### Scenario: A regime is not a guess

- **WHEN** a document declares the construction regime
- **THEN** no general industry number is applied, and any clause not yet anchored for that
  regime is not evaluated naming it

### Requirement: Fall-protection triggers are reported, not assumed away

The pack SHALL report, for every declared platform edge and fixed ladder, whether the
regulation's height trigger for fall protection or a ladder safety system is reached
from the declared heights, naming the paragraph; an edge or ladder with no declared
height SHALL be not evaluated naming it.

#### Scenario: A ladder over the trigger

- **WHEN** a fixed ladder is declared at 26 ft above the lower level under the general
  industry regime
- **THEN** the card reports that a ladder safety or fall arrest system is required citing
  the paragraph, and the ladder's rung and clearance checks still run

### Requirement: Grating and decking spans use the user's load table

Grating, plank and decking spans SHALL be screened against a load table the user supplies
with its manufacturer and citation, carrying user provenance; the pack MUST NOT bundle a
manufacturer's table or estimate a capacity from the bar size.

#### Scenario: No table, no verdict

- **WHEN** a platform declares a grating span and supplies no load table
- **THEN** the span check is not evaluated naming the table it needs, and the card does not
  pass
