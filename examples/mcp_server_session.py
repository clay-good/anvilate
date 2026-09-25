"""Worked example: driving the Anvilate MCP server as a real subprocess.

Everything else in this repository imports the library. This one starts the server the way
a client does — ``python -m anvilate.mcp``, newline-delimited JSON over its stdin and
stdout — and holds a short session with it: initialize, list the tools, compile a spec,
build a base plate, render and measure it, and run a validation.

The build and refusal are different statements:

1. **``build_part`` synchronously builds the audited ``base_plate`` primitive.** It executes
   no caller code and returns a published geometry summary with volume and semantic faces.
2. **``render_viewport`` takes the build handle and returns a deterministic SVG.** The same
   bytes cross as schema-backed structured data and as an MCP image attachment.

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
    """The first round: handshake, catalog, compile, screen, and build."""
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
    build_document = {
        **document,
        "name": "bp1",
        "element_type": "base_plate",
        "element_params": {
            "name": "bp1",
            "width": {"magnitude": 300.0, "unit": "mm"},
            "depth": {"magnitude": 240.0, "unit": "mm"},
            "plate_thickness": {"magnitude": 25.0, "unit": "mm"},
            "cantilever": {"magnitude": 50.0, "unit": "mm"},
            "plate_material": "ASTM-A36",
            "axial_load": {"magnitude": 200.0, "unit": "kN"},
            "concrete_strength": {"magnitude": 25.0, "unit": "MPa"},
        },
    }

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
        call(6, "build_part", {"spec": build_document}),
    ]


def session() -> list[dict]:
    """Run the whole session against a real ``python -m anvilate.mcp`` subprocess.

    Two rounds, because the second depends on the first: validation and build each return a
    subject handle consumed by a later call. A client that writes its whole script up front
    cannot do that, which is the difference between a transcript and a session.
    """
    server = subprocess.Popen(  # noqa: S603 - our own module, no shell, fixed argv
        [sys.executable, "-m", "anvilate.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env={"PYTHONPATH": _SRC, "PATH": "/usr/bin:/bin", **_STORE_ENV},
    )
    assert server.stdin is not None and server.stdout is not None
    # Closed however the session ends. A response that is not the shape expected raises
    # half way through, and without this the two pipes and a live server outlived the call.
    try:

        def send(request: dict) -> None:
            server.stdin.write(json.dumps(request) + "\n")
            server.stdin.flush()

        responses: list[dict] = []
        for request in _requests():
            send(request)
            if "id" in request:  # a notification takes no response line
                responses.append(json.loads(server.stdout.readline()))

        card_handle = next(r for r in responses if r.get("id") == 5)["result"]["structuredContent"][
            "subject"
        ]
        build_handle = next(r for r in responses if r.get("id") == 6)["result"][
            "structuredContent"
        ]["subject"]
        for request in (
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "render_viewport",
                    "arguments": {"subject": build_handle, "view": "iso", "width_px": 640},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "read_scorecard", "arguments": {"subject": card_handle}},
            },
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "measure_geometry",
                    "arguments": {"subject": build_handle, "query": "area:top"},
                },
            },
        ):
            send(request)
            responses.append(json.loads(server.stdout.readline()))

    finally:
        server.stdin.close()
        server.stdout.close()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
    return responses


def main() -> None:
    responses = session()
    print(f"{len(_requests()) + 3} messages sent, {len(responses)} responses — the")
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

    geometry = by_id[6]["result"]["structuredContent"]["geometry"]
    print(
        f"\nbuild_part -> {geometry['pattern']}, {geometry['volumeMm3']:g} mm³, "
        f"faces: {', '.join(geometry['faceTags'])}"
    )
    viewport = by_id[7]["result"]["structuredContent"]["viewport"]
    print(
        f"render_viewport -> {viewport['view']} {viewport['width_px']}×{viewport['height_px']} "
        f"{viewport['mime_type']}, image attachment included"
    )
    measured = by_id[9]["result"]["structuredContent"]["measurement"]
    pretty_unit = measured["unit"].replace("^2", "²").replace("^3", "³")
    print(f"measure_geometry -> {measured['query']} = {measured['value']:g} {pretty_unit}")


if __name__ == "__main__":
    main()
