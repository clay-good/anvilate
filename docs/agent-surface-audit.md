# Audit of the agent surface

What an engineer's agent meets when it connects to Anvilate: every tool, every command, the
limits the two target clients put on them, the journeys a user actually asks for, and what
was found. The tables are generated from the live catalog by `tools/audit/inventory.py`;
the findings are written by hand, each with what was done.

Target clients: **Claude Code** and **OpenAI Codex**.

## What the clients allow

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

## The tools

12 tools. The description is what the model reads; its length is counted against the client limit above.

| Tool | Group | Takes | Returns | Writes | Description | Budget | Journeys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `compile_spec` | pipeline | `document` | `spec`, `errors`, `remedies`, `subject` | yes | 327 characters | 1 s | none |
| `build_part` | pipeline | `spec` | `geometry`, `warnings`, `subject` | yes | 295 characters | 10 s | draw, export, context |
| `render_viewport` | pipeline | `subject`, `view`, `width_px` (optional), `dimensions` (optional), `format` (optional) | an image and one line of text | yes | 476 characters | 2 s | draw, export, context, combination |
| `measure_geometry` | pipeline | `subject`, `query` | `measurement` | no | 164 characters | 2 s | none |
| `run_validation` | pipeline | `spec`, `tiers` (optional) | `scorecard`, `subject` | yes | 220 characters | 2 s | check |
| `run_fea_validation` | pipeline | `spec`, `convergence_tol` (optional) | `scorecard` | yes | 470 characters | a task | none |
| `read_scorecard` | pipeline | `subject` | `scorecard` | no | 194 characters | 1 s | none |
| `export_artifact` | pipeline | `subject`, `format` | `format`, `bundle`, `sha256`, `file`, `validated`, `note` | yes | 673 characters | 2 s | export, combination |
| `build_combination` | combination | `combination` | `combination`, `scorecard`, `subject` | yes | 668 characters | 15 s | combination |
| `list_context` | reads the user's files | `folder` | `inventory` | no | 338 characters | 1 s | context |
| `read_cad_file` | reads the user's files | `source`, `unit` (optional), `material` (optional) | `facts`, `seed` | no | 791 characters | 10 s | context |
| `describe_part` | catalog lookup | `element_type` (optional) | `catalog` | no | 384 characters | 1 s | check, draw, export |

## The journeys

What a user asks for, and the calls that answer it. Each is walked call by call in a test, with each call given the handle the one before it returned.

| Journey | The user says | Calls | In order |
| --- | --- | --- | --- |
| check | Check a part I describe | 2 | `describe_part` → `run_validation` |
| draw | Draw a part and show it to me | 3 | `describe_part` → `build_part` → `render_viewport` |
| export | Give me the file for my CAD | 4 | `describe_part` → `build_part` → `render_viewport` → `export_artifact` |
| context | Start from the drawings in my folder | 4 | `list_context` → `read_cad_file` → `build_part` → `render_viewport` |
| combination | Put these parts together | 3 | `build_combination` → `render_viewport` → `export_artifact` |

## The commands

The shell is the engineer's own door; an agent uses the tools above. Every command's first line of help says what it is for.

| Command | What it is for | Flags |
| --- | --- | --- |
| `build` | build an audited Design Spec geometry pattern as STEP or 3MF | `--ap214`, `--force`, `--format`, `--module`, `--output`, `--unvalidated` |
| `check` | compile a spec document and screen it, printing the scorecard | `--format`, `--module`, `--show-work` |
| `combine` | place several parts by the features they share, and check where they meet | `--force`, `--output`, `--picture`, `--unvalidated` |
| `diff` | compare two spec documents and the verdicts they screen to | `--format`, `--module` |
| `doctor` | check which Anvilate runtime capabilities are ready | `--format` |
| `export` | write a downstream artifact from a screened spec | `--artifact`, `--format`, `--module` |
| `fetch` | download a dataset Anvilate may read but not ship, once, with your consent | `--consent`, `--format` |
| `interfaces` | detect planar faces and through-hole patterns in a mating STEP | `--accept`, `--accept-contact`, `--accept-gap`, `--accept-mate`, `--basic-size`, `--confirmed-by`, `--fit`, `--format`, `--locator`, `--mating-plane`, `--max-gap`, `--min-contact-area`, `--min-engagement`, `--min-gap`, `--name`, `--requirement`, `--solid` |
| `parts` | list the parts a spec can declare, or describe one | none |
| `read` | measure a STEP, DXF, STL or 3MF file, or list a folder of them | `--material`, `--unit` |
| `verify` | verify an attestation envelope or STEP import integrity | `--artifact`, `--format`, `--hmac-key-file` |
| `view` | write a one-page HTML part sheet: the drawn part beside its scorecard | `--force`, `--module`, `--no-open`, `--output` |

## Where the time goes

One pass of `tools/responsiveness/measure.py` on a developer laptop, 2026-10-10. The budget
is judged on the reference runner; this run is evidence of what dominates, not a result.

| The five slowest | Measured | Budget | What the time is |
| --- | --- | --- | --- |
| `anvilate combine` | 2.4 s | 20 s | importing the geometry kernel is most of it; placing and intersecting three bodies is the rest |
| `anvilate view` | 2.4 s | 15 s | the kernel import, then one build and four projections |
| `anvilate build` | 2.4 s | 15 s | the kernel import, then one build and a STEP write that is read back |
| `anvilate read` (a STEP file) | 2.3 s | 15 s | the kernel import; the read itself is milliseconds |
| `build_part` over MCP, first call | 1.6 s | 10 s | the kernel import, paid once per server; later builds are tens of milliseconds |

Every one is the same cost: loading the kernel in a fresh process. It is paid once per
command at the shell and once per session over MCP, where every later geometry call is
fast (`build_combination` 0.02 s, `read_cad_file` 0.002 s in the same run). Commands that
need no geometry do not pay it: `anvilate check` 0.5 s, `anvilate parts` 0.4 s. Nothing here
is worth trading correctness for; the kernel is imported only by the calls that need it.

## Checked and found sound

| What was checked | What holds it |
| --- | --- |
| The README reaches a first part in three steps, says what comes back and what Anvilate is not. | The README's first screen; its counts and its example are each held by a test. |
| Every docs page is reachable from the README or the docs index, by task. | A test fails on a page neither links, and on a link to a page that is gone. |
| No page still describes the removed viewer, a web server or a built-in model. | Searched; the design-decisions page records their removal and nothing else mentions them. |
| `anvilate doctor` says in plain words what is missing and what to do about it. | Each failing item carries a `fix:` line. Its exit status is finding 9. |
| A bad spec is refused in the same words at the shell and over MCP. | The surface-parity tests compare the two, field by field. |
| Every command's help opens with what the command is for. | The commands table above is generated from those lines. |

## Findings

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
| 14 | In a combination's picture, two parts on one axis shared a balloon position, and a bolt, its washer and its nut were three balloons on one stack. | The flange pair: balloons 1 and 2 both sat in the bore. | **Fixed.** A balloon sits on its own part's visible surface, and a fastener in several holes is marked in a different hole from the one before it. A test holds the balloons apart. |
| 15 | Four tools are in no journey a user asks for: `compile_spec`, `run_fea_validation`, `measure_geometry` and `read_scorecard`. | The journeys column of the tools table above. | **Proposed, not applied.** The first two are findings 7 and 8. The other two are an agent checking its own work, and earn their place only if a measured run shows a model using them; that is part of finding 10. |
