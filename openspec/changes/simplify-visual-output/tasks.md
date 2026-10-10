# Tasks: One visual path

## 1. Remove what competes with CAD

- [x] 1.1 Remove `anvilate view --3d`, the inline viewer and `geometry.tessellate`; a part
      sheet contains no script (gate restored to "no `<script>` in any sheet")
- [ ] 1.2 Archive the `workbench-ui` capability; reword the two requirements that mention it —
      the deltas are written; they apply when this change is archived, which waits on 2.3
- [x] 1.3 Record the decision in `docs/design-decisions.md`: no interface of our own

## 2. The agent sees the picture

- [x] 2.1 Split render results: image and text summary only; no output schema on a tool
      that returns an image; structured facts from a separate call
- [x] 2.2 Claude Code check: a recorded session where the model describes a rendered part
- [ ] 2.3 Codex check: the same — NOT RUN: Codex is not installed on the machine this was
      built on. `python tools/client-checks/see_the_render.py codex` runs it and records the
      result; the Claude Code half passed on 2026-10-10 (client 2.1.295)
- [x] 2.4 Gate: no tool pairs an image with structured content

## 3. The engineer gets files

- [x] 3.1 `anvilate-mcp --out DIR`, with a default folder; nothing written outside it
- [x] 3.2 Renders, STEP, 3MF, DXF, sheet, report and bundle written there; results name
      path, size and SHA-256; stable names replaced on rebuild
- [x] 3.3 Export gating and watermark hold for written files; test per artifact
- [x] 3.4 Text results under a declared size budget; remainder on disk and named

## 4. Limits

- [x] 4.1 Golden-path calls within 20 s on the reference profile; added to the
      responsiveness budget
- [x] 4.2 No dependence on the Tasks extension on the golden path

## 5. Docs

- [x] 5.1 "Open it in your CAD": STEP and DXF import notes for SolidWorks, Fusion, Onshape,
      FreeCAD (units, assembly mapping, Z up)
- [x] 5.2 README and agent guide describe the three outputs and no others
