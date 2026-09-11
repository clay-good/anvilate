# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: Typed keepout declaration

A Design Spec SHALL be able to declare keepout envelopes as typed, schema-validated
elements: a semantic tag, a generating rule with its parameters, a declared clearance
margin, a stated reason the volume is protected, and the owner that declared it — the user
or a named module. A keepout whose generating rule would produce a degenerate body — zero
or negative volume, inverted extents — SHALL be rejected naming the offending parameter,
because an empty keepout is a constraint that can never be violated and would report a
vacuous pass forever.

#### Scenario: Keepout round-trips with its reason

- **WHEN** a spec declaring a connector mating envelope is serialized and reloaded
- **THEN** the tag, generating rule, margin, reason, and owner round-trip unchanged

#### Scenario: Degenerate keepout refused

- **WHEN** a keepout is declared with a zero height or an inverted extent
- **THEN** the spec is rejected naming the parameter, rather than accepting a volume
  nothing can intrude upon

#### Scenario: Reason is required

- **WHEN** a keepout is declared with a blank reason
- **THEN** the spec is rejected, because a protected volume nobody can explain cannot be
  weighed against a change that wants the space

### Requirement: A keepout is anchored to something that can move

A keepout declaration SHALL name the semantic tag or datum its position is defined
against, and SHALL move with that anchor when the anchor moves. An unanchored keepout
SHALL be refused, because a protected volume fixed in absolute space silently stops
protecting the right region the moment a design change moves the feature it exists to
protect — and the check keeps passing.

#### Scenario: The envelope follows its feature

- **WHEN** a design change moves the tagged face a keepout is anchored to
- **THEN** the keepout moves with it and the intrusion check re-evaluates against the new
  position

#### Scenario: Unanchored keepout refused

- **WHEN** a keepout is declared with no anchor
- **THEN** the spec is rejected naming the keepout

#### Scenario: A broken anchor is not a silent pass

- **WHEN** a keepout's anchor tag no longer exists after a change
- **THEN** the keepout reports "not evaluated" naming the missing anchor, and the card
  does not pass
