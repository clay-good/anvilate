# Anvilate

**Anvilate** (*anvil* + *validate*) — describe a part in plain English, get back a physics-validated, parametric STEP/DXF file that drops straight into CATIA, SolidWorks, NX, or AutoCAD — plus the editable code that made it.

**License:** MIT
**Status:** Draft specification for v1.0 · July 2026
**Specs:** maintained in [OpenSpec](https://github.com/Fission-AI/OpenSpec) format under [`openspec/`](openspec/)

---

## TL;DR

Anvilate is a **local-first, open-source design agent** for mechanical engineers — and, through optional discipline packs, for the structural and industrial engineers who share the same unmet need. It closes the loop that no existing tool closes:

```
 natural language ──► typed Design Spec ──► parametric B-Rep geometry
        ▲                                          │
        │                                          ▼
   human review ◄── validation report ◄── automated physics + DFM checks
        │                                          │
        └───────── agent self-corrects ◄───────────┘  (until all checks pass)
                            │
                            ▼
        STEP AP242 · DXF · 2D drawing · STL/3MF · URDF · Python source
```

It is **not** a wrapper around an LLM. The LLM is a replaceable component. The durable product is:

1. A **Design Spec IR** — a typed, versionable intermediate representation of engineering intent (loads, interfaces, materials, manufacturing method, constraints).
2. A **deterministic geometry + validation pipeline** (OCCT → Gmsh → CalculiX) that runs identically with or without any AI.
3. A **verification harness** the agent must satisfy — analytical sanity checks, DFM rules, and FEA — before a file is ever handed to the user.
4. A **dead-simple three-pane UI**: one text box, one live 3D view, one pass/fail report.

## Problem

Mechanical engineers today face a barbell market:

- **Enterprise generative design** (Fusion Generative, CATIA MODSIM, nTop) is powerful but expensive, cloud-locked, and unacceptable to IP-sensitive firms.
- **Open-source pieces** (CadQuery, build123d, FreeCAD, Gmsh, CalculiX, Elmer) are individually excellent and scriptable, but wiring them together is a weeks-long systems-integration project per part.
- **Text-to-CAD tools** (Zoo, AdamCAD, open-source harnesses) generate geometry from prompts, but they generate *unverified* geometry. Nothing checks whether the bracket survives its load, whether the wall is castable, or whether the bolt circle matches the motor it claims to mount.

The unmet need: **a single tool that produces geometry an engineer can trust enough to open in CATIA and send toward release** — with the evidence attached.

### Who this is for

| Persona | Situation | What Anvilate gives them |
|---|---|---|
| **Design engineer at an OEM** (auto, aero, consumer hardware) | Spends 30–60% of time on standardized components: brackets, mounts, covers, spacers, enclosures | Validated STEP in minutes, with the FEA report and source code for design review |
| **Freelance/small-shop ME** | Can't justify $10k+/seat CAD+CAE licenses | A complete free design+validate stack |
| **Hardware startup** | Moves fast, iterates constantly, no PLM discipline yet | Parts as version-controlled code; regenerate on parameter change |
| **IP-sensitive enterprise team** | Prohibited from uploading designs to third-party clouds | 100% local execution, air-gapped LLM option, auditable open code |
| **Structural/civil engineer** (via the structural pack) | Base plates, gusset plates, lifting lugs eat 1–3 hours each in Excel; connection-design tools cost thousands per seat and are black boxes | Plain English → code-checked plate geometry (AISC 360 / ACI 318 / ASME BTH-1, every check citing its clause) → fabrication-ready DXF + drawing |
| **Industrial/manufacturing engineer** (via the industrial pack) | Jigs, fixtures, guards, and gauges are repetitive, standards-driven, and modeled by hand | Fixture plates with standard dowel grids, ISO 13857-parameterized machine guards, ISO 9409-1 EOAT plates — generated and checked |

### Explicit non-goals (v1)

- Not a replacement for interactive CAD. No sketch-and-extrude GUI. Engineers keep CATIA/SolidWorks/NX; Anvilate feeds them.
- Not a mesh-art generator. No text-to-STL "creative" 3D. B-Rep solids only.
- Not full multi-part assembly design with kinematics (v1 handles single parts and small rigid assemblies; full assemblies are Phase 4+).
- Not surface-modeling / Class-A surfacing.
- Not a certified analysis tool. Anvilate's FEA is a *screening* gate, clearly labeled as such; sign-off analysis remains with the engineer of record.

## Product principles

1. **The spec is the product, not the chat.** Every conversation compiles into a typed Design Spec the user can read, diff, save, and rerun.
2. **Nothing unvalidated leaves the tool.** Export is gated on checks passing (explicit, watermarked override available).
3. **Determinism over vibes.** Same spec + same seed + same versions = identical STEP file. All AI outputs are constrained to structured schemas.
4. **Local-first, cloud-optional.** Full functionality on a laptop with a local model. Cloud LLM APIs are an opt-in upgrade, never a requirement.
5. **Code is the source of truth.** The generated parametric script *is* the model. The STEP file is a build artifact.
6. **Simple surface, deep engine.** One input box. Three panes. Everything else is progressive disclosure.

## Architecture

Five subsystems. The LLM touches only #1 and #5; everything else is deterministic, tested Python.

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. INTENT COMPILER (LLM, schema-constrained)                     │
│    prose ─► Design Spec IR (typed, validated JSON/YAML)          │
├─────────────────────────────────────────────────────────────────┤
│ 2. GEOMETRY ENGINE (deterministic)                               │
│    Spec + generated build123d code ─► OCCT B-Rep solid           │
│    + semantic face/edge tagging + standard-parts library         │
├─────────────────────────────────────────────────────────────────┤
│ 3. VALIDATION ENGINE (deterministic, tiered)                     │
│    T0 geometry checks ─► T1 analytical checks ─►                 │
│    T2 DFM rules ─► T3 FEA (Gmsh → CalculiX) ─► scorecard         │
├─────────────────────────────────────────────────────────────────┤
│ 4. EXPORT LAYER (deterministic)                                  │
│    STEP AP242 · DXF/2D drawing (ezdxf) · STL/3MF · URDF ·        │
│    evidence bundle (HTML/PDF)                                    │
├─────────────────────────────────────────────────────────────────┤
│ 5. AGENT LOOP (LLM Critic + deterministic Planner)               │
│    reads scorecard ─► proposes bounded code/parameter edits ─►   │
│    re-runs 2–4 ─► converges or surfaces trade-off to user        │
└─────────────────────────────────────────────────────────────────┘
```

The behavioral contract for every subsystem lives in [`openspec/specs/`](openspec/specs/). Tech-stack choices and conventions live in [`openspec/project.md`](openspec/project.md). Future behavior changes flow through OpenSpec change proposals under `openspec/changes/`.

### Capability specs

| Capability | What it covers |
|---|---|
| [spec-ir](openspec/specs/spec-ir/spec.md) | The typed Design Spec IR: schema, units, provenance, composition, versioning |
| [intent-compilation](openspec/specs/intent-compilation/spec.md) | Prose → spec; retrieval-not-recall; bounded clarification; backend independence |
| [input-ingestion](openspec/specs/input-ingestion/spec.md) | Mating STEP, DXF dimensions, datasheet PDFs — extraction with per-value confirmation |
| [geometry-generation](openspec/specs/geometry-generation/spec.md) | Pattern-constrained codegen, sandboxed execution, semantic tagging, interface detection |
| [standards-data](openspec/specs/standards-data/spec.md) | Standards & materials databases; provenance on every value |
| [validation-gauntlet](openspec/specs/validation-gauntlet/spec.md) | T0–T3 tiers, mesh-convergence gate, modal screening, scorecard, no silent green |
| [tolerance-management](openspec/specs/tolerance-management/spec.md) | ISO 2768 defaults, fits, process-capability checks, 1D stack-up analysis |
| [cost-estimation](openspec/specs/cost-estimation/spec.md) | Screening-grade additive & CNC cost models, cost as a constraint |
| [agent-repair-loop](openspec/specs/agent-repair-loop/spec.md) | Deterministic planner, structured-edit critic, budgets, Pareto honesty |
| [artifact-export](openspec/specs/artifact-export/spec.md) | Gated STEP AP242 + validation properties + semantic PMI, STL/3MF, URDF, evidence bundle |
| [drawing-generation](openspec/specs/drawing-generation/spec.md) | Auto-dimensioned 2D drawings, tolerance callouts, feature control frames, title blocks |
| [assembly-robotics](openspec/specs/assembly-robotics/spec.md) | Typed assemblies with joints, interference checks, URDF/MJCF with exact inertia |
| [workbench-ui](openspec/specs/workbench-ui/spec.md) | The three-pane screen, assumption chips, parameter sliders, click-to-reference, iteration timeline |
| [units-and-quantities](openspec/specs/units-and-quantities/spec.md) | SI and US customary as first-class citizens: kip/ksi/in end-to-end, mixed-unit input, code-conventional precision |
| [discipline-packs](openspec/specs/discipline-packs/spec.md) | Optional packs for structural (base plates, lugs, gussets — AISC/ACI/BTH-1 checks) and industrial (fixtures, guards) engineers |
| [documentation](openspec/specs/documentation/spec.md) | Docs as a product surface: plain language, every check explained, examples executed in CI, offline help |
| [onboarding](openspec/specs/onboarding/spec.md) | One-command install, `anvilate doctor`, zero-config first run, sample gallery, time-to-first-part budget |
| [headless-automation](openspec/specs/headless-automation/spec.md) | CLI parity, CI regeneration, geometric diff, MCP server, provenance hashing |
| [sandbox-security](openspec/specs/sandbox-security/spec.md) | Code sandboxing, air-gapped mode, keychain keys, supply chain, no telemetry |
| [benchmarking](openspec/specs/benchmarking/spec.md) | AnvilateBench, solver verification, export regression, escaped-defect process |

## Repository layout (planned)

```
anvilate/
├── anvilate-core/       # spec IR, geometry engine, tagging, pattern library
├── anvilate-handbook/   # T1 analytical checks (unit-tested vs textbook cases)
├── anvilate-validate/   # gmsh + calculix orchestration, DFM rules, scorecard
├── anvilate-export/     # STEP/DXF/drawing/STL/URDF/evidence
├── anvilate-agent/      # intent compiler, planner, critic, budgets
├── anvilate-ui/         # FastAPI backend + React frontend
├── anvilate-cli/        # headless: anvilate build / check / export / diff
├── data/
│   ├── standards/       # BOLTS-derived + curated (NEMA, ISO, DIN, T-slot…)
│   └── materials/       # provenance-tagged property DB
├── patterns/            # the audited archetype library + golden files
├── benchmarks/          # AnvilateBench: prompt→validated-part tasks, scored in CI
└── openspec/            # this specification (OpenSpec format)
```

Distribution: `pip install anvilate` (pulls prebuilt gmsh/ccx wheels where available), `docker run ghcr.io/anvilate/anvilate`, conda-forge.

## Roadmap

**Phase 1 — Trustworthy One-Shot (Months 1–3)**
Spec IR + intent compiler; units layer (SI + US customary from day one — retrofitting units is how tools end up SI-only); build123d generation over 15 launch patterns; T0+T1 checks; STEP AP242 + source export; CLI + minimal 3-pane UI with live viewport; local LLM support; one-command install, `anvilate doctor`, sample gallery, executed-in-CI quickstart. *Exit: golden-path bracket demo end-to-end in < 2 min, STEP imports clean into SolidWorks & FreeCAD, a new user reaches an exported sample in < 10 min.*

**Phase 2 — The Physics Gate (Months 3–6)**
Gmsh→CalculiX pipeline with auto-BCs from tags; mesh-convergence gate; scorecard + evidence bundle; DFM rule packs (CNC, FDM); deterministic parameter-nudge repair loop. *Exit: parts cannot export green without passing FEA; convergence rate > 80% on AnvilateBench structural set.*

**Phase 3 — The Full Agent (Months 6–9)**
LLM Critic with structured edits; pattern-swap repairs; Pareto trade-off UX; mating-part STEP import → interface detection; 2D dimensioned drawings with ISO 2768 general tolerances; tolerance stack-up analysis; cost estimation; pattern library to 40; parameter sliders bound to code; MCP server + CI action for agent/parts-as-code integration; discipline-pack contract + structural steel pack preview (base plate + anchor layout, lifting lug — AISC 360 / ACI 318 / ASME BTH-1 checks with cited clauses).

**Phase 4 — Ecosystem (Months 9+)**
Small rigid assemblies + URDF/MJCF; thermal, buckling, and fatigue screening (pyLife/FKM) standard; semantic AP242 PMI export; datasheet/drawing ingestion; Elmer/OpenFOAM adapters; file-refresh helpers for SolidWorks/Fusion/FreeCAD; team mode (shared spec/pattern registries in git); community pattern marketplace; structural pack complete (gusset/shear plates, EN 1993-1-8) + industrial fixtures pack (fixture plates, ISO 13857/14120 machine guards, ISO 9409-1 EOAT plates).

## Success metrics

| Metric | 6 mo | 12 mo |
|---|---|---|
| AnvilateBench pass rate (prompt → converged validated part) | 70% | 90% |
| Median golden-path time | < 5 min | < 3 min |
| STEP clean-import rate across CAD matrix | 100% | 100% |
| GitHub stars / monthly active installs | 5k / 1.5k | 20k / 10k |
| Community-contributed merged patterns | 10 | 75 |
| "Escaped defect" reports (green-checked part that failed physically for a modeled reason) | 0 tolerated | 0 |

## Top risks & mitigations

1. **FEA auto-setup wrongness (worst risk: false confidence).** Mitigate: BCs only via semantic tags from audited patterns; convergence gate; conservative defaults; assumptions printed on every report; escaped-defect zero-tolerance process.
2. **LLM code quality on small local models.** Mitigate: pattern-constrained generation (selection + parameters, not freestyle); deterministic repair loop does most fixes without the LLM; cloud-model opt-in for hard cases.
3. **GPL boundary (Gmsh/CalculiX).** Mitigate: subprocess + file interchange architecture from day one; legal review in Phase 1.
4. **Scope creep toward "open-source SolidWorks."** Mitigate: non-goals section is enforced in triage; we feed CAD, we don't replace it.
5. **Standards data licensing** (ISO tables are copyrighted as documents). Mitigate: use dimension *data* from BOLTS/public sources with provenance; never redistribute standard documents.
6. **Fragmentation between CadQuery/build123d ecosystems.** Mitigate: build on shared OCP layer; keep geometry engine behind an internal interface.

## License

MIT — see [LICENSE](LICENSE). GPL-licensed analysis components (Gmsh, CalculiX, Elmer, OpenFOAM) are invoked as separate subprocesses with file-based interchange, keeping Anvilate's own codebase MIT. Note that MIT carries no explicit patent grant; contributions of potentially patented methods should be flagged in review.
