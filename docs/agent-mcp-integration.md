# Driving Anvilate from a coding agent

This is the operator's half of [the MCP tool surface](mcp-tool-contracts.md). That page
says what the eight tools *are*; this one is what an agent actually does with them, and
what it will hit when it tries the loop everybody writes first.

The rules an agent must follow while doing any of this are the shipped
[agent skill](agent-skill.md) — retrieval not recall, read the scorecard, `not_evaluated`
is not a pass, screening is not certification. This page assumes them and covers the wire.

## The loop, with the first geometry pattern

The loop a coding agent wants is *build, render, validate, read the scorecard, repair, repeat*.
The analytical loop and the first geometry pattern are callable today:

| Step | Tool | Today |
| --- | --- | --- |
| Compile the spec | `compile_spec` | **Dispatched.** |
| Build the part | `build_part` | **Dispatched synchronously** for `base_plate`; returns the published geometry summary. |
| Render the part | `render_viewport` | **Dispatched synchronously.** Takes the build handle and returns a deterministic SVG as structured data and an image attachment. |
| Validate | `run_validation` | **Dispatched.** The card comes back in the reply. |
| Run T3 | `run_fea_validation` | **Task-dispatched.** Returns a durable handle; poll with `tasks/get`. Until a solver lands, the typed result is `not_evaluated`. |
| Read the scorecard | `read_scorecard` | **Dispatched.** Takes the subject handle returned by validation. |

Compile, validate, and read are separate stateless calls because every later call names its
subject handle. T3 adds a durable task handle: `tools/call` returns immediately,
`tasks/get` reports `statusMessage` progress and eventually carries the ordinary typed tool
result, and `tasks/cancel` terminates the worker process group. Cancellation completes with
a `not_evaluated` scorecard, not a passing card and not a nonstandard result on MCP's bare
`cancelled` variant.

Every task response also carries `_meta["dev.anvilate/progress"]` with `activity`,
`completedUnits`, `totalUnits`, and `indeterminate`. Queued and running work has no invented
total and is explicitly indeterminate; completion reports `1/1`, while failure or
cancellation ends indeterminate progress at `0/1` without claiming the unit completed.

A task that rejects its input finishes with `status: "failed"` and preserves the handler's
error category. For example, a document that fails Design Spec validation carries error
code `-32602`; it is not rewritten as `-32603`, which is reserved for an actual defect in
the server. An unavailable task operation similarly retains `-32000`.

Task records contain the original spec arguments and final result. They persist with
`ttlMs: null` under `ANVILATE_TASK_STORE` when that environment variable is set, otherwise
under Anvilate's local cache. This release does not evict them automatically; operators who
handle sensitive specs should place that directory on appropriately protected storage and
remove records according to their own retention policy. Task IDs are unguessable bearer
handles and the server provides no operation that lists them.

## Connecting

```bash
anvilate-mcp
```

Newline-delimited JSON-RPC over stdin and stdout; `python -m anvilate.mcp` is the same
thing. [`examples/mcp_server_session.py`](../examples/mcp_server_session.py) drives it as a
real subprocess the way a client does. Everything below calls `handle_request` directly,
which is the same function the transport calls, so the examples stay about the protocol
rather than about pipe plumbing.

Start where any client starts:

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
tools: compile_spec, build_part, render_viewport, measure_geometry, run_validation, run_fea_validation, read_scorecard, export_artifact
compile_spec output $ref: {"$ref": "https://anvilate.dev/schemas/design-spec/1.3.0.json"}
```

**Read the `$ref`, not the property name.** A tool that consumes a spec or returns a
scorecard points at the published contract at its version rather than paraphrasing it, so
the schema you constrain your model's output with and the schema the server validates
against are one document. Fetch it once, pin the version, and you are done.

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
first error: description: Field required
transport error? False
```

**A document that does not validate is a result, not a transport error.** Your request was
well formed; the document was not. An agent that treats a JSON-RPC error and a failed
compile the same way goes looking for a bug in its client, and the fix is in the spec it
wrote. `isError` and the `errors` list always agree, so a client reading only the protocol
flag reaches the same verdict as one reading the structured content.

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


print(refusal("measure_geometry", {"subject": "sha256:" + "a" * 64, "query": "volume"}))
print(refusal("run_validation", {}))
```

```text
cannot be served statelessly: 
task-dispatched: run_fea_validation
(-32000, 'measure_geometry is not dispatched yet: measuring a feature needs built geometry')
(-32602, "run_validation requires 'spec'")
```

- **`-32602` is yours to fix.** The arguments did not match the published `inputSchema`.
- **`-32021`, task capability missing.** `run_fea_validation` can only return a task, and
  the extension forbids that response unless this request declares
  `io.modelcontextprotocol/tasks`. Add it under the request's client-capability metadata;
  the error's `requiredCapabilities` gives the exact shape.
- **`-32000`, not dispatched yet.** The contract and the handler are built and the operation
  behind it is not, and the message names what it waits on — `measure_geometry` waits on
  built geometry. Retrying is pointless; a result invented
  there would be indistinguishable from a real one.
- **`-32000`, that format is not served here.** The narrower version of the same fact, and
  the one place a tool is dispatched while part of what it publishes is not: `export_artifact`
  serves `evidence_bundle` and refuses `dxf` and `qif` — **for two different reasons, and the
  message gives you the one that applies.** A DXF is drawn from built geometry, and there is
  none. QIF results are not: they cross from a screened card, and `anvilate export --artifact
  qif` writes one at the shell today. What they wait on *here* is this tool's published
  result, whose payload is the evidence bundle document, where a QIF results file is XML. It
  is not `-32602`, so do not retry with a different argument — retry with a different
  *format*, or at the shell, or not at all.

  This used to be a different refusal. Four tools named nothing in their input to act on, so
  they could not be served by a server with no memory between calls — an open contract
  question rather than an outage. It is closed: every tool now takes a **subject**, a handle
  returned by an earlier call, and `stateless_gaps()` is empty as a consequence rather than
  as an edit. See [what a subject is](#subjects-a-handle-not-a-memory).
- **`-32603`** you should never see. It means a handler produced a result the tool's own
  published `outputSchema` rejects, which is a bug in Anvilate, not in your client.

## Subjects: a handle, not a memory

Four tools take a **subject** — `render_viewport`, `measure_geometry`, `read_scorecard` and
`export_artifact`. It is a handle: `sha256:` and the digest of the document it names, returned
by an earlier call. `render_viewport` wants the handle returned by `build_part`.
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

- **Both ends are checked against the schemas you were handed.** Arguments in against
  `inputSchema`, `structuredContent` out against `outputSchema`. A result that does not
  conform is refused rather than sent.
- **Restarting the server loses nothing**, because there is nothing to lose. Reconnecting
  after a crash puts you exactly where you were.
- **A notification gets no response line.** If you send one and then block on a read, you
  will block forever.
- **Rubbish does not take the stream down.** A line that is not JSON gets a `-32700` with a
  null id and the loop continues. Nor does a well-formed line carrying the wrong shape: a
  property declared as one of the published schemas must arrive as a JSON object, and a
  string or a null where a document belongs is `-32602` rather than an exception out of the
  handler. That is worth stating because it was not true — the argument checker treats a
  `$ref` as something the operation resolves, and the operation resolved it by calling
  `dict()` on whatever arrived.
