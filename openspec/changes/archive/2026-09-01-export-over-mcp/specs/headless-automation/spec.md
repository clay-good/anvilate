# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: The evidence bundle is producible over the tool surface

The MCP tool surface SHALL be able to produce the evidence bundle for a screening result it
is given, because that artifact needs no built geometry: the CLI produces it from a spec file
today by screening the spec and rolling the card up, and the tool has that card through its
subject handle. Artifacts that do need built geometry — a QIF results file, a DXF — SHALL
continue to be refused with that reason, and the refusal SHALL name what the operation waits
on rather than reporting the request as malformed.

The produced bundle SHALL be **returned and not written**. The tool SHALL NOT accept a
destination path, and SHALL NOT create a file. Where a bundle ends up is the client's
decision, made with the client's own filesystem: an MCP server writing to a path a caller
names is a capability, and this surface does not grant one.

The export gate applies, and it applies as `artifact-export` states it — to the CAD artifacts
whose export is enabled only when the acceptance checks pass. The evidence bundle is the
evidence, including the evidence that a part did not pass, so it SHALL be produced whatever
the verdict and SHALL carry the screening disclaimer and its own rolled-up status in every
case. This surface grants no override, and no artifact leaves it unwatermarked.

#### Scenario: A bundle is produced from a scorecard handle

- **WHEN** a client calls the export tool with a handle to a scorecard and asks for the
  evidence bundle
- **THEN** it receives the bundle document as structured content, identical to the one the
  CLI produces for the same spec, together with the digest of the bundle's own canonical JSON

#### Scenario: An artifact that needs geometry is still refused

- **WHEN** the same client asks the same tool for a QIF results file or a DXF
- **THEN** the call is refused as unavailable, naming built geometry as what it waits on,
  rather than answered with a file drawn from nothing

#### Scenario: A card that does not pass is still exported, and says so

- **WHEN** the scorecard behind the handle does not pass
- **THEN** the bundle is returned, carrying the screening disclaimer and a status that is not
  a pass, because a document reporting that a part failed is the artifact a caller most needs
  and the one a refusal would withhold

#### Scenario: No path is written anywhere

- **WHEN** any export call is served
- **THEN** no file is created, and the tool's published input schema offers no property that
  could name one
