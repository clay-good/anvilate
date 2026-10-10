# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: A render is something the agent can see

A tool that renders a part SHALL return the image as PNG in the tool result's content with
a short text summary beside it (what is shown, the view, the size, where the file was
written), and MUST NOT return structured content in the same result, because the target
clients forward only the structured content to the model when both are present. Structured
facts about the same render SHALL be available from a separate call. For each target
client, a recorded check SHALL show that the model received the image, and that check
SHALL be repeated when a client's major version changes.

#### Scenario: The model sees the bracket

- **WHEN** an agent in Claude Code or Codex renders a built part and is asked what it shows
- **THEN** it describes the part's shape and visible features from the image itself

#### Scenario: Image and structured content are never paired

- **WHEN** the tool catalog is inspected
- **THEN** no tool that returns an image declares an output schema or returns structured
  content with it

### Requirement: Results are written where the engineer can open them

The MCP server SHALL take an output folder when it starts (defaulting to a named folder
under the directory it was started in) and SHALL write there every artifact a tool
produces: rendered images, STEP, 3MF and DXF files, part sheets, reports and bundles. A
tool result SHALL name each file's path, size and SHA-256 and MUST NOT carry a CAD file's
contents through the model. Files SHALL be named from the part and the artifact, a rebuild
SHALL replace the same names rather than accumulate, and the server MUST NOT write outside
its output folder. Export gating and watermarking apply to a written file exactly as they
do to a returned one.

#### Scenario: The engineer opens what the agent made

- **WHEN** an agent builds and exports a part
- **THEN** the reply names a STEP file and an image in the output folder, and the engineer
  opens the STEP in their CAD without the agent relaying its contents

#### Scenario: Nothing is written outside the folder

- **WHEN** a tool is asked to write to a path outside the output folder
- **THEN** the call is refused, naming the folder it may write to

### Requirement: No interface of Anvilate's own

Anvilate SHALL start no web server and SHALL ship no interactive viewer. The visual
outputs are a rendered image, an optional static part sheet that is one file and runs no
script, and exchange files (STEP, DXF, 3MF) for the user's own CAD. An interactive viewer
delivered through an MCP extension MAY be added only as an optional extra once both target
clients render it, and MUST NOT be the only way to obtain any result.

#### Scenario: The part sheet is inert

- **WHEN** a part sheet is written
- **THEN** it is a single HTML file containing no script and no reference to anything
  outside itself

#### Scenario: Every result is reachable without a viewer

- **WHEN** any tool completes
- **THEN** its result is fully available as text, an image and files on disk

### Requirement: Tool calls fit the clients' limits

A tool call on the documented golden path SHALL complete within 20 seconds on the
reference profile, well inside the shortest default tool timeout of the target clients (60
seconds), and its text result SHALL stay under a declared size budget, with the remainder
written to the output folder and named. Work that can exceed the limit SHALL report
progress or be split, and MUST NOT rely on the Tasks extension, which neither target
client supports.

#### Scenario: A slow build does not time out silently

- **WHEN** an operation would exceed the time limit
- **THEN** it is refused or split with the reason, rather than left to the client to cut off

## MODIFIED Requirements

### Requirement: CLI parity with the UI

The CLI SHALL expose every pipeline capability the MCP tools expose — at minimum `anvilate
build`, `anvilate check`, `anvilate export`, `anvilate diff` and `anvilate view` —
operating on spec files and producing the same artifacts, scorecards, and exit codes
deterministically. There is no other interface for either to have parity with.

#### Scenario: Headless build

- **WHEN** `anvilate build spec.yaml --output part.step` runs on a machine with no display
- **THEN** the pipeline validates, builds and exports exactly as the MCP tools would, with
  a machine-readable scorecard available

#### Scenario: Exit codes gate CI

- **WHEN** any acceptance check fails during `anvilate check`
- **THEN** the process exits non-zero with the failing checks listed on stderr and in the JSON report

### Requirement: MCP server for agent integration

