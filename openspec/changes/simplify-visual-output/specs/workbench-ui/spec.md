# Workbench UI Specification (delta)

The whole capability is retired. Anvilate has no interface of its own: the user's agent is
the interface, a rendered image and files on disk are the output, and the user's CAD is
the viewer.

## REMOVED Requirements

### Requirement: Three-pane core screen

**Reason**: Anvilate is driven through the user's agent over MCP and ships no web app.
**Migration**: The golden path is three tool calls (check, build and render, export),
specified under `headless-automation`.

### Requirement: One primary input

**Reason**: The agent's chat is the one input.
**Migration**: Files the user points the agent at are read through `add-agent-context-intake`.

### Requirement: Live viewport with engineering views

**Reason**: Rotating, sectioning and probing are what the user's CAD does from the STEP
file. Replicating them is the product Anvilate is not.
**Migration**: Rendered views and the dimensioned view under `drawing-generation`; STEP
export for everything else.

### Requirement: Visible, reversible assumptions

**Reason**: There is no spec card to tap.
**Migration**: Every assumption is a value with provenance in the spec; the agent states
them and the scorecard prints them.

### Requirement: Parameter sliders bound to code

**Reason**: No interface to hold sliders.
**Migration**: The agent edits the spec parameter and rebuilds; bounds come from the
drawable-parts catalog.

### Requirement: Click-to-reference geometry

**Reason**: No viewport to click.
**Migration**: Faces and features are named by semantic tag, listed by the catalog and
labelled in the dimensioned view.

### Requirement: Iteration timeline

**Reason**: No interface to scrub.
**Migration**: Specs are files under version control; `anvilate diff` compares two.

### Requirement: Failure as a first-class citizen

**Reason**: The requirement was about a UI surface that will not exist.
**Migration**: A failing or unevaluated result leads every surface with what decides it,
as the part sheet's verdict block and the tool results already do.

### Requirement: Report pane mirrors the scorecard

**Reason**: No pane.
**Migration**: The scorecard is returned by the tools and printed on the part sheet.

### Requirement: Local, loginless, telemetry-opt-in

**Reason**: No server is started at all. The properties it protected hold more strongly.
**Migration**: `headless-automation`, "The MCP server is local software, not a hosted
service", and `sandbox-security`, "No default telemetry".

### Requirement: Keyboard-first with CLI parity

**Reason**: No UI to have parity with.
**Migration**: `headless-automation`, "CLI parity with the MCP surface".
