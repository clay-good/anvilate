# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: Products go through the workflow tools, answered as a tree

A product SHALL go through the same workflow-level MCP tools and CLI commands a part and
a combination use, with no tool added per product concept. A product build SHALL return a
bounded summary tree: each node's path, part number, verdict and finding count, and the
governing finding at each failing node. Any node's full card SHALL be retrievable by its
path, and anything a response omits SHALL be stated with the path to request it.

#### Scenario: An agent drills into a failure

- **WHEN** a 60-item product build fails
- **THEN** the agent receives a summary naming the failing paths, and reads the full card
  of `stage/drive[3]/motor_mount` alone in one further call

#### Scenario: The CLI matches the tool

- **WHEN** `anvilate check stage.product.yaml` runs at the shell
- **THEN** it prints the same tree and verdicts the MCP tool returns

### Requirement: Worked products an agent can adapt

The library SHALL ship worked products, each a short document over catalog parts,
combinations and purchased components, that an agent can copy and change rather than
compose from nothing: a single-axis linear stage, a two-stage gear reducer, an electronics
enclosure with a board, a fan and a lid, and a welded frame on casters. Every worked
product SHALL build, check and export in CI.

#### Scenario: An agent starts from a worked product

- **WHEN** an agent is asked for a belt-driven linear axis
- **THEN** it can start from the linear-stage product and change the stroke, the motor
  and the carriage, rather than compose the tree from nothing
