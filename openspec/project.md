# Anvilate Project Context

## Purpose

Anvilate (*anvil* + *validate*) is a local-first, open-source design agent for mechanical engineers: plain-English part descriptions compile into a typed Design Spec, which drives a deterministic parametric-geometry and physics-validation pipeline. Nothing leaves the tool without evidence. Outputs: STEP AP242, DXF/2D drawings, STL/3MF, URDF, the generating Python source, and a reproducible validation evidence bundle.

The durable product is the Design Spec IR, the deterministic pipeline, and the verification harness — the LLM is a replaceable component.

## Tech Stack

| Concern | Component | License | Notes |
|---|---|---|---|
| B-Rep kernel | OCCT (via OCP) | LGPL-2.1 w/ exception | Industrial-grade open kernel; NURBS, booleans, fillets, STEP AP242 incl. validation properties & PMI |
| Parametric modeling | build123d (primary), CadQuery (interop) | Apache-2.0 | Both sit on the shared OCP wrapper; shapes interchange |
| Meshing | Gmsh (Python SDK) | GPL-2.0+ * | Size fields, 2nd-order tets, scriptable end-to-end |
| Structural FEA | CalculiX (ccx) | GPL-2.0 * | Abaqus-like decks; static, modal, buckling, thermal |
| Multiphysics (roadmap) | Elmer, OpenFOAM | GPL * | Thermal/EM/CFD expansion without changing architecture |
| 2D drawings / DXF | ezdxf | MIT | DXF R12–R2018 read/write; drawing add-on renders PDF/SVG/PNG |
| DWG (true) | ODA File Converter (optional user install) | freeware | DXF→DWG if present; DXF is native |
| Standard parts data | bd_warehouse (active) + archived BOLTS BLT tables + cq_warehouse fastener CSVs + FreeCAD FastenersWB FsData + curated Anvilate DB (NEMA, ISO 4762/4014/4032, DIN 625, T-slot) | mixed OSS | Standards come from data tables, never LLM memory. BOLTS itself is archived — data reusable, project dead |
| Materials data | Curated `anvilate_materials` DB, provenance-tagged (sources: NIMS MatNavi, public property data; FKM-estimated fatigue parameters labeled as such) | CC-BY / project | E, ν, ρ, Sy, Su, thermal props with citations. No open FEA-grade materials DB exists — ours is a differentiator |
| Fatigue screening (roadmap) | pyLife (Bosch Research) | Apache-2.0 | FKM linear/nonlinear, rainflow, Wöhler — permissive implementation of FKM methods |
| 3DP cost estimation | Headless slicer subprocess (PrusaSlicer/OrcaSlicer CLI) | AGPL * | Print time + material mass from G-code; subprocess-isolated |
| Datasheet extraction (roadmap) | Docling (+ Granite-Docling-258M, Apache-2.0) + pdfplumber (vector geometry) | MIT | Local-first PDF table/figure extraction; per-value user confirmation required |
| Collision meshes (URDF/MJCF) | CoACD (with PaMO manifold preprocessing) | MIT | Convex decomposition for robotics export. V-HACD is archived — do not adopt |
| Units & quantities | Pint or forallpeople | BSD / Apache-2.0 | Dual SI / US-customary layer; kip, ksi, kip·ft first-class (forallpeople's `structural` environment was built for exactly this) |
| Steel sections (structural pack) | sectionproperties + eurocodepy profile data + AISC shapes DB via fetch-on-first-use | MIT / MIT / no-redistribution | Store geometry, compute properties at build time; never redistribute the AISC XLSX |
| Structural frame checks (reference) | Pynite | MIT | Reference implementation for T1-class structural checks where useful |
| LLM runtime (local) | Ollama / llama.cpp | MIT | Air-gapped mode. Ollama `:cloud`-suffixed models route to a paid remote service — air-gapped mode must refuse them (spec'd in sandbox-security) |
| LLM structure | PydanticAI 2.x (stable since mid-2026) or equivalent (instructor, outlines) | MIT | Forces valid Spec IR / edit patches; outlines' FSM token masking is the fallback for small local models |
| Viewer | three.js + tessellated B-Rep streaming (three-cad-viewer / ocp-vscode lineage) | MIT | Edges, section, exploded views, stress overlay |
| Backend/API | Python 3.11+, FastAPI, WebSocket iteration streaming | MIT | |
| Frontend | React + Vite + TypeScript | MIT | |
| Agent integration | MCP (Model Context Protocol) server | MIT | Exposes build/check/export to coding agents |
| Packaging | pip wheel + Docker/Podman image (bundles ccx, gmsh) + conda-forge | — | `docker run anvilate` must just work |
| Results post-processing | .frd/.dat parsers (in-repo), ParaView-compatible VTK export | BSD | |

\* GPL/AGPL components run as **separate subprocesses with file-based interchange** (the FreeCAD/PrePoMax/ONELAB architecture), keeping Anvilate's own codebase MIT. Legal review of the exact boundary is a Phase-1 task.

**Version pinning (verified 2026-07-08):** OCCT 7.9.x via OCP 7.9.3.x (OCCT 8.0.0 shipped May 2026 — BRepGraph topology API, faster STEP, AP242 PMI fixes — but OCP 8 bindings are still RC/experimental; stay on 7.9 and plan the migration), build123d ≥ 0.11.1, CadQuery 2.8.x, Gmsh 4.15.x (note: 4.15 changed `Boundary` tag signedness), CalculiX ccx 2.23 (2.24 expected on the usual late-summer cadence — golden regressions must gate the bump), ezdxf 1.4.x. CalculiX buckling results are version-sensitive — every physics gate carries golden-result regression cases against the pinned solver version. pycalculix is abandoned: write `.inp` decks directly and parse `.frd`/`.dat` in-repo (ccx2paraview for VTK). Avoid deep coupling to meshio (unmaintained).

**Deliberately not integrated (v1):** Zoo/KittyCAD cloud APIs (violates local-first), proprietary CAD plug-in APIs (Phase 4 does thin file-refresh helpers instead), text-to-mesh models like Hunyuan/Tripo (mesh output is the wrong artifact class for this audience).

## Project Conventions

### Code Style

- Python 3.11+, `ruff` lint + format, full type hints; Pydantic models for every schema-bearing boundary.
- TypeScript strict mode in the frontend.
- Generated (model-written) code must pass the same lint gate as human code before execution.

### Architecture Patterns

- **LLM at the edges only.** Subsystems 1 (intent compiler) and 5 (critic) may call an LLM; subsystems 2–4 (geometry, validation, export) are deterministic and must run identically with AI disabled.
- **Schema-constrained AI.** Free text never crosses a subsystem boundary; every LLM output is validated against a JSON Schema before use.
- **Semantic tags, not indices.** All cross-stage references to geometry use semantic tags assigned at feature-creation time (`mount_face`, `motor_pilot_bore`), never kernel-assigned indices (`Face7`).
- **Subprocess isolation** for GPL solvers and for model-generated code (sandboxed: no network, scratch-dir-only filesystem, CPU/RAM/time caps).
- **Determinism:** pinned solver/kernel versions per release; same spec + seed + versions ⇒ identical artifacts, bit-for-bit where the kernel permits.

### Testing Strategy

- T1 analytical checks unit-tested against Roark/Shigley worked examples.
- Every pattern in the pattern library ships with ≥ 5 golden-file tests.
- FEA pipeline regression-tested against NAFEMS-class benchmark problems (published targets re-derived, not redistributed).
- AnvilateBench (prompt → validated part) runs in CI; convergence-rate regressions block release.
- STEP import-regression matrix in CI against free/community CAD tiers; manual matrix quarterly for CATIA/NX.
- Air-gapped mode has a CI test asserting zero network calls.

### Git Workflow

- Conventional Commits (`feat(core): …`, `fix(validate): …`); PR titles follow the same convention.
- Specs first: behavior changes land as OpenSpec change proposals under `openspec/changes/`, are approved, implemented, then archived into `openspec/specs/`.
- Design Specs, generated code, and evidence bundles are all git-trackable artifacts; CI regenerates and revalidates parts on push.

## Domain Context

- **Competitive position (verified July 2026):** no shipping product combines open-source + local-first + physics-validation-in-the-loop. Text-to-CAD products (Zoo, Adam, Spectral SGS-1, Backflip) generate unverified geometry — hallucinated dimensions are their communities' top complaint; physics-AI companies (SimScale agents, Luminary, Ansys SimAI) validate geometry they didn't generate. The only closed generate→validate loops are enterprise/proprietary (PhysicsX at $2.4B valuation, domain-locked; Leap71 Noyron; Ansys GeomAI+SimAI pieces under one roof) or academic with unpublished code ("FEA as Feedback," May 2026 — frontier LLMs pass only ~20% of requirements unaided; "Physics-in-the-Loop," IJCAI 2026). Watch: Spectral SGS-2 (RL-from-simulation roadmap), Dassault's mid-2026 "Leo" agent (generation + FEA surrogates in SOLIDWORKS), and OSS fast-followers (earthtojake/text-to-cad, MIT, 7.8k stars, no FEA; build123d-mcp's tool-grounded generation beating blind codegen). Validation-in-the-loop plus free-and-local is the moat; speed to a polished MIT reference implementation matters.
- **Civil/structural white space (July 2026):** no product turns plain English into code-checked connection/plate geometry with DXF output. IDEA StatiCa validates but doesn't generate (and its cost and CBFEM opacity are its users' top complaints); OSS structural tools (Pynite, anaStruct, sectionproperties) are analysis libraries with no path to a fabrication drawing. The discipline-packs capability targets exactly this.
- Primary users are mechanical engineers, with structural/civil and industrial/manufacturing engineers served through discipline packs; outputs feed CATIA V5/3DEXPERIENCE, SolidWorks, NX, Fusion, FreeCAD, Onshape, and AutoCAD-class 2D tools.
- "Validated" means *screening-level* evidence: geometry validity, closed-form handbook checks, DFM rules, and linear-static FEA with mesh-convergence gating — explicitly **not** certified analysis. Engineering sign-off remains with a qualified engineer.
- Standard component dimensions (bolt circles, threads, bearings, extrusion profiles) are safety-critical facts: they are always retrieved from the bundled standards database, never generated from LLM memory.
- Topological-naming fragility is dissolved, not solved: the persistent artifacts are the spec and the code; geometry is regenerated from scratch each iteration and referenced by semantic tags.

