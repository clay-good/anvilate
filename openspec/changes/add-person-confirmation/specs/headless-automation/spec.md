# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: Confirmations that must be a person's cannot be tool arguments

The following SHALL be person-only confirmations: confirming a draft value an agent read
from a picture, document or sketch; exporting past a failing gate; recording a review or
accepting a check failure as an exception; and consenting to a dataset download. No MCP
tool input SHALL carry a field that supplies one, and a request that attempts to supply
one in its arguments SHALL be refused naming the confirmation and the channel that can
give it. CI SHALL hold the tool catalog to this rule.

#### Scenario: The agent cannot confirm its own reading

- **WHEN** an agent writes a spec value it read from a sketch and sets a confirmation on
  it in the tool call
- **THEN** the call is refused naming the value, stating that confirmation is the person's,
  and naming the channel that records it

### Requirement: The server asks the person through elicitation when the client can

When the connected client advertises the elicitation capability, the server SHALL request
each person-only confirmation through an elicitation in form mode that shows the value or
action, its source, and what confirming it means, and SHALL treat accept as confirmation
and decline or cancel as no confirmation, with the tool result naming the outcome. The
server MUST NOT infer the capability from the client's name or version; it SHALL read it
from the initialization exchange.

#### Scenario: The form reaches the person

- **WHEN** a build rests on an unconfirmed draft value and the client advertises
  elicitation
- **THEN** the server elicits the confirmation showing the value and its source, and on
  accept the value is confirmed with the channel recorded as elicitation through the named
  client and version

#### Scenario: Declined is not confirmed

- **WHEN** the person declines the elicitation
- **THEN** the value stays a draft, the build result says so, and the export gate holds

### Requirement: A client that cannot elicit is told the one step that confirms

A tool needing a person-only confirmation SHALL, when the client does not advertise
elicitation, refuse naming the shell command that records it and the confirmation-file form the
person can write in the output folder (the value, its digest, the person and the date).
The server SHALL read confirmation files from the output folder and SHALL offer no tool
that writes one.

#### Scenario: Refusal with the remedy

- **WHEN** an export past a failing gate is requested from a client with no elicitation
- **THEN** the call is refused naming the shell command and the file form, and no file is
  written
