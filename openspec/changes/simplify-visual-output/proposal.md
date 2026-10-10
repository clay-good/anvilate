# Change: One visual path — a picture for the agent, files for the engineer, no interface of our own

## Why

Anvilate is driven by the user's agent. The engineer types into Claude Code or Codex; the
agent calls Anvilate's tools. Anvilate's job is to show quickly what the agent produced and
hand it to the CAD system the engineer already owns. It is not a CAD system and should not
grow an interface that competes with one.

The specs still carry the opposite plan: `workbench-ui`, a three-pane local web app with a
live viewport, sliders and a timeline. Nothing of it is built, and the work that drifted
toward it (a WebGL viewer embedded in the part sheet behind `anvilate view --3d`) adds
script and maintenance for something every CAD tool does better once the STEP file is open.

Research on the two target clients (2026-10-09) settles the rest:

- Neither Claude Code nor Codex renders interactive MCP UI (`ui://`, MCP Apps). Both pass a
  tool's image to the model.
- **Both forward only `structuredContent` to the model when a result carries structured
  content and an image together.** `render_viewport` returns exactly that pair today, so
  the agent may never see the picture it asked for.
- It is not documented that either client shows a tool's image to the *user*. The engineer
  needs a file they can open.
- Codex stops a tool call at 60 seconds by default and truncates large results.

## What Changes

| Decision | Detail |
| --- | --- |
| **Retire the workbench** | `workbench-ui` is removed as a capability. No web server, no local web app. What mattered in it survives as agent behavior: assumptions stated, failures named, alternatives offered. |
| **The agent gets a picture it can see** | A render returns the image and a short text summary, and never pairs the image with structured content. Held by a test against each target client. |
| **The engineer gets files** | Every render, STEP, DXF and sheet the agent produces is written to an output folder chosen when the server starts, and the reply names the paths. Large files never pass through the model. |
| **One optional page** | `anvilate view` keeps writing the static one-file part sheet for sharing and sign-off. It runs no script. `--3d` is removed. |
| **CAD is the viewer** | Rotating, sectioning and measuring happen in the user's CAD from the STEP file. Docs say so, per tool. |

## Impact

- Affected specs: `workbench-ui` (REMOVED, whole capability), `headless-automation`
  (ADDED, MODIFIED), `onboarding` (MODIFIED), `discipline-packs` (MODIFIED).
- Affected code (when implemented): remove `view --3d`, `geometry.tessellate` and the
  inline viewer; split `render_viewport`'s result; add the output folder to the MCP
  server; a client check for each of Claude Code and Codex.
- Supersedes the open question recorded on 2026-10-09 about keeping the workbench spec
  open beside the part sheet.
- Explicitly out: MCP Apps or any in-chat interactive viewer. It may be revisited as an
  optional extra if both target clients come to render it, and must never be the only way
  to get a result.
