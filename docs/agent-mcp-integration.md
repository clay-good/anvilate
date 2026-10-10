# Driving Anvilate from a coding agent

This is the operator's half of [the MCP tool surface](mcp-tool-contracts.md). That page
says what the twelve tools *are*; this one is what an agent actually does with them, and
what it will hit when it tries the loop everybody writes first.

The rules an agent must follow while doing any of this are the shipped
[agent skill](agent-skill.md) — retrieval not recall, read the scorecard, `not_evaluated`
is not a pass, screening is not certification. This page assumes them and covers the wire.

## The loop, with audited geometry patterns

The loop a coding agent wants is *build, render, validate, read the scorecard, repair, repeat*.
The analytical loop and the base-plate, cover-plate, and solid transmission-shaft geometry
patterns are callable today:

| Step | Tool | Today |
| --- | --- | --- |
| Compile the spec | `compile_spec` | **Dispatched.** |
| Find the part | `describe_part` | **Dispatched synchronously.** With no argument, every element a spec can declare, marking the ones `build_part` draws and the ones no screen checks. With an `element_type`, that element's fields and an example spec to copy and edit. Call it before writing a spec for a part. |
| Put parts together | `build_combination` | **Dispatched synchronously.** Places catalog parts by the features they share (holes on holes, face on face, shaft in bore), adds bolts, washers and nuts as envelopes, and checks where the parts meet. Its handle goes to `render_viewport` and `export_artifact`. See [combinations](combinations.md). |
| Build the part | `build_part` | **Dispatched synchronously** for every part in the [parts catalog](parts-catalog.md): plates, brackets, flanges, spacers, shafts, gear pairs, bearings, rolled members, lifting lugs, pipe runs, sheet-metal brackets, enclosures and their lids. Returns the published geometry summary, with each hole and slot under its tag. A part with no screen is drawn and not checked, and its exports carry the unvalidated mark. |
| Render the part | `render_viewport` | **Dispatched synchronously.** Takes the build handle and returns a deterministic PNG (or the SVG drawing with `format: "svg"`) with one line of text and no structured content, so the model actually sees it, and writes the image to the server's output folder. |
| Inspect the part | `measure_geometry` | **Dispatched synchronously.** Reads dimensions, volume, face count, or tagged-face area from the regenerated B-Rep. |
| Validate | `run_validation` | **Dispatched.** The card comes back in the reply. |
| Run T3 | `run_fea_validation` | **Task-dispatched.** Returns a durable handle; poll with `tasks/get`. Until a solver lands, the typed result is `not_evaluated`. |
| Read the scorecard | `read_scorecard` | **Dispatched.** Takes the subject handle returned by validation. |

Compile, validate, and read are separate stateless calls because every later call names its
subject handle. T3 adds a durable task handle: `tools/call` returns immediately,
`tasks/get` reports `statusMessage` progress and eventually carries the ordinary typed tool
result, and `tasks/cancel` terminates the worker process group, including any solver it started.
A solver that ignores SIGTERM is killed after a 2-second grace. Cancellation completes with
a `not_evaluated` scorecard, not a passing card and not a nonstandard result on MCP's bare
`cancelled` variant.