## Important Constraints

- **Local-first is non-negotiable.** Full functionality on a laptop with a local model; zero network calls in air-gapped mode; cloud LLMs are opt-in with keys in the OS keychain.
- **No silent green.** A check that could not run shows "not evaluated," never pass. A non-converged FEA result can never show a green check.
- **Export gating.** Unvalidated exports require an explicit override and are watermarked in file metadata.
- **License boundary.** Anvilate code is MIT; GPL tools are subprocess-isolated with file interchange. MIT carries no patent grant — patent-sensitive contributions get flagged in review.
- **Standards data licensing.** Dimension *data* with provenance only; standard documents are never redistributed. Known tripwires: NAFEMS benchmark publications (reimplement from public reproductions, never redistribute), Fusion 360 Gallery and Text2CAD datasets (non-commercial licenses — excluded from the repo), FKM guideline text (paywalled; use pyLife's Apache-2.0 implementation), AISC shapes database (free download but AISC-copyrighted compilation — fetch-on-first-use to the user's machine, never bundle; store geometry facts and compute section properties instead where possible).
- **STEP PMI path.** OCCT/XCAF is the only open route to AP242 semantic PMI and validation properties; the writer must explicitly select the AP242 schema (the AP214 default silently drops GD&T), and build123d/CadQuery exporters don't do this — a dedicated export layer over OCP/XCAF is required, conformance-checked against NIST MBE PMI test models.
- **Performance targets** (mid-range 8-core laptop, local 8B model): prose→spec < 15 s; spec→first solid < 10 s; T0–T2 < 5 s; T3 FEA per load case (bracket-class, converged) < 60 s; full converged golden path < 5 min.

## External Dependencies

- **Ollama / llama.cpp** for local model serving; BYO API keys for Anthropic/OpenAI/Google models (opt-in).
- **Gmsh, CalculiX** binaries bundled in Docker image / fetched as wheels where available; versions pinned per release and recorded in every evidence bundle.
- **ODA File Converter** (optional, user-installed) for DWG output.
- **BOLTS / bd_warehouse** data ingested at build time with provenance tags.
- **conda-forge / PyPI / ghcr.io** distribution channels; signed releases with SBOM.
