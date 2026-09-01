# Driving Anvilate from a coding agent

This is the operator's half of [the MCP tool surface](mcp-tool-contracts.md). That page
says what the eight tools *are*; this one is what an agent actually does with them, and
what it will hit when it tries the loop everybody writes first.

The rules an agent must follow while doing any of this are the shipped
[agent skill](agent-skill.md) — retrieval not recall, read the scorecard, `not_evaluated`
is not a pass, screening is not certification. This page assumes them and covers the wire.

## The loop, and the part of it that does not exist yet

The loop a coding agent wants is *build, validate, read the scorecard, repair, repeat*.
Two of those four steps are not callable today, and the reason is worth understanding
before you write a client around them:

| Step | Tool | Today |
| --- | --- | --- |
| Compile the spec | `compile_spec` | **Dispatched.** |
| Build the part | `build_part` | Task-dispatched: it runs caller-supplied code, so its cost is unbounded. The Tasks extension is unbuilt. |
| Validate | `run_validation` | **Dispatched.** The card comes back in the reply. |
| Read the scorecard | `read_scorecard` | Refused. It takes no arguments and returns a scorecard, which means asking the server to remember the last call. |

So the shape that works is two calls, not four: compile the document, then validate it and
read the card **out of the validation reply**. There is no separate read step, because a
separate read step is a session, and this server has none.

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

## The three refusals, and how to tell them apart

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


print(refusal("read_scorecard", {}))
print(refusal("build_part", {"spec": {}}))
print(refusal("run_validation", {}))
```

```text
cannot be served statelessly: render_viewport, measure_geometry, read_scorecard, export_artifact
task-dispatched: build_part, run_fea_validation
(-32000, 'read_scorecard names nothing in its input to act on')
(-32000, 'build_part is task-dispatched because its cost is unbounded')
(-32602, "run_validation requires 'spec'")
```

- **`-32602` is yours to fix.** The arguments did not match the published `inputSchema`.
- **`-32000`, task-dispatched.** Not a failure and not a retry: the operation's cost is
  bounded by a convergence criterion or by your own code, so a synchronous call cannot
  promise a reply. Waiting or backing off will not help; the Tasks extension is what will.
- **`-32000`, stateless.** The tool names nothing in its input to act on. Four are in that
  position — `render_viewport`, `measure_geometry`, `read_scorecard` and `export_artifact`
  — and `run_fea_validation` joins `build_part` on the task side. Retrying is pointless:
  this is an open contract question, not an outage. Do not work around it by assuming the
  server remembers your last call.
- **`-32603`** you should never see. It means a handler produced a result the tool's own
  published `outputSchema` rejects, which is a bug in Anvilate, not in your client.

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
