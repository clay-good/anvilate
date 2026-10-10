# Benchmarking Specification (delta)

## ADDED Requirements

### Requirement: Agent-driving is measured on every supported client

The agent-driving task corpus SHALL run on each supported client (Claude Code and Codex)
through that client's real MCP integration, and the published results SHALL state, per
client and client version: tasks completed, tool calls per task, calls refused and why,
whether the agent saw the rendered image, whether the result was reported as a screen and
not a certification, and wall-clock time per call. The corpus SHALL include each
documented journey, at least one task per drawable part family, one combination, and one
task that starts from a folder of context files. A release SHALL NOT ship with a lower
completion rate on either client than the previous release without a recorded decision.

#### Scenario: A Codex-only failure is caught

- **WHEN** a change makes a tool's result exceed Codex's output budget while Claude Code
  still succeeds
- **THEN** the Codex run fails that task and the release is blocked

#### Scenario: Results name the client version

- **WHEN** the published results are read
- **THEN** each row names the client, its version and the date it was run
