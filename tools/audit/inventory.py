"""Write the agent-surface audit: what an agent meets, measured from the live catalog.

    python tools/audit/inventory.py            # rewrite docs/agent-surface-audit.md
    python tools/audit/inventory.py --check    # exit 1 if the page is not what this writes

The tables are generated from `anvilate.mcp.tool_catalog()`, the command parser and the
responsiveness budget, so they cannot describe a tool that has moved on. The journeys are
data here and are walked, call by call, by `tests/test_agent_surface.py`. The findings are
written by hand, each with what was done about it.
"""

# ruff: noqa: E501 - the page's table rows are long lines of Markdown
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "docs" / "agent-surface-audit.md"

#: What a user asks for, and the calls an agent makes to answer it. Each step names a tool;
#: the test that walks these supplies the arguments and feeds each call the handle before it.
JOURNEYS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "check",
        "Check a part I describe",
        ("describe_part", "run_validation"),
    ),
    (
        "draw",
        "Draw a part and show it to me",
        ("describe_part", "build_part", "render_viewport"),
    ),
    (
        "export",
        "Give me the file for my CAD",
        ("describe_part", "build_part", "render_viewport", "export_artifact"),
    ),
    (
        "context",
        "Start from the drawings in my folder",
        ("list_context", "read_cad_file", "describe_part", "build_part", "render_viewport"),
    ),
    (
        "combination",
        "Put these parts together",
        ("build_combination", "render_viewport", "export_artifact"),
    ),
)

_GROUPS = (
    ("REQUIRED_OPERATIONS", "pipeline"),
    ("CATALOG_OPERATIONS", "catalog lookup"),
    ("CONTEXT_OPERATIONS", "reads the user's files"),
    ("COMBINATION_OPERATIONS", "combination"),
)

_HEAD = """# Audit of the agent surface

What an engineer's agent meets when it connects to Anvilate: every tool, every command, the
limits the two target clients put on them, the journeys a user actually asks for, and what
was found. The tables are generated from the live catalog by `tools/audit/inventory.py`;
the findings are written by hand, each with what was done.

Target clients: **Claude Code** and **OpenAI Codex**.
"""

_LIMITS = """## What the clients allow

| Limit | Claude Code | Codex | How Anvilate meets it |
| --- | --- | --- | --- |
| Tool description | cut at 2,048 characters, silently | not documented | every description is under 2,048, held by a test |
| Server instructions | cut at 2,048 characters ("Server instructions truncated", debug log, 2026-10-09) | not documented | the rules, every element name and every material id are in the first 2,048, held by a test with 20 characters to spare |
| A result with an image | only the structured content reaches the model when both are present | the same | an image tool returns the image and one line of text, and no structured content |
| Tool output size | warns near 10,000 tokens, stops at 25,000 | cut to a token budget | every result is under 60,000 characters; anything larger is a file the result names |
| Time for one call | not stated | 60 seconds by default | each interactive call has a budget in `tools/responsiveness/budget.json`, the longest 20 seconds |
| Long-running tasks | the MCP Tasks extension is not offered | not offered | the one task tool answers in the reply when the client declares no Tasks support |
| Adding the server | `claude mcp add anvilate -- "$(which anvilate-mcp)"` | `codex mcp add anvilate -- "$(which anvilate-mcp)"` | one line each, in the README |

Sources: each vendor's MCP documentation as read on 2026-10-09, and for the Claude Code
truncations its own debug log on that date with Claude Code 2.1. Codex was not installed
on the machine this audit ran on, so its column is from documentation and not from a run.
"""

