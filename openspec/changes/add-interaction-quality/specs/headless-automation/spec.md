# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: The CLI follows established command-line conventions

The CLI SHALL follow the conventions engineers already expect: a machine-readable output
flag on every command, progress on the diagnostic stream, colour suppressed when not
writing to a terminal or when suppression is requested, width-aware wrapping, documented
and stable exit codes, shell completion for the supported shells, and runnable examples in
every help text. A command that produces output SHALL be usable in a pipeline without
flags, and the tool MUST NOT require a terminal to function.

#### Scenario: The tool composes

- **WHEN** a validation command's machine-readable output is piped into another tool
- **THEN** the stream parses cleanly and the progress was not part of it

#### Scenario: Completion and examples ship with the tool

- **WHEN** a user installs Anvilate and requests help for any command
- **THEN** shell completion is available and the help carries a runnable example

#### Scenario: No terminal required

- **WHEN** a command runs in a CI job with no terminal attached
- **THEN** it completes normally with no interactive prompts and no control sequences in
  its output
