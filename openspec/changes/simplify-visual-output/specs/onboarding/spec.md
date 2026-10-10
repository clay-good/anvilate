# Onboarding Specification (delta)

## MODIFIED Requirements

### Requirement: One-command install per platform

Anvilate SHALL install with a single documented command per supported channel (pip, Docker/Podman, conda-forge), and installation MUST NOT require the user to manually install, locate, or configure solvers, meshers, or the geometry kernel — bundled or auto-fetched components resolve without user action.

#### Scenario: pip install just works

- **WHEN** a user runs the documented pip install command on a supported platform and registers the MCP server with their agent
- **THEN** a sample part checks, builds and renders through the agent without any manual solver setup

#### Scenario: Container parity

- **WHEN** a user runs the official container image
- **THEN** the same golden path works with no host installation beyond the container runtime

### Requirement: Sample part gallery

Anvilate SHALL bundle at least 5 runnable sample specs spanning the supported personas (e.g., motor bracket, enclosure, structural base plate, lifting lug, fixture plate), each checkable and buildable in one command or one request to the agent with zero network calls; the catalog an agent can list SHALL name them.

#### Scenario: First part in one request

- **WHEN** a new user asks their agent to build a bundled sample
- **THEN** the agent checks it, builds it and shows its picture and files from the bundled spec, demonstrating the full describe → validate → export loop without the user writing a spec

## REMOVED Requirements

### Requirement: Optional guided first build

**Reason**: It described a walkthrough of the workbench's three panes, and there is no workbench.
**Migration**: The first-run guide is the README's three steps and the agent guide's worked session.