Mating-STEP interface discovery is currently a local operation:
`anvilate interfaces mating.step`. It returns measured planar faces and regular through-hole
patterns but is not exposed as an MCP tool, because those coordinates disclose imported CAD
geometry and the remote tool surface has no approved delivery contract for that content.
Multi-solid files receive deterministic geometry-derived solid IDs on each candidate, so an
agent can retain exact component identity without depending on STEP or kernel ordering. Each
ID is accompanied by measured volume, centroid, and axis-aligned bounds so it can be mapped
to a component without trusting imported labels. Exact coplanar overlap between opposing
faces on different solids is reported as a contact candidate with both solid/face IDs and
kernel-measured area; this is geometric evidence, not proof of design intent. A second pass
with `--solid` narrows the summary, discovery, contacts, and acceptance to one exact ID; an
unknown ID is refused with the available choices.
Separated opposing planar faces with positive projected overlap are reported as gap
candidates carrying their separation and direction. No maximum acceptable gap is inferred.
`--accept-gap` records one exact gap, semantic name, and named confirmer in a separate local
artifact without fabricating an `InterfaceContract` or allowable clearance.
Optional `--min-gap`, `--max-gap`, and `--requirement` inputs produce a cited clearance-band
check; all three are required, and the CLI exits 1 when the confirmed separation is outside
the caller's band. This remains a local CLI workflow rather than an MCP tool.
Every multi-solid import also returns a scored interference check. Positive common B-Rep
volume names the offending solid pair, measured volume, centroid, and bounds and exits 1;
exact face contact is not interference. This result is available through the local CLI only.
The local CLI rolls that check together with any requested ISO-fit and cited gap-band checks
into a top-level `assembly_scorecard`; its status and governing entry drive the exit code.
A passing confirmed ISO interference fit may account for the exact annular common volume of
its measured engagement. Any volume beyond that geometry remains a collision failure.
Coaxial bore/shaft surfaces on different solids are reported separately with signed
diametral clearance and axial engagement. The result is measured geometry, not a fit verdict.
`--accept-contact` requires an exact contact ID, semantic name, and named confirmer and emits
a separate confirmed-contact artifact. It deliberately does not fabricate the hole pattern
required by `InterfaceContract`.
The local CLI can additionally check that contact against explicit `--min-contact-area` and
`--requirement` inputs; the typed result joins `assembly_scorecard`.
`--accept-mate` does the same for an exact cylindrical mate, preserving its bore/shaft
endpoints, signed clearance, and engagement without making a fit verdict. Both acceptance
paths are local CLI workflows, not MCP tools.
When the caller also supplies `--fit` and `--basic-size`, the CLI resolves the existing ISO
286 tables and reports per-feature limits and pass/fail results. It refuses missing fit
inputs and never chooses a basic size or fit designation from measured geometry.
Optional `--min-engagement` and `--requirement` inputs independently check the same mate's
measured axial engagement and join the typed result to `assembly_scorecard`.
The same local command can accept an exact pattern with `--accept`, `--name`,
`--mating-plane`, and `--confirmed-by`; all four are required before it emits an
`InterfaceContract` with the source digest, solid identity, and candidate IDs retained beside
it. Single-solid JSON omits `solid_id` for compatibility.
An optional `--locator` selects an exact concentric through-bore, blind-bore, boss, or
counterbore candidate; omission
leaves the contract's locator empty rather than guessing that a circular feature locates.

Every task response also carries `_meta["dev.anvilate/progress"]` with `activity`,
`completedUnits`, `totalUnits`, and `indeterminate`. Queued and running work has no invented
total and is explicitly indeterminate; completion reports `1/1`, while failure or
cancellation ends indeterminate progress at `0/1` without claiming the unit completed.

A task that rejects its input finishes with `status: "failed"` and preserves the handler's
error category. For example, a document that fails Design Spec validation carries error
code `-32602`; it is not rewritten as `-32603`, which is reserved for an actual defect in
the server. An unavailable task operation similarly retains `-32000`.

If the worker cannot start, the call returns a durable failed task containing the launch
error. While the launching server remains running, its process monitor also marks a task
failed if the worker exits without recording a terminal result, including exit code `0`.
The error records the exit code, progress ends at `0/1`, and no scorecard is invented.
A completed result, input refusal, or cancellation already recorded by the worker wins
over the process monitor.

After the launching server exits, `tasks/get` can recover an abandoned task. New tasks
carry an OS-held execution lock inherited by the worker before it starts; a live worker
keeps that lock even during startup. If polling finds the lock released and no terminal
result, it persists a failed task with error `-32603` and progress `0/1`. It neither guesses
from a PID nor invents an exit code or scorecard. Lock-access errors leave the task
unchanged. Records created before this recovery mechanism remain readable but cannot be
automatically classified as abandoned; cancel those explicitly if needed.

Task records contain the original spec arguments and final result. They persist with
`ttlMs: null` under `ANVILATE_TASK_STORE` when that environment variable is set, otherwise
under Anvilate's local cache. This release does not evict them automatically; operators who
handle sensitive specs should place that directory on appropriately protected storage and
remove records according to their own retention policy. Task IDs are unguessable bearer
handles and the server provides no operation that lists them.

## Connecting

Anvilate's MCP server is a local process your agent starts over stdio. Nothing is hosted and
there is no URL: your agent's model writes the specs, and Anvilate validates and screens them
on your machine. Point your client at the `anvilate-mcp` executable from the environment you
installed into (`which anvilate-mcp` prints its path).

