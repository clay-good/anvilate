"""Worked example: driving the Anvilate MCP server as a real subprocess.

Everything else in this repository imports the library. This one starts the server the way
a client does — ``python -m anvilate.mcp``, newline-delimited JSON over its stdin and
stdout — and holds a short session with it: initialize, list the tools, compile a spec,
run a validation, and try the two things it refuses.

The refusals are the interesting half, and they are two different statements:

1. **``build_part`` is task-dispatched.** Its cost is unbounded because it executes
   caller-supplied code, so a synchronous call cannot promise a reply and is refused
   rather than blocked on.
2. **``render_viewport`` is not dispatched yet, and says what it waits on.** It names what
   it acts on — every tool does now, by taking a subject handle — so the contract is sound
   and what is missing is built geometry. "Not implemented" is not an answer a client can
   act on; the message names the thing.

The session also does the thing subjects exist for: ``run_validation`` returns a handle to
the card it screened, and ``read_scorecard`` reads that card back by handle. No memory
between calls, and the payload never crosses the wire twice.

``run_validation``'s answer is the shape worth looking at: the scorecard comes back with
the analytical tier ``not_evaluated``, because a Design Spec declares no structural element
type and no discipline-pack screen can be selected from one. That is a named gap, which is
the only kind this library ships.

And one thing that is *not* a refusal: a spec document that fails validation comes back as
a **result** carrying its error paths. The request was well formed; the document was not,
and telling the client its request was malformed would send it looking in the wrong place.

Run it directly (``python examples/mcp_server_session.py``); :func:`session` is exercised
in the test suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent / "src")

# Where the server publishes the handles it hands back. Left to the server's own default —
# `$ANVILATE_SUBJECT_STORE`, else the user's cache — unless the caller has set one, which is
# how the test suite keeps its runs out of that cache.
_STORE_ENV = (
    {"ANVILATE_SUBJECT_STORE": os.environ["ANVILATE_SUBJECT_STORE"]}
    if "ANVILATE_SUBJECT_STORE" in os.environ
    else {}
)


def _requests() -> list[dict]:
    """The session, in order: handshake, catalog, three real calls, two refusals."""
    from anvilate.spec import (
        AcceptanceCriteria,
        DesignSpec,
        Manufacturing,
        ManufacturingProcess,
        MaterialRef,
        Provenanced,
        ValidationTier,
    )
    from anvilate.units import UnitSystem

    document = DesignSpec(
        name="mezzanine_deck",
        description="A mezzanine deck plate with a wind-exposed leading edge.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.SHEET_METAL),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    ).model_dump(mode="json")

    def call(request_id: int, name: str, arguments: dict) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }

    return [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        call(3, "compile_spec", {"document": document}),
        call(4, "compile_spec", {"document": {"name": "nameless"}}),
        call(5, "run_validation", {"spec": document}),
        call(6, "build_part", {"spec": document}),
        call(7, "render_viewport", {"subject": "sha256:" + "a" * 64, "view": "iso"}),
    ]


def session() -> list[dict]:
    """Run the whole session against a real ``python -m anvilate.mcp`` subprocess.

    Two rounds, because the second one depends on the first: `run_validation` answers with a
    **subject** — a handle to the card it screened — and `read_scorecard` takes that handle.
    A client that writes its whole script up front cannot do that, which is the difference
    between a transcript and a session.
    """
    server = subprocess.Popen(  # noqa: S603 - our own module, no shell, fixed argv
        [sys.executable, "-m", "anvilate.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env={"PYTHONPATH": _SRC, "PATH": "/usr/bin:/bin", **_STORE_ENV},
    )
    assert server.stdin is not None and server.stdout is not None

    def send(request: dict) -> None:
        server.stdin.write(json.dumps(request) + "\n")
        server.stdin.flush()

    responses: list[dict] = []
    for request in _requests():
        send(request)
        if "id" in request:  # a notification takes no response line
            responses.append(json.loads(server.stdout.readline()))

    handle = next(r for r in responses if r.get("id") == 5)["result"]["structuredContent"][
        "subject"
    ]
    send(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "read_scorecard", "arguments": {"subject": handle}},
        }
    )
    responses.append(json.loads(server.stdout.readline()))

    server.stdin.close()
    server.stdout.close()
    server.wait(timeout=30)
    return responses


def main() -> None:
    responses = session()
    print(f"{len(_requests())} messages sent, {len(responses)} responses — the")
    print("notification takes none, which is what a client waiting one-for-one needs.\n")

    by_id = {response.get("id"): response for response in responses}
    print(f"initialize -> protocol {by_id[1]['result']['protocolVersion']}")
    print(f"tools/list -> {len(by_id[2]['result']['tools'])} tools")

    good = by_id[3]["result"]
    print(f"\ncompile_spec (valid)   -> isError {good['isError']}, ", end="")
    print(f"spec name {good['structuredContent']['spec']['name']!r}")
    bad = by_id[4]["result"]
    print(f"compile_spec (invalid) -> isError {bad['isError']}, a result and not an error:")
    for message in bad["structuredContent"]["errors"][:3]:
        print(f"    {message}")

    card = by_id[5]["result"]["structuredContent"]["scorecard"]
    print("\nrun_validation -> a scorecard, with the tier it cannot run named:")
    for entry in card["entries"]:
        print(f"    [{entry['status'].upper()}] {entry['name']}: {entry['detail'][:72]}")

    handle = by_id[5]["result"]["structuredContent"]["subject"]
    read_back = by_id[8]["result"]["structuredContent"]["scorecard"]
    print(f"\nthe card came back with a handle: {handle[:20]}…")
    print(f"read_scorecard({handle[:13]}…) -> the same card: {read_back == card}")

    print("\nand the two refusals, each saying a different thing:")
    for request_id in (6, 7):
        error = by_id[request_id]["error"]
        print(f"  {error['code']}  {error['message'][:96]}")


if __name__ == "__main__":
    main()
