# Onboarding Specification (delta)

## ADDED Requirements

### Requirement: Installing and connecting takes two commands

Anvilate SHALL be installable from the public package index by name, with the geometry
kernel and exchange formats in the default install, and the MCP server SHALL be startable
by a single command that needs no prior install step (a package runner invocation). The
documented setup for each supported client SHALL be one command or one configuration
entry, verified in CI by registering the server with the real client and listing its
tools. The install SHALL work with no compiler and no system packages on the supported
platforms, and the environment self-check SHALL say in plain words what is missing when
it does not.

#### Scenario: From nothing to a first part

- **WHEN** a new user runs the documented install and the documented one-line client setup
- **THEN** their agent lists Anvilate's tools and builds a sample part with no further step

#### Scenario: The setup line is tested, not remembered

- **WHEN** the client's registration syntax changes
- **THEN** the CI check that runs the documented line fails