Claude Code:

```bash
claude mcp add anvilate -- /path/to/anvilate/.venv/bin/anvilate-mcp
```

OpenAI Codex (the CLI, IDE extension and desktop app share one configuration):

```bash
codex mcp add anvilate -- /path/to/anvilate/.venv/bin/anvilate-mcp
```

Codex stops a tool call at 60 seconds by default (its per-server tool timeout setting
raises it). Anvilate's calls are designed to finish well inside
that; the [responsiveness budget](../tools/responsiveness/README.md) measures them.

Claude Desktop (`claude_desktop_config.json`) or Cursor (`.cursor/mcp.json`), the same shape:

```json
{"mcpServers": {"anvilate": {"command": "/path/to/anvilate/.venv/bin/anvilate-mcp"}}}
```

The server's `initialize` reply carries `instructions` your client hands the model: the
workflow, the rules for stating a requirement, and every material, component and element
identifier that exists, generated from the bundled databases so the model copies identifiers
rather than recalling them. A field that takes one of a fixed set of values is listed with
them, for example `support*=cantilever|simply_supported|fixed_fixed|fixed_pinned|overhang`.

Order matters, because clients cut it: Claude Code 2.1 keeps the first 2,048 characters.
The rules, every element type and every material id come first and a test holds them
inside that limit; components, rolled sections and each element's fields follow, and a
refusal names the same fields and ids when a client never saw them.

```bash
anvilate-mcp
```

Newline-delimited JSON-RPC over stdin and stdout; `python -m anvilate.mcp` is the same
thing. [`examples/mcp_server_session.py`](../examples/mcp_server_session.py) drives it as a
real subprocess the way a client does. Everything below calls `handle_request` directly,
which is the same function the transport calls, so the examples stay about the protocol
rather than about pipe plumbing.

Start where any client starts. The server speaks MCP revisions 2026-07-28, 2025-11-25,
2025-06-18 and 2025-03-26 and answers in the one the client asks for (Claude Code asks for
2025-11-25), falling back to 2026-07-28 for a revision it does not know. Before 2026-07-28 a
result carries no `resultType`; the tools are the same in every revision.


```python
import json

from anvilate.mcp import handle_request

reply = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
info = reply["result"]
print("protocol:", info["protocolVersion"])
print("server:", info["serverInfo"]["name"])

tools = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
print("tools:", ", ".join(tool["name"] for tool in tools))
print("compile_spec output $ref:", json.dumps(tools[0]["outputSchema"]["properties"]["spec"]))
```

```text
protocol: 2026-07-28
server: anvilate
tools: compile_spec, build_part, render_viewport, measure_geometry, run_validation, run_fea_validation, read_scorecard, export_artifact, build_combination, list_context, read_cad_file, describe_part
compile_spec output $ref: {"$ref": "urn:anvilate:schema:design-spec:1.20.0"}
```

**Read the `$ref`, not the property name.** A tool that consumes a spec or returns a
scorecard points at the published contract at its version rather than paraphrasing it, so
the schema you constrain your model's output with and the schema the server validates
against are one document. It is not fetched: the identifier is a URN, a name and not a
location, and every tool definition embeds the schemas it references under `$defs`, so a
client resolves them offline.

An *input* that takes a spec also says `"type": "object"` beside its `$ref`, with a
description naming where the object comes from. A model writes the call from what it can
read, and a bare URN is not that: measured through Claude Code 2.1, every agent sent `spec`
as a string holding the JSON and was refused, until the type was stated inline. A string
that does hold a JSON object is refused with that reason, so the retry is the right one.

## Where results go, and opening them in your CAD

The server writes what the agent produces into one folder: `./anvilate-out` under the
directory it was started in, or the one you name.

```bash
claude mcp add anvilate -- /path/to/anvilate/.venv/bin/anvilate-mcp --out ~/parts/out
```

| The agent calls | You find |
| --- | --- |
| `render_viewport` | `<part>-<view>.png`, the same picture the model looked at |
| `export_artifact` `step`, `3mf`, `dxf` | the solid, a print mesh, a flat profile |
| `export_artifact` `part_sheet` | `<part>.html`, the drawings and every check on one page |
| `export_artifact` `evidence_bundle`, `qif` | the evidence document and the QIF results |

