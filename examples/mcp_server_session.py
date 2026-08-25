"""Worked example: driving the Anvilate MCP server as a real subprocess.

Everything else in this repository imports the library. This one starts the server the way
a client does — ``python -m anvilate.mcp``, newline-delimited JSON over its stdin and
stdout — and holds a short session with it: initialize, list the tools, compile a spec,
and try the three things it refuses.

The refusals are the interesting half, and they are three different statements:

1. **``build_part`` is task-dispatched.** Its cost is unbounded because it executes
   caller-supplied code, so a synchronous call cannot promise a reply and is refused
   rather than blocked on.
2. **``read_scorecard`` cannot be served at all.** It takes no arguments and returns a
   scorecard, so it is asking the server to remember what the last call produced — and
   this server has no memory between calls. Four of the eight published tools are in that
   position, and it is a contract question rather than a missing feature.
3. **``run_validation`` is not dispatched yet.** Contract and handler exist, the operation
   behind them does not, and a plausible-looking result invented here would be
   indistinguishable from a real one.

And one thing that is *not* a refusal: a spec document that fails validation comes back as
a **result** carrying its error paths. The request was well formed; the document was not,
and telling the client its request was malformed would send it looking in the wrong place.

Run it directly (``python examples/mcp_server_session.py``); :func:`session` is exercised
in the test suite.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent / "src")


def _requests() -> list[dict]:
    """The session, in order: handshake, catalog, one real call, three refusals."""
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
        call(5, "build_part", {"spec": document}),
        call(6, "read_scorecard", {}),
        call(7, "run_validation", {"spec": document}),
    ]


def session() -> list[dict]:
    """Run the whole session against a real ``python -m anvilate.mcp`` subprocess."""
    requests = _requests()
    payload = "".join(json.dumps(request) + "\n" for request in requests)
    completed = subprocess.run(  # noqa: S603 - our own module, no shell, fixed argv
        [sys.executable, "-m", "anvilate.mcp"],
        input=payload,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": _SRC, "PATH": "/usr/bin:/bin"},
        check=True,
    )
    return [json.loads(line) for line in completed.stdout.splitlines()]


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

    print("\nand the three refusals, each saying a different thing:")
    for request_id in (5, 6, 7):
        error = by_id[request_id]["error"]
        print(f"  {error['code']}  {error['message'][:96]}")


if __name__ == "__main__":
    main()
