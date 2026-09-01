# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: The evidence bundle is producible over the tool surface

The MCP tool surface SHALL be able to produce the evidence bundle for a spec it is given,
because that artifact needs no built geometry: the CLI produces it from a spec file today by
screening the spec and rolling the card up, and the tool has the same spec through its
subject handle. Artifacts that do need built geometry — a QIF results file, a DXF — SHALL
continue to be refused with that reason.

Where the produced bundle goes is a separate decision from whether it can be produced, and
this requirement does not settle it: writing to a caller-named path, writing under a declared
root, and returning the document rather than writing it are all conforming, and the export
gate applies to each — a card that does not pass is refused rather than watermarked and
written, and the tool surface grants no override.

#### Scenario: A bundle is produced from a spec handle

- **WHEN** a client calls the export tool with a handle to a compiled spec and asks for the
  evidence bundle
- **THEN** it receives the bundle produced from that spec, identical to the one the CLI
  produces for the same document

#### Scenario: An artifact that needs geometry is still refused

- **WHEN** the same client asks the same tool for a QIF results file or a DXF
- **THEN** the call is refused naming built geometry as what it waits on, rather than
  answered with a file drawn from nothing

#### Scenario: A failing card is not exported

- **WHEN** the spec behind the handle screens to a card that does not pass
- **THEN** the export is refused, and no artifact is written or returned, because the tool
  surface inherits the export gate and grants no override