No tool takes a path, a rebuild replaces its files, and a CAD or QIF file is written only
when the part's checks pass. Anvilate has no viewer of its own. To turn the part over,
section it or measure it, open the STEP file:

| Tool | Import | Worth knowing |
| --- | --- | --- |
| SolidWorks | File > Open, `.step` | Units come from the file (mm). An assembly imports as an assembly unless you choose to collapse it. |
| Fusion | Upload or File > Open, `.step` | Components keep their structure. DXF inserts into a sketch. |
| Onshape | Import, `.step` | Geometry and names only; pick "Z up" if the part arrives on its side. DXF imports into a drawing or sketch. |
| FreeCAD | File > Open, `.step` | The most faithful open route. DXF is 2D. |

Anvilate writes millimetres with Z up, and says so in the file.

## Pointing your agent at a folder

Start the server with the folder the engineer wants read, and two more tools answer:

```bash
anvilate-mcp --context ~/projects/gearbox --out ~/projects/gearbox/anvilate-out
```

`--context` may be given more than once. With none, `list_context` and `read_cad_file`
are refused with `-32000` and say how to enable them.

| What is in the folder | Who reads it | How |
| --- | --- | --- |
| STEP (`.step`, `.stp`) | Anvilate | `read_cad_file`: each solid's size and volume, its holes and bosses with diameter, depth and position, hole patterns with their pitch and bolt circle, and the unit the file was written in. |
| DXF (`.dxf`) | Anvilate | `read_cad_file`: layers, closed profiles with their size and the holes inside them, and dimension entities, flagging one whose text disagrees with what it measures. A drawing that states no unit needs `unit`. |
| STL, 3MF | Anvilate | `read_cad_file`: overall size, volume when the mesh is closed, triangle count. A mesh has no holes or faces to report, and says so. |
| Images, PDFs, text, spreadsheets | The agent | With its own file tools. A number it reads from one is the agent's reading, not a measurement: say which file it came from, and ask the engineer to confirm it. |
| DWG, IGES, Parasolid, native CAD files | Nobody, yet | Refused by name. The listing says what to export from the CAD tool: DXF for a drawing, STEP for a model. Anvilate bundles no converter. |

A session reads like this. The agent calls `list_context` with `folder: "."` and learns
there is a `bracket.step`, a `plate.dxf` and a `sketch.png`. It calls `read_cad_file` with
`source: "plate.dxf"` and gets a 101.6 x 76.2 mm rectangle with four 6.35 mm holes, each
38.1 mm and 25.4 mm from the centre, and a note that the file was drawn in inches. Because
that shape is one the catalog draws, the result also carries a `seed`: a mounting plate's
parameters filled in from the drawing, the `sources` entries that cite the file for each
value, and the fields the drawing cannot give (a name and a thickness). The agent asks the
engineer for the thickness, adds it, and builds the part. A shape no pattern matches has
no seed, and the measurements are what the agent works from.

Three rules hold on every read. **Lengths are millimetres, and the result says which unit
the file was written in.** **A file is measured and never returned:** the result carries
sizes, positions and the file's SHA-256, and no geometry data. **Nothing outside the
context folders is read:** a path is resolved, links included, before it is checked, and
the folders are never written to.

At the shell, `anvilate read FILE` prints the same facts and `anvilate read FOLDER` the
same listing.

### A value that came from a file says so

A spec's `sources` list records where a value came from. Each entry names the value by its
path in the document (`field`, such as `element_params.width`), how it was obtained
(`origin`), the `file` and its `sha256`, and a `locator` saying where in the file.
[`examples/context/plate_from_drawing.spec.yaml`](../examples/context/plate_from_drawing.spec.yaml)
is a plate whose width, length and hole size each cite the DXF beside it.

| Origin | Who obtained it | What the card does |
| --- | --- | --- |
| measured from file | Anvilate, with `read_cad_file` | Nothing more: a measurement is used as it is. |
| agent read | The agent, off a picture, a scan or a PDF | The part is drawn and screened, every check that used the value says it rests on an unconfirmed reading, one entry counts the readings and names each with its file, and nothing exports as validated. |