_FINDINGS = """## Findings

| # | Finding | Evidence | Outcome |
| --- | --- | --- | --- |
| 1 | No tool said whether it writes anything, so a client had to ask before every call or none. | `tools/list` carried no `annotations`. | **Fixed.** Every tool states read-only or not, never destructive, never open-world. A test calls each read-only tool and compares the output folder, the subject store and the context folder before and after. |
| 2 | Three arguments had no description: the render width, the tiers override and the FEA tolerance. | Found by the new gate on its first run. | **Fixed.** Each says what it takes, and the gate holds the next one. |
| 3 | An agent learned an element's fields from refusals, a call at a time. | The field lists sit past the 2,048 characters Claude Code keeps. | **Fixed.** `describe_part` returns the fields and an example spec in one call. |
| 4 | A part with no screen could not be exported over MCP at all. | `export_artifact` refused any card that did not pass. | **Fixed.** A drawn-only part is written marked unvalidated and the result says so; a failing part is still refused. |
| 5 | A sheet-metal bracket's STEP file crashed the server on export. | The solid carried a placement; the kernel wrote an assembly of one and segfaulted reading it back. | **Fixed.** Built in place; `write_step` refuses a placed solid before reading it; every part's STEP is written and read back in a test. |
| 6 | A dimension label ran off a long thin part's view and read "200 M". | The rendered picture of a 4 m beam. | **Fixed.** The view makes room for the label; a test holds every stroke inside the image. |
| 7 | `run_fea_validation` can only ever answer *not evaluated*: no solver ships. | Its own result, on every call. | **Proposed, not applied.** Removing a tool is a breaking change to the published catalog. Proposal: drop it until a solver ships, and let `run_validation` say T3 was not evaluated, as it already does. |
| 8 | `compile_spec` is a step `run_validation` makes unnecessary: a bad spec is refused there with the same remedies. | The 2026-10-09 measurement scored correct runs incomplete for skipping it. | **Proposed, not applied.** Fold it into `run_validation`'s refusal; keep the tool one release with a note. |
| 9 | `anvilate doctor` reports FAIL on every install. | It fails on the FEA solver, which nothing a user does can supply. | **Proposed, not applied.** Report a capability that is not built as *not shipped* and exit 0 when everything a user can fix is fine. It changes the published doctor result, so it wants a version bump of that contract. |
| 10 | Only the eight pipeline tools have been measured with a real agent, and only on Claude Code. | `tools/agent-skill-measurement/results/2026-10-09.json`. | **Open.** The four tools added since (`describe_part`, `list_context`, `read_cad_file`, `build_combination`) are walked by the journey test below and have not been driven by a model. Extending the corpus means a paid run on each client. |
| 11 | Codex has not been run at all. | Not installed where this audit ran. | **Open.** The registration line is in the README; the harness has no Codex runner yet. |
| 12 | Install is `git clone`. | There is no `anvilate` on the package index; a CI job watches for the day there is. | **Open, the owner's decision.** Publishing is outward-facing and was not done. |
| 13 | The independent STEP reader has not seen the new files. | The scheduled referee job now covers 26 patterns and 5 assemblies and last ran before them. | **Open.** Run the `step-referee` job; a warning it reports is a finding. |
| 14 | In a combination's picture, two parts on one axis share a balloon position. | The flange pair: balloons 1 and 2 both sit in the bore. | **Open.** Balloons step aside when they collide; placing each on its own part's surface is the fix. |
| 15 | Four tools are in no journey a user asks for: `compile_spec`, `run_fea_validation`, `measure_geometry` and `read_scorecard`. | The journeys column of the tools table above. | **Proposed, not applied.** The first two are findings 7 and 8. The other two are an agent checking its own work, and earn their place only if a measured run shows a model using them; that is part of finding 10. |
"""


def _tools() -> str:
    from anvilate import mcp

    budget = json.loads(
        (REPO / "tools" / "responsiveness" / "budget.json").read_text(encoding="utf-8")
    )["operations"]
    used: dict[str, list[str]] = {}
    for key, _ask, steps in JOURNEYS:
        for step in steps:
            used.setdefault(step, []).append(key)
    rows = [
        "## The tools",
        "",
        f"{len(mcp.tool_catalog())} tools. The description is what the model reads; its length is counted against the client limit above.",
        "",
        "| Tool | Group | Takes | Returns | Writes | Description | Budget | Journeys |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for tool in mcp.tool_catalog():
        group = next(label for name, label in _GROUPS if tool.name in getattr(mcp, name))
        required = set(tool.input_schema.get("required", []))
        takes = ", ".join(
            f"`{name}`" + ("" if name in required else " (optional)")
            for name in tool.input_schema["properties"]
        )
        if tool.output_schema is None:
            returns = "an image and one line of text"
        else:
            returns = ", ".join(f"`{name}`" for name in tool.output_schema["properties"])
        seconds = budget.get(f"mcp {tool.name}", {}).get("seconds")
        rows.append(
            f"| `{tool.name}` | {group} | {takes or 'nothing'} | {returns} | "
            f"{'yes' if tool.writes else 'no'} | {len(tool.description):,} characters | "
            f"{f'{seconds:g} s' if seconds is not None else 'a task'} | "
            f"{', '.join(used.get(tool.name, [])) or 'none'} |"
        )
    return "\n".join(rows) + "\n"


def _journeys() -> str:
    rows = [
        "## The journeys",
        "",
        "What a user asks for, and the calls that answer it. Each is walked call by call in a test, with each call given the handle the one before it returned.",
        "",
        "| Journey | The user says | Calls | In order |",
        "| --- | --- | --- | --- |",
    ]
    for key, ask, steps in JOURNEYS:
        rows.append(f"| {key} | {ask} | {len(steps)} | {' → '.join(f'`{s}`' for s in steps)} |")
    return "\n".join(rows) + "\n"


def _commands() -> str:
    from anvilate.cli import _build_parser

    parser = _build_parser()
    commands = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    helps = {choice.dest: choice.help for choice in commands._choices_actions}
    rows = [
        "## The commands",
        "",
        "The shell is the engineer's own door; an agent uses the tools above. Every command's first line of help says what it is for.",
        "",
        "| Command | What it is for | Flags |",
        "| --- | --- | --- |",
    ]
    for name in sorted(commands.choices):
        flags = sorted(
            option
            for action in commands.choices[name]._actions
            for option in action.option_strings
            if option.startswith("--") and option != "--help"
        )
        rows.append(
            f"| `{name}` | {helps[name]} | {', '.join(f'`{f}`' for f in flags) or 'none'} |"
        )
    return "\n".join(rows) + "\n"


def page() -> str:
    """The audit page, as text."""
    return "\n".join([_HEAD, _LIMITS, _tools(), _journeys(), _commands(), _FINDINGS])


def main(argv: list[str]) -> int:
    if "--check" in argv:
        if PAGE.read_text(encoding="utf-8") != page():
            print(f"{PAGE.relative_to(REPO)} is stale; run tools/audit/inventory.py")
            return 1
        return 0
    PAGE.write_text(page(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
