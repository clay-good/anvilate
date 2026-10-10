# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: The tool set is shaped by the user's journeys

The MCP tool set SHALL be the smallest set of workflow-level tools that completes the
documented journeys: find out what Anvilate can check and draw; check a described part;
build it and see it; measure it; export it; read context files; build a combination. Each
journey SHALL complete in a stated maximum number of tool calls, with no call that exists
only to prepare the next. Each tool SHALL be named for what the user is asking for, share
one prefix-free naming style, state when to use it in its first sentence, declare truthful
read-only, destructive and open-world hints, and take one consistent name for the same
thing everywhere (one word for a spec, one for a built part, one for a card). A tool that
can never return a result in a shipped configuration MUST NOT be in the catalog.

#### Scenario: Check, build and show in three calls

- **WHEN** an agent is asked to design a catalog part from a plain description
- **THEN** it reaches a checked part, a picture and a STEP file on disk in at most three
  tool calls after its first reading of the catalog

#### Scenario: No tool that cannot answer

- **WHEN** the catalog is listed in a default install
- **THEN** every tool in it can return a real result for some valid input

### Requirement: The surface fits each client's limits, by test

For each supported client, a gate SHALL hold: every tool description and the server
instructions within that client's truncation limit, with the most important guidance
first; every tool's input schema within the client's documented schema constraints; every
result within the declared size budget; and every golden-path call within the declared
time limit. The limits SHALL be recorded per client and version in one table the gates
read, with the source and date each was taken from.

#### Scenario: A description that would be cut is caught

- **WHEN** a tool description is edited past the shortest client limit
- **THEN** the build fails, naming the tool and the limit

### Requirement: A refusal tells the agent how to succeed

Every refusal an MCP tool or CLI command returns SHALL name the field or argument at
fault, say what is wrong in one sentence, give one valid example or the allowed values,
and stay under a declared length. A suggested correction MUST NOT be a value less
conservative than the one refused, and a near-match suggestion SHALL be offered only when
it is unambiguous. Refusals SHALL be collected and reviewed as a set, so the same mistake
gets the same words on every surface.

#### Scenario: A wrong unit is repaired in one step

- **WHEN** an agent supplies a thickness in kilograms
- **THEN** the refusal names the field, says a length is required, and shows a valid value

#### Scenario: A refusal never loosens a requirement

- **WHEN** a safety factor below the allowed minimum is refused
- **THEN** no suggested value is lower than the minimum