The two origins are written in the document with underscores, as the example shows. An
agent's reading becomes a confirmed value when the engineer adds who confirmed it and on
what date to its source: the two fields are named confirmed-by and confirmed-on, with
underscores. That is the engineer's act. An agent must not fill it in for them, and a
confirmation without a named person is refused.

When the server can find a cited file in its context folders (or `anvilate check` finds it
beside the spec), it hashes it. A file that has changed since the value was taken from it
fails the `cited sources` check and names the value to read again.

## Step one: compile the document

```python
from anvilate.mcp import handle_request

DOCUMENT = {
    "anvilate_spec": "1.1.0",
    "name": "deck_plate",
    "description": "A mezzanine deck plate.",
    "units": {"value": "SI", "origin": "user_stated"},
    "material": {"ref": "ASTM-A36"},
    "manufacturing": {"process": "sheet_metal"},
    "acceptance": {"tiers": ["T1_analytical"]},
}


def call(name, arguments, request_id=1):
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


reply = call("compile_spec", {"document": DOCUMENT})
print("isError:", reply["result"]["isError"])
print("errors:", reply["result"]["structuredContent"]["errors"])

bad = call("compile_spec", {"document": {"name": "nameless"}})
print("isError:", bad["result"]["isError"])
print("first error:", bad["result"]["structuredContent"]["errors"][0])
print("transport error?", "error" in bad)
```

```text
isError: False
errors: []
isError: True
first error: description: Field required — add `description` to the document, for example `description: "A motor mount bracket for a NEMA 23 stepper."`
transport error? False
```

**A document that does not validate is a result, not a transport error.** Your request was
well formed; the document was not. An agent that treats a JSON-RPC error and a failed
compile the same way goes looking for a bug in its client, and the fix is in the spec it
wrote. `isError` and the `errors` list always agree, so a client reading only the protocol
flag reaches the same verdict as one reading the structured content.

The fix also comes back on its own. A refusal that knows what to write instead carries it in
`remedies`: a missing field's line, an unknown field's nearest real name, `60 kN` written as
`{magnitude: 60, unit: kN}`, and a bare `min_safety_factor: 1.5` written as
`{value: 1.5, origin: user_stated}`. It is the same list the CLI's JSON refusal reads as
`remedy`, so an agent can apply it without parsing the error line.

## Step two: validate, and read the card out of the reply

```python
from anvilate.mcp import handle_request

DOCUMENT = {
    "anvilate_spec": "1.1.0",
    "name": "deck_plate",
    "description": "A mezzanine deck plate.",
    "units": {"value": "SI", "origin": "user_stated"},
    "material": {"ref": "ASTM-A36"},
    "manufacturing": {"process": "sheet_metal"},
    "acceptance": {"tiers": ["T1_analytical"]},
}

reply = handle_request(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "run_validation", "arguments": {"spec": DOCUMENT}},
    }
)
card = reply["result"]["structuredContent"]["scorecard"]
for entry in card["entries"]:
    print(f"{entry['status']:14} {entry['name']}")
    print(f"               {entry['detail']}")

# The verdict is not `all(status == "pass")`, and it is not "nothing failed" either.
statuses = {entry["status"] for entry in card["entries"]}
print("passed:", statuses == {"pass"})
print("statuses present:", sorted(statuses))
```

```text
not_evaluated  T1 analytical
               the Design Spec declares no structural element type, so no discipline-pack screen can be selected from it; declare element_type and element_params, or build the pack's element and screen that
pass           material resolution
               ASTM-A36 resolves in the bundled materials database
passed: False
statuses present: ['not_evaluated', 'pass']
```

**That card is honest and it is also incomplete, and the reason is in the detail.** A Design
Spec that does not say what kind of element the part is cannot select a discipline-pack
screen, so the analytical tier reports `not_evaluated` naming the gap rather than reporting a
pass on checks it never ran.

Say what the part is, and the tier runs. `element_type` names one of the elements this
library screens and `element_params` carries that element's own fields — or `structure`,
whose `element_params` is a list of members written the same way, when the part is an
assembly rather than one element:

