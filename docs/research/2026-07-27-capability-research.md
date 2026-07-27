# Capability research notes — 2026-07-27

Companion notes to the 18 OpenSpec change proposals under `openspec/changes/`. Four
research sweeps (AI-CAD landscape, OSS calculation ecosystem, agent/provenance
infrastructure, open data & interop) plus a main-branch audit. Local working notes; not
shipped documentation.

## The one-line synthesis

2026 independently converged on Anvilate's architecture — the literature now names it the
"Stochastic-Deterministic Boundary" (LLM proposes, deterministic verifier disposes), MCP
deprecated server-side sampling in favor of LLM-at-the-edges, and simulation research is
decomposing into atomic schema-typed callable functions. The unclaimed intersection is
**deterministic validation + reviewable/signed evidence + reproducible artifacts**. Every
proposal below feeds that moat.

## Key findings driving the portfolio

| Finding | Evidence | Change(s) |
|---|---|---|
| The reviewable calc sheet (formula → substitution → result, clause-cited, submittal PDF) is the most-validated missing artifact; Mathcad refugees want exactly this, open and local | handcalcs, efficalc, Calcs.com pitch, Eng-Tips Mathcad threads | `add-calculation-report` |
| Frontier coding agents get ~0% strict passes on unaided CAD; typed feedback schemas + over-engineering bands are what works | arXiv 2605.17448, 2605.19717 (IJCAI), 2605.20190 | `add-typed-repair-feedback` |
| Practical UQ = Monte Carlo on inputs + sensitivity ranking; a nominal PASS hiding 20% failure probability is silent green | PySTRA, pyLife probability framing | `add-uncertainty-margins` |
| The shipped analysis library (~495 symbols) has no spec domain governing its own contract | main-branch audit | `codify-analysis-library-contract` |
| Pynite's wishlist is dominated by "code checks over my member forces"; sectionproperties is the section engine everyone composes | Pynite discussion #106, StructuralPython org | `add-member-force-interop` |
| No prior art for attested mechanical calculations; in-toto custom predicates + Sigstore are mature; EU DPP registry went live 2026-07-20 | SLSA/in-toto docs, DPP Implementing Reg. (EU) 2026/1778 | `add-evidence-attestation` |
| MCP 2026-07-28 release: stateless, JSON Schema 2020-12 tools, Tasks extension, sampling deprecated; no registry server does cited engineering validation | MCP release blog, registry, build123d-mcp | `modernize-mcp-server` |
| Empty OSS code-check domains with spreadsheet-dominated workflows: ASME B31.3 piping, ASME VIII components, NDS timber, AISI S100 DSM | ecosystem sweep (no maintained PyPI packages found) | four discipline-pack changes |
| Thermal screening and isolation/shock *design* screening are unserved (analysis tools exist, design screens don't) | heatsink-calc fragments; enDAQ/PyTTa are measurement-side | `add-thermal-and-isolation-screening` |
| Eval suites are the credibility currency; MUSE's structured-spec funnel tops out ~31% intent for frontier models — a deterministic pipeline should crush it in-scope | MUSE (2605.28579), CFDLLMBench, MCP-Bench | `extend-benchmarking-agent-evals` |
| Engineers start from requirement docs, not chat | Leo AI traction; VFEAgent extract-spec-first | `add-requirements-doc-ingestion` |
| MIL-HDBK-5J is public-domain design-allowable-grade data; NIMS fatigue is free-but-gated; AISC v16 xlsx is fetchable; no "KiCad library for mechanical" exists | data sweep | `expand-open-design-data` |
| QIF (ISO 23952) schemas are free; DCC (calibration certificate) XSD is open — evidence can interoperate with the quality/metrology world | qifstandards.org, PTB DCC | `add-quality-evidence-interchange` |
| Semantic GD&T (FCF/datum model) is a confirmed vacant OSS niche bridging stack-ups → AP242 PMI → QIF | only two 1D hobby tools exist | `add-semantic-gdt-layer` |
| AP242 Edition 4 published (ISO 10303-242:2025); OCCT 8.0.0p1 shipped; NIST SFA + CAx-IF models are free conformance referees; 3MF is now ISO/IEC 25422 | prostep fact sheet, OCCT releases | `target-ap242-e4-exports` |

## Suggested sequencing (product view)

1. **Now, pure-Python, highest leverage:** `codify-analysis-library-contract` →
   `add-calculation-report` → `add-typed-repair-feedback` → `add-uncertainty-margins`.
   These monetize work already done and require none of the deferred native deps.
2. **Ecosystem positioning:** `add-member-force-interop`, `expand-open-design-data`,
   `add-quality-evidence-interchange` — make Anvilate the checking/evidence layer for the
   StructuralPython world.
3. **New verticals (parallelizable):** piping → pressure equipment → timber → CFS →
   thermal/isolation, in rough order of gap size × audience.
4. **Infrastructure that lands with later phases:** `add-evidence-attestation`,
   `modernize-mcp-server`, `add-semantic-gdt-layer`, `target-ap242-e4-exports`,
   `extend-benchmarking-agent-evals`, `add-requirements-doc-ingestion`.

## Explicit rejections (researched, declined)

- Training a geometry foundation model (Spectral/Backflip lane) — capital-intensive;
  Spectral's own essay documents the complexity/editability trap; zero verification story.
- RL-trained repair orchestration (COSMO-Agent lane) — design inverses make revision a
  solve, not a search.
- Text-to-mesh models — wrong artifact class for this audience (unchanged from project.md).
- Vision-only feedback loops as a pass/fail authority — literature says they plateau and
  cannot verify structural integrity; acceptable later only as a gross-error supplement.
- HVAC/psychrometrics and pipe hydraulics screening — well served (psychrolib, ChEDL
  `fluids`); the open gap is *code compliance*, which the piping pack takes instead.

Full source URLs are in each change's `proposal.md`.
