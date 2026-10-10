# Change: A tool set and a command set with nothing in them that cannot answer

## Why

The surface audit (`docs/agent-surface-audit.md`, findings 7, 8, 9 and 15) measured what an
agent meets: twelve tools and twelve commands. Five journeys cover what a user asks for, and
four of the twelve tools are in none of them. Two of those four can be decided now from what
they return. Every tool an agent reads costs it attention, and a tool that can only say *not
evaluated* teaches it to call something that does nothing.

This change is the proposal the audit asked for. Nothing in it is applied: each row removes
or renames something a published contract carries, so each is the owner's to approve.

## What Changes

### Tools

| Tool | Proposal | Why |
| --- | --- | --- |
| `run_fea_validation` | **Remove** until a solver ships. | It can only answer *not evaluated*. `run_validation` already says the FEA tier did not run. |
| `compile_spec` | **Remove** after one release with a note in its description. | `run_validation` and `build_part` refuse a bad spec with the same remedies. The 2026-10-09 measurement marked correct runs incomplete for skipping it. |
| `measure_geometry`, `read_scorecard` | **Hold.** Decide from the next measured run on both clients. | Both are an agent checking its own work. No journey needs them; a recorded run may show a model using them. |
| the other eight | **Keep, unchanged.** | Each is a step of at least one journey. |

Ten tools after the two removals. The journeys and their call counts do not change.

### Commands

| Command | Proposal | Why |
| --- | --- | --- |
| `build`, `export` | **One writer.** `export --artifact step` and `3mf` join `evidence-bundle`, `dxf` and `qif`; `build` stays one release as the same thing. | Two commands write files from a spec, and which one writes which is a thing to memorise. MCP already has one: `export_artifact`. |
| `doctor` | **Exit 0 when everything a user can fix is fine.** Report a capability that is not built as *not shipped*. | It fails on every install, on the FEA solver, which nothing a user does can supply. |
| `interfaces` | **Keep; move its eleven acceptance flags into one `--accept KIND` flag in a later change.** | It is the one command with more flags than the rest together, and each new interface kind has added one. |
| `check`, `combine`, `diff`, `fetch`, `parts`, `read`, `verify`, `view` | **Keep, unchanged.** | Each does one thing no other command does. |

## Impact

- Affected specs: `headless-automation` (ADDED).
- Affected contracts, each a version bump: the MCP tool catalog, the doctor result, the
  command table in `docs/headless-cli.md`.
- Affected code when approved: `mcp.py` (two tool definitions and their handlers), `cli.py`
  (`export`'s artifacts, `doctor`'s exit status), the agent skill and the server
  instructions (audit task 2.6), and the tests that walk the catalog.
- Not affected: any screen, any pattern, any file format.
