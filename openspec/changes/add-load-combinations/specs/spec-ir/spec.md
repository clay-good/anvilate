# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: Typed load combinations

The Spec IR SHALL allow load cases to carry a load-nature classification (at minimum
dead, live, roof live, snow, wind, seismic, thermal, fluid/other) and SHALL allow a spec
to declare a combination set: named combinations, each a factored sum over declared load
cases. A combination set MAY be generated from a named code basis — at minimum ASCE 7-22
strength (LRFD) and allowable-stress (ASD) combinations, with seismic system parameters
(redundancy, overstrength, vertical component) as typed user inputs — or authored fully
custom; generated sets SHALL cite the code clause per combination and record the
generator inputs. A combination referencing an undeclared load case or a case with no
nature classification where the basis requires one SHALL be rejected naming the gap.

#### Scenario: Generated LRFD set

- **WHEN** a spec declares dead, live, and wind cases and requests ASCE 7-22 LRFD
  combinations
- **THEN** the standard combinations over those natures are generated with per-combination
  clause citations, including both maximum and counteracting (0.9D) forms, and appear in
  the spec as ordinary typed data the user can inspect and edit

#### Scenario: Custom combination is first-class

- **WHEN** a user authors a custom combination 1.0D + 1.5L_test for a proof condition
- **THEN** it is stored, cited as user-defined, and evaluated identically to generated
  combinations

#### Scenario: Unclassified case rejected

- **WHEN** generation from a code basis is requested but a declared load case has no
  nature classification
- **THEN** generation is rejected naming the case — natures are never guessed from case
  names