Anvilate SHALL ship an MCP server targeting the 2026-07-28 protocol revision, operating
statelessly, exposing the pipeline as tools — at minimum: compile spec, build/regenerate,
render viewport image, measure/inspect geometry, run validation, read scorecard, and export
— whose input and output schemas are the same published JSON Schemas (2020-12) that define
the Spec IR and scorecard; tool results SHALL return typed `structuredContent` (never
prose-only), with one exception: a tool that returns a rendered image returns the image and
a text summary and no structured content, because the target clients pass only the
structured content to the model when both are present; and MUST
NOT depend on protocol features deprecated in that revision (server-initiated sampling); the
same sandboxing, validation gating, and watermarking rules apply as in the UI — the MCP
surface grants no bypass.

**Every tool SHALL identify what it acts on through its own input.** A tool whose input
names no subject requires the server to remember what a previous call produced, which is
incompatible with stateless operation; the tool surface SHALL NOT contain one. Where the
subject is an artifact too large to send on every call, the tool SHALL take a
content-addressed digest of it and resolve that digest from a store reachable by every
server instance — which is not per-connection state: any instance can serve any call and a
reconnecting client loses nothing.

#### Scenario: Agent-driven iteration

- **WHEN** an external agent calls build, then render, then validate through MCP
- **THEN** each call names its subject — the spec it builds, the digest of the geometry it
  renders, the digest of the scorecard it reads — and it receives the geometry summary and
  the typed scorecard as structured content conforming to the published schemas, and the
  viewport image as an image with a text summary, sufficient to propose its next edit
  without human relay

#### Scenario: A reconnecting client loses nothing

- **WHEN** a client's connection drops between two calls and it reconnects to a different
  server instance
- **THEN** the second call succeeds, because everything it acts on is named in the call
  itself rather than remembered by the instance that served the first

#### Scenario: MCP inherits all gates

- **WHEN** any MCP tool triggers code execution or export
- **THEN** the same sandboxing, validation gating, and watermarking rules apply as in the UI — the MCP surface grants no bypass

#### Scenario: One schema, two enforcement points

- **WHEN** the Spec IR schema version changes
- **THEN** the MCP tool contracts and the structured-output constraints used for LLM compilation both derive from the same schema artifact, so they cannot drift apart

### Requirement: The evidence bundle is producible over the tool surface

The MCP tool surface SHALL be able to produce the evidence bundle for a screening result it
is given, and SHALL be able to produce the CAD and results artifacts the CLI produces (STEP,
3MF, DXF for parts with a flat profile, QIF results) for a subject it is given. The result
contract for a file artifact is the one in "Results are written where the engineer can open
them": the file is written to the server's output folder and the result names its path,
size and SHA-256. A refusal SHALL name what that operation is actually waiting on rather
than reporting the request as malformed.

**A refusal SHALL state the reason that is true of the artifact it refuses.** Where two
surfaces refuse different sets, each SHALL say why **it** refuses, and neither SHALL inherit
the other's reason.

**No tool SHALL accept a destination path.** Where files are written is decided once, by
the user, when the server is started; a server writing to a path a caller names is a
capability, and this surface does not grant one. The evidence bundle document SHALL also be
returned as structured content, as before.

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

#### Scenario: A CAD file is written, not relayed

- **WHEN** the same client asks for the STEP file of a built part whose card passes
- **THEN** the file is written to the output folder, and the result names its path, size
  and digest without carrying the file's contents

#### Scenario: An artifact that needs geometry names what it needs

- **WHEN** a client asks for a DXF with only a scorecard handle and no built part
- **THEN** the call is refused as unavailable, naming built geometry as what it waits on,
  rather than answered with a file drawn from nothing

#### Scenario: A card that does not pass is still exported, and says so

- **WHEN** the scorecard behind the handle does not pass
- **THEN** the bundle is returned, carrying the screening disclaimer and a status that is not
  a pass, because a document reporting that a part failed is the artifact a caller most needs
  and the one a refusal would withhold

#### Scenario: No caller names a path

- **WHEN** any tool's published input schema is inspected
- **THEN** it offers no property that could name a destination, and every file a call
  creates is inside the server's output folder
