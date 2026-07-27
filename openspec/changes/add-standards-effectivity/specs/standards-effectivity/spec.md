# Standards Effectivity Specification (delta)

## ADDED Requirements

### Requirement: Every citation carries an edition

A clause citation SHALL identify the standard, its edition or publication year, and the
clause — a citation without an edition SHALL be rejected at registration time, not at
render time. The edition SHALL travel with the check result into the scorecard, the
calculation report, and the evidence bundle.

#### Scenario: Editionless citation refused

- **WHEN** a check is registered citing a clause with no edition
- **THEN** registration fails naming the check and the incomplete citation

#### Scenario: Edition reaches the artifact

- **WHEN** a validated part is exported
- **THEN** every check's standard, edition, and clause appear in the evidence bundle

### Requirement: Design basis pins editions per spec

A spec SHALL be able to declare a design basis: a set of standard-to-edition pins. When a
basis is declared, checks SHALL evaluate against the pinned edition or, if that edition
is unsupported for that check, report "not evaluated" naming the standard and edition —
never silently substituting a different edition.

#### Scenario: Pin honored

- **WHEN** a spec pins AISC 360-16 and a member check supporting both -16 and -22 runs
- **THEN** the check evaluates under -16 and the result names that edition

#### Scenario: Unsupported pin is honest

- **WHEN** a spec pins an edition a check does not implement
- **THEN** the check reports "not evaluated" naming the standard and edition, and the
  scorecard cannot show a pass for it

### Requirement: Mixed editions require an explicit waiver

The system SHALL block an evidence bundle whose checks resolve to different editions of
the same standard, unless the spec records an explicit mixed-edition waiver naming the
standard and the editions involved; the waiver SHALL appear in the bundle.

#### Scenario: Accidental mix caught

- **WHEN** two checks in one run cite different editions of the same standard with no
  waiver declared
- **THEN** the bundle is refused with both citations named

#### Scenario: Deliberate mix is recorded

- **WHEN** the user records a mixed-edition waiver for a documented reason
- **THEN** the bundle is produced and the waiver, its reason, and the editions appear in
  it

### Requirement: Superseded editions are usable but labeled

Evaluating against an edition the system knows to be superseded SHALL succeed and SHALL
carry a superseded-edition label naming the newer edition and the date the supersession
was recorded; the label MUST NOT be presented as a failure, since legacy work legitimately
runs on the edition in force at the time.

#### Scenario: Legacy basis flagged, not blocked

- **WHEN** a spec pins a superseded edition
- **THEN** results evaluate normally and every rendering carries the superseded label
  naming the successor edition

### Requirement: Edition differences are reported, not hidden

Where a check's governing provision differs between supported editions, the system SHALL
record that difference and SHALL be able to evaluate the check under each supported
edition and report both results side by side with the differing clauses named. A
difference registry entry SHALL cite its source; where no difference is recorded for a
check, the system SHALL state that no difference is registered rather than implying
equivalence.

#### Scenario: Edition delta surfaced

- **WHEN** a user requests an edition comparison for a check whose provision changed
  between two supported editions
- **THEN** both results, both clause references, and the registry citation are reported

#### Scenario: Absence of data stated plainly

- **WHEN** an edition comparison is requested for a check with no registered difference
- **THEN** the response states that no difference is registered — never that the editions
  are equivalent

### Requirement: Jurisdiction mapping is advisory and dated

If the system ships a jurisdiction-to-edition mapping, it SHALL be offline, carry an
"as of" date and source per entry, present results as advisory suggestions for the user
to confirm, and warn when the data is older than a declared staleness threshold. The
mapping MUST NOT set a design basis automatically and MUST NOT be presented as a
determination of legal code compliance.

#### Scenario: Suggestion, not selection

- **WHEN** a user names a jurisdiction
- **THEN** the system suggests the referenced editions with per-entry sources and "as of"
  dates, and the design basis remains unset until the user confirms

#### Scenario: Stale data warns

- **WHEN** the mapping entry predates the staleness threshold
- **THEN** the suggestion is accompanied by a staleness warning naming the entry date
