# Margin Ledger Specification (delta)

## ADDED Requirements

### Requirement: Every applied conservatism is a ledger entry

The system SHALL record, as a typed ledger entry, every factor applied anywhere in a build
that makes a result more conservative than the unfactored physics: safety and design
factors, resistance and load factors, statistical material bases, contingency and growth
allowances, deratings, and rounding that moves a value in the safe direction. Each entry
SHALL carry its numeric value, its kind, the quantity it bears on, its origin — the check,
module, spec declaration, or database record that introduced it — and the authority that
justifies it. A factor MUST NOT be applied without an entry.

#### Scenario: A factor cannot be applied invisibly

- **WHEN** a screen divides a capacity by a design factor
- **THEN** a ledger entry exists naming the factor's value, kind, origin, and authority,
  and the entry is retrievable from the result

#### Scenario: Rounding in the safe direction is conservatism too

- **WHEN** a required thickness is snapped up to the next stock size
- **THEN** the resulting conservatism is recorded as a rounding entry with the nominal and
  the delivered value

#### Scenario: Entries survive into the bundle

- **WHEN** an evidence bundle is produced
- **THEN** it carries the full ledger, not a summary, so a reviewer can audit each entry

### Requirement: An unattributable factor is refused

A ledger entry SHALL be refused when its origin or its authority is blank, and the check
attempting to apply it SHALL report "not evaluated" naming the factor. An authority SHALL
name a source that a reader can go and read — a standard clause with its edition, a
declared company practice with its identifier, a cited reference, or an explicit
user election recorded as such. A factor nobody can attribute is indistinguishable from an
arbitrary one, and the system MUST NOT carry it silently.

#### Scenario: Blank authority stops the check

- **WHEN** a factor is supplied with no authority
- **THEN** the check reports "not evaluated" naming the factor, rather than applying it

#### Scenario: "Engineering judgment" is an election, recorded as one

- **WHEN** a user elects a factor above the code minimum on their own judgment
- **THEN** the entry is accepted with kind user-elected and the authority recorded as the
  user's election, so the report distinguishes it from a code requirement

### Requirement: Kinds are distinguished and never rendered alike

Every ledger entry SHALL carry a kind from a closed enumeration — code-required,
user-elected, statistical-basis, contingency-or-growth, rounding, and derating — and every
consumer of the ledger SHALL handle each kind explicitly. A consumer MUST NOT file an
unrecognized kind under a default arm, and adding a kind SHALL fail any consumer that has
not been updated to handle it. A code-required factor and a user-elected one MUST NOT
render identically on any surface.

#### Scenario: The report distinguishes obligation from choice

- **WHEN** a report renders a design factor required by a cited clause and another the
  user elected
- **THEN** the two are visibly distinguished with their kinds and authorities stated

#### Scenario: A new kind breaks its consumers loudly

- **WHEN** a kind is added to the enumeration
- **THEN** every consumer that does not handle it fails, rather than silently treating it
  as one of the existing kinds

### Requirement: The cumulative factor per quantity is computed and shown

For each checked quantity the system SHALL compute the cumulative conservatism — the
product of the factors bearing on it — and report it beside the verdict with the
multiplication itemized. The cumulative factor SHALL be reported whether or not the check
passes, because an over-margined pass is the finding this capability exists to surface.

#### Scenario: Five defensible factors, one visible product

- **WHEN** a bracket's bending check carries a code factor, an elected factor, a
  statistical allowable basis, a load contingency, and a thickness rounding
- **THEN** the result reports each entry and their product, so the engineer sees the total
  conservatism in one number

#### Scenario: A passing check still reports its margin stack

- **WHEN** a check passes comfortably
- **THEN** the cumulative factor is reported, rather than omitted because nothing failed

### Requirement: The physics-limited result is reported beside the delivered one

The system SHALL report, alongside the delivered result, the result the same screen would
have produced with code-required entries only — the physics-limited result — together
with the difference attributable to elected conservatism. This comparison SHALL be
reported as information, and the system MUST NOT alter, relax, or recommend relaxing any
declared factor on the basis of it.

#### Scenario: The cost of caution is a number

- **WHEN** a mass-driven part is screened
- **THEN** the report states the delivered utilization and the physics-limited
  utilization, and names the elected entries that account for the difference

#### Scenario: The tool informs and does not decide

- **WHEN** the physics-limited comparison shows large elected conservatism
- **THEN** the report states it without recommending removal, and the delivered verdict is
  unchanged

### Requirement: Duplicate conservatism is named, not multiplied in silence

The system SHALL detect when two or more entries of the same kind bear on the same
quantity from different origins, and SHALL report them together as possible double
counting with every origin named and their combined effect stated. Detection SHALL be by
the quantity an entry bears on and its kind, not by matching the entries' names or
descriptions, so that two differently worded factors on the same quantity are still
caught. The system MUST NOT resolve the duplication itself.

#### Scenario: Two contingencies on one load

- **WHEN** a load carries a contingency declared in the spec and another applied by a
  module
- **THEN** the report names both origins, states their combined effect, and flags possible
  double counting

#### Scenario: Detection does not depend on wording

- **WHEN** two entries on the same quantity use different labels for the same kind of
  conservatism
- **THEN** they are still reported together, because detection keys on the quantity and
  kind rather than on the text

#### Scenario: The engineer resolves it

- **WHEN** a possible double count is reported
- **THEN** neither entry is removed or reduced automatically, and the verdict continues to
  reflect both

### Requirement: The dominant entry is identified, with ties reported

For each checked quantity the system SHALL name the dominant ledger entry — the one whose
removal would most reduce the cumulative factor — and SHALL report a tie as a tie rather
than selecting arbitrarily among equal entries. Where the ledger for a quantity is empty,
the result SHALL say that the quantity carries no recorded conservatism, which is itself a
finding rather than an absence to be rendered as blank.

#### Scenario: The biggest lever is named

- **WHEN** a quantity carries several entries
- **THEN** the dominant one is named with its value and kind

#### Scenario: Equal entries tie rather than being ranked

- **WHEN** two entries on a quantity have equal value
- **THEN** both are reported as tied dominant entries

#### Scenario: An unfactored quantity says so

- **WHEN** a checked quantity carries no ledger entries at all
- **THEN** the result states that no conservatism was applied to it, so an unprotected
  quantity is distinguishable from one nobody recorded
