# evidence-attestation Specification (delta)

## ADDED Requirements

### Requirement: The disclosure names how each confirmation was obtained

The AI-involvement disclosure SHALL record, for every person-only confirmation the bundle
rests on, the channel it came through and the client name and version where the channel
was an elicitation, and SHALL state when a bundle rests on no confirmation that any
channel can attest to a person. A bundle MUST NOT describe a value as confirmed by a
person when its confirmation channel cannot attest to one.

#### Scenario: Disclosure per channel

- **WHEN** a bundle rests on one value confirmed by confirmation file and one answered
  through an elicitation
- **THEN** the disclosure lists both with their channels, and names the client and version
  for the elicitation
