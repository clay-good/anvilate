# Declaration Completeness Specification (delta)

## ADDED Requirements

### Requirement: One consolidated report of what the build needs

The system SHALL collect every declaration a build required and did not receive into one
report, rather than leaving them distributed across individual not-evaluated entries. Each
item SHALL name the declaration, the dimension and units it takes, the screens it would
unblock, and where an acceptable value may come from — a standard, a database record, a
measurement, or the user's own statement. The report SHALL be produced whenever any
declaration is missing, including on builds that otherwise pass.

#### Scenario: The card and the next step arrive together

- **WHEN** a build reports eleven not-evaluated entries arising from four missing
  declarations
- **THEN** the needs report lists four items, each naming the entries it would resolve

#### Scenario: A passing build still reports its gaps

- **WHEN** every evaluated screen passes but two declarations were never supplied
- **THEN** the needs report is still produced, because a pass computed over a subset is
  not a complete answer

### Requirement: Needs are ordered by what they unblock, with ties named

The report SHALL order items by the number of screens each would unblock, and SHALL state
that number per item so the ordering is checkable rather than asserted. Items unblocking
equal numbers of screens SHALL be reported as tied rather than ranked arbitrarily. The
ordering SHALL be presented as a measure of leverage and MUST NOT be described or rendered
as a ranking of importance, risk, or severity, which it is not.

#### Scenario: The count is shown beside the order

- **WHEN** the needs report is rendered
- **THEN** each item shows the number of screens it unblocks, and the order follows those
  numbers

#### Scenario: Leverage is not severity

- **WHEN** an item unblocking one screen concerns a safety-governing check and an item
  unblocking six concerns a secondary one
- **THEN** the report orders by leverage and states explicitly that the order is not a
  ranking of importance

### Requirement: Profiles supply coherent declaration sets with their provenance intact

A profile SHALL be a named, versioned record carrying a source citation, an applicability
statement, and the set of declarations it supplies, and binding one SHALL supply those
declarations in a single action. Every value a profile supplied SHALL be marked as
profile-sourced wherever it appears — on the rendered report, in the scorecard, and in the
evidence bundle — and SHALL be individually overridable, with an override recorded as user
provenance. A profile MUST NOT supply a value outside its own declared applicability; such
a binding SHALL be refused naming the value and the applicability it exceeds.

#### Scenario: One binding, many declarations, all attributed

- **WHEN** a user binds an environment profile
- **THEN** the declarations it supplies are recorded with the profile's id, version, and
  citation, and each is individually overridable

#### Scenario: A profile value that governs a verdict is visible

- **WHEN** a profile-supplied value governs a failing check
- **THEN** the rendered result names the profile as the source of that value, so the
  reader can weigh it rather than assume the user stated it

#### Scenario: Out-of-applicability binding refused

- **WHEN** a profile whose applicability stops at one temperature range is bound to a spec
  declaring a wider range
- **THEN** the binding is refused naming the value and the range, rather than supplying a
  value outside its basis

### Requirement: Declared screening depth is distinct from a missing declaration

A spec SHALL be able to declare a screening depth, and a screen outside that depth SHALL
report "out of declared depth" — a status distinct from "not evaluated" and from every
other status. The card SHALL report the count of out-of-depth screens and the count of
not-evaluated screens separately, and the two MUST NOT render identically on any surface,
because a screen the user deliberately deferred and a screen that could not run are
different facts about the design.

#### Scenario: A concept-depth run is short and honest

- **WHEN** a spec declares concept depth
- **THEN** the card carries the screens within that depth and reports the deeper ones as
  out of declared depth with their count, rather than as failures or as gaps

#### Scenario: Deferral never becomes a pass

- **WHEN** an out-of-depth screen would have governed
- **THEN** the card does not claim completeness, and the out-of-depth count appears beside
  the verdict

#### Scenario: The two statuses stay distinguishable

- **WHEN** a card carries both out-of-depth and not-evaluated entries
- **THEN** both counts are stated and neither is rendered in the other's form

### Requirement: Raising the depth is one action that reports what it now needs

Raising a spec's declared screening depth SHALL re-run the needs collection and report
exactly which declarations the new depth requires that the previous depth did not, so
deepening a screen presents a finite next step rather than a new wall. The system SHALL
report what the raise newly unblocked as well as what it newly requires, so the cost and
the benefit of going deeper are visible together.

#### Scenario: Going deeper names its price and its return

- **WHEN** a user raises depth from concept to detailed
- **THEN** the report names the declarations newly required and the screens newly
  available

#### Scenario: Depth does not silently change a verdict's basis

- **WHEN** raising the depth changes a verdict
- **THEN** the change is attributable to the newly run screens, which are named
