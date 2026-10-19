# Input Ingestion Specification (delta)

## ADDED Requirements

### Requirement: A confirmation records the person and the channel it came through

Every confirmation of a draft value SHALL record the person named, the date, and the
channel: an elicitation answered through a named client and version, a shell command run
by the person, or a confirmation file in the output folder. A confirmation given through
an elicitation SHALL be reported as answered through the client, never as proof of who
answered, and every report that renders a confirmed value SHALL be able to show its
channel.

#### Scenario: Two channels, two wordings

- **WHEN** one value was confirmed by a shell command and another through an elicitation
- **THEN** the report shows the first as confirmed by the named person at the command line
  and the second as answered through the named client, and neither is rendered as the other
