"""Worked example: the pipeline as MCP tool contracts, and which calls are tasks.

Eight operations, two dispatch modes, and one rule that decides between them.

An agent driving Anvilate over MCP needs to know two things about every call it can make:
what document it will get back, and whether it will get it in the reply. The first is
answered by ``$ref``-ing the published contract instead of describing it — the tool schema
points at ``https://anvilate.dev/schemas/scorecard/1.0.0.json``, so the tool surface and
the structured-output constraint a compiler is decoded under resolve to the same artifact
and cannot drift apart. The second is answered by cost:

- **Bounded** — the work is a function of the input's size. Parsing a spec, running the
  closed-form T0/T1/T2 checks, reading a scorecard, writing an export. Synchronous.
- **Unbounded** — the work is a function of a convergence criterion, or of code the caller
  supplied. A full build, an FEA-class run. Dispatched through the Tasks extension:
  handle, progress, cancellation.

The trap on either side is symmetric and both halves are real. Expose everything as a task
"for consistency" and an agent polls for a result that was ready before the first poll.
Expose everything synchronously and the client times out on the one call that mattered.
So the FEA tier's cost is not a judgement call: a tool covering T3 that declares bounded
cost is refused in the constructor, because T3's stopping condition is a convergence
tolerance and a convergence tolerance is not a bound on wall time.

Four of the eight are backed by shipping code today and name the symbol, which CI resolves
against the live surface. The other four say ``None`` rather than naming something that
does not exist — the contract is worth pinning before the server is built, which is the
cheapest moment to change a tool surface, but not at the price of implying it runs.

Run it directly (``python examples/mcp_tool_catalog.py``); the assertions below are the
example's claims.
"""

from __future__ import annotations

import json

from anvilate.mcp import Dispatch, catalog_issues, tool_catalog, wire_definitions


def describe_tool_surface() -> list[str]:
    """The catalog as the table an integrator reads, one line per operation."""
    lines = [f"{'tool':<20}{'dispatch':<14}{'gates':<24}backing"]
    for tool in tool_catalog():
        gates = ",".join(sorted(gate.value for gate in tool.gates)) or "-"
        lines.append(
            f"{tool.name:<20}{tool.dispatch.value:<14}{gates:<24}{tool.backing or '(not built)'}"
        )
    return lines


def main() -> None:
    # The catalog holds itself to the published contracts on every import.
    assert catalog_issues() == []

    for line in describe_tool_surface():
        print(line)

    tasks = [t.name for t in tool_catalog() if t.dispatch is Dispatch.TASK]
    print(f"\ntask-dispatched: {tasks}")
    assert tasks == ["build_part", "run_fea_validation"]

    # What a client actually receives for one tool. The scorecard is referenced, not
    # described: an agent that fetches that $id gets the same document the library writes.
    validation = next(d for d in wire_definitions() if d["name"] == "run_validation")
    print("\nrun_validation output schema:")
    print(json.dumps(validation["outputSchema"], indent=2))
    assert (
        validation["outputSchema"]["properties"]["scorecard"]["$ref"]
        == "https://anvilate.dev/schemas/scorecard/1.0.0.json"
    )
    assert validation["_meta"]["dev.anvilate/dispatch"] == "synchronous"


if __name__ == "__main__":
    main()