```python
from anvilate.mcp import handle_request

DOCUMENT = {
    "anvilate_spec": "1.2.0",
    "name": "padeye",
    "description": "A lifting padeye on a skid frame.",
    "units": {"value": "SI", "origin": "user_stated"},
    "material": {"ref": "ASTM-A36"},
    "manufacturing": {"process": "sheet_metal"},
    "element_type": "lifting_lug",
    "element_params": {
        "name": "padeye",
        "material": "ASTM-A36",
        "width": {"magnitude": 120.0, "unit": "mm"},
        "hole_diameter": {"magnitude": 40.0, "unit": "mm"},
        "thickness": {"magnitude": 20.0, "unit": "mm"},
        "load": {"magnitude": 60.0, "unit": "kN"},
    },
    "constraints": {"min_safety_factor": {"value": 2.0, "origin": "user_stated"}},
    "acceptance": {"tiers": ["T1_analytical"]},
}

reply = handle_request(
    {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "run_validation", "arguments": {"spec": DOCUMENT}},
    }
)
card = reply["result"]["structuredContent"]["scorecard"]
for entry in card["entries"]:
    print(f"{entry['status']:14} {entry['name']}")
    print(f"               {entry['detail']}")
print("card status:", card["status"])
```

```text
pass           padeye net tension
               safety factor 6.67 vs required minimum 2.00
pass           padeye pin bearing
               safety factor 3.33 vs required minimum 2.00
pass           material resolution
               ASTM-A36 resolves in the bundled materials database
card status: pass
```

Two ASME BTH-1 checks, from a document, with no Python written against the analysis library
at all. `constraints.min_safety_factor` is what the checks are judged against and it is not
defaulted: a screen that needs one and is given none reports `not_evaluated` saying so,
because a safety factor nobody stated is the assumption least worth inventing. See
[screening a spec](spec-screening.md) for the whole element list.

**And this card is the exact shape the trap has.** One entry passed and one could not run:
`all(e["status"] == "pass")` is False, `not any(e["status"] == "fail")` is True, and only
one of those two readings is right. The line to copy is the status handling, not the
verdict — `not_evaluated` is a fourth value, and `status != "fail"` reads a check that could
not run as one that passed.

## The refusals, and how to tell them apart

```python
from anvilate.mcp import handle_request, stateless_gaps, tool_catalog

print("cannot be served statelessly:", ", ".join(stateless_gaps()))
print("task-dispatched:", ", ".join(t.name for t in tool_catalog() if t.dispatch == "task"))


def refusal(name, arguments):
    reply = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    error = reply["error"]
    return error["code"], error["message"].split(";")[0].split(",")[0]


print(refusal("measure_geometry", {"subject": "sha256:" + "a" * 64, "query": ""}))
print(refusal("run_validation", {}))
```

```text
cannot be served statelessly: 
task-dispatched: run_fea_validation
(-32602, 'measure_geometry.query must be at least 1 character(s)')
(-32602, "run_validation requires 'spec'")
```

- **`-32602` is yours to fix.** The arguments did not match the published `inputSchema`.
- **A refusal that names `anvilate fetch` is the user's to act on.** Some reference data,
  such as AISC's W-shapes, may be read but not shipped, so it is downloaded once with the
  user's consent. No tool fetches it: tell the user what the refusal names and ask them to
  run `anvilate fetch <dataset> --consent`, or declare the section's properties instead.
  A material refusal that offers no identifier means none is a safe substitute; ask the
  user rather than picking the nearest grade.
- **`run_fea_validation` answers either way.** Declare `io.modelcontextprotocol/tasks` in
  the request's client-capability metadata and you get a task handle to poll; declare
  nothing (Claude Code does not) and the same result comes back in the reply. Until
  2026-10-09 the second case was refused with `-32021`, which left Claude Code with no
  T3 tier at all. This release ships no FEA solver, so either way T3 is not evaluated.
- **`-32000`, the export cannot be written.** Three true reasons, each stated: the server
  was started without an output folder (`anvilate-mcp --out DIR`); the part's checks do not
  pass, so a CAD or QIF file is withheld and there is no override on this surface; or the
  part has no such artifact (a shaft has no flat DXF profile). This is not `-32602`, so do
  not retry with a different argument. The evidence bundle and the part sheet are written
  whatever the verdict.
- **`-32000`, this install has no geometry runtime.** `build_part`, `render_viewport` and
  `measure_geometry` need the optional `anvilate[geometry]` extra. Without it they say so
  and name the extra. Your spec is not at fault, so do not edit it; ask the user to install
  the extra, or carry on with `run_validation`, which needs no geometry.
- **`-32603`** you should never see. It means a handler produced a result the tool's own
  published `outputSchema` rejects, which is a bug in Anvilate, not in your client.

## Subjects: a handle, not a memory

Four tools take a **subject** — `render_viewport`, `measure_geometry`, `read_scorecard` and
`export_artifact`. It is a handle: `sha256:` and the digest of the document it names, returned
by an earlier call. `render_viewport` wants the handle returned by `build_part`.
`measure_geometry` takes that same build handle and answers `volume`, `width`, `depth`,
`plate_thickness`, `face_count`, or `area:<semantic-face>` from the regenerated B-Rep.
`read_scorecard` and `export_artifact` both want the handle
`run_validation` returns, not the spec handle `compile_spec` returns; the store records each
document's kind, so handing over the wrong one is refused by name rather than failing three
layers down in a schema you did not send.

That handle names a **screening result** — the spec and the scorecard together — rather than
the card alone. `read_scorecard` gives you the card out of it; `export_artifact` builds a
bundle from both, so the evidence bundle you receive carries the inputs its verdicts were
computed from and can be re-run from on its own. A handle from a build before that change
resolves as a `scorecard` and is refused with what changed and what to do: call
`run_validation` again.

```python
from anvilate.mcp import handle_request

DECK = {
    "name": "deck_plate",
    "description": "A mezzanine deck plate.",
    "units": {"value": "SI", "origin": "user_stated"},
    "material": {"ref": "ASTM-A36"},
    "manufacturing": {"process": "sheet_metal"},
    "acceptance": {"tiers": ["T1_analytical"]},
}


def call(name, arguments, request_id=9):
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )["result"]["structuredContent"]


screened = call("run_validation", {"spec": DECK})
handle = screened["subject"]
print(handle.startswith("sha256:"), len(handle))
print(call("read_scorecard", {"subject": handle})["scorecard"]["status"])
```

```text
True 71
not_evaluated
```

Why a handle rather than the payload, or a session: the server keeps no memory between
calls, so any instance can serve any call and a reconnect loses nothing — and the whole
geometry does not cross the wire on every request. What it costs is a store, whose location,
reach and retention `anvilate.store` states rather than assumes. **A handle resolves in one
place or in none**: one the store does not hold is refused by name, never answered with
whatever the server did most recently.

## What a client can rely on

Request and response envelopes follow the [MCP base protocol](https://modelcontextprotocol.io/specification/2026-07-28/basic)
and [JSON-RPC Invalid Request rules](https://www.jsonrpc.org/specification#response_object).

- **Both ends are checked against the schemas you were handed.** Arguments in against
  `inputSchema`, `structuredContent` out against `outputSchema`. A result that does not
  conform is refused rather than sent.
- **Restarting the server loses nothing**, because there is nothing to lose. Reconnecting
  after a crash puts you exactly where you were.
- **A valid notification gets no response line.** Invalid request objects receive
  `-32600` with a null response ID, even when no ID was supplied. Requests require a
  string or integer ID, a string method, `jsonrpc: "2.0"`, and object-valued parameters
  when present. Booleans, null IDs, and floating-point IDs are refused.
- **Successful responses declare `resultType`.** Catalog and initialization responses use
  `"complete"`, as do synchronous tool results; dispatched work uses `"task"`.
- **`ping` is answered, and `serverInfo` names its version.** Both were missing until the
  official conformance suite was run against the server through a loopback HTTP shim: the
  handshake failed on `serverInfo.version`, which an Implementation requires, before any
  other check could run. The suite now runs weekly in CI through
  `tools/mcp-conformance/stdio_bridge.py`, which starts the real stdio server and relays the
  suite's HTTP requests to it. Its only failures are capabilities Anvilate does not declare,
  the suite's own fixture tools, and HTTP-only session behavior, each listed in
  `tools/mcp-conformance/expected-failures.yaml`.
- **Rubbish does not take the stream down.** A line that is not JSON gets a `-32700` with a
  null id and the loop continues. Nor does a well-formed line carrying the wrong shape: a
  property declared as one of the published schemas must arrive as a JSON object, and a
  string or a null where a document belongs is `-32602` rather than an exception out of the
  handler. That is worth stating because it was not true — the argument checker treats a
  `$ref` as something the operation resolves, and the operation resolved it by calling
  `dict()` on whatever arrived.
