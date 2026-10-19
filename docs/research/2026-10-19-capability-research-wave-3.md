# Capability research notes, wave 3 — 2026-10-19

Companion to the two 2026-07-27 notes and the ten OpenSpec change proposals this wave
produced. One session: a re-read of all 27 capability specs and 46 open changes, an
inventory of the shipped library (249 analysis modules, 12 packs), and web verification
of every edition, license and regulation the new proposals cite. Local working notes; not
shipped documentation.

## The one-line synthesis

Waves 1 and 2 built the evidence moat and the inputs and outputs around it. By October
2026 the shipped product is a part-and-product checker with 1,957 cited symbols, and the
open changes already cover FEA, optimization, drive trains, profiles and quality forms.
What is left is on the edges of that: the loops the doctrine demands and nobody closed
(the test result read back, the person who must confirm), the structural persona's
missing code family (Eurocode 3) and its everyday regulated artifacts (guardrails,
stairs, ladders, equipment anchorage, timber connections), the solve that stops typed
member forces (frame analysis), and the handoffs that make a check visible to people who
did not run it (SARIF and JUnit in CI, IFC into the building model, a maintenance plan
after delivery).

## Audit findings that drove the portfolio

| Finding | Evidence | Change |
| --- | --- | --- |
| `discipline-packs` has promised Eurocode check sets since the first spec and nothing ships; the second-generation Eurocodes land in exactly this window (EN 1993-1-1:2022 DAV 2026-03-30, EN 1993-1-8:2024, withdrawal of first generation 2028-03-30) | spec audit; JRC 2G workshop; BSI, AENOR listings | `add-eurocode-steel-pack` |
| Member forces are typed by the agent for every frame; `product-screening` names indeterminate paths and (correctly) refuses to split them; the member-force doorway accepts only external solvers | spec audit; `docs/analysis-interop.md` | `add-frame-analysis` |
| `verification-planning` records a test outcome and nothing reads it; the escaped-defect process has no detector | spec audit | `add-model-credibility` |
| Seven screens compute a life (bearing, fatigue, duty cycle, wear, corrosion, O-ring set, creep) and no artifact turns a life into a date | library inventory | `add-service-life-planning` |
| Four person-only decisions (draft confirmation, unvalidated export, review record, dataset consent) are tool arguments the agent fills; MCP elicitation now exists in both target clients | `src/anvilate/mcp.py`; Claude Code 2.1.76 changelog; Codex 0.119 notes | `add-person-confirmation` |
| Guardrails, stairs, ladders and platforms are the most-built small structures in industry and are governed by a public-domain regulation with numeric rules | 29 CFR 1910 Subpart D read via LII | `add-walking-working-surfaces-pack` |
| Findings have no line, no JUnit, no SARIF, no baseline; the "parts as code" lane stops at exit codes | `headless-automation` audit | `add-parts-as-code-ci` |
| The structural pack has anchor checks and the loads library has seismic base shear, but nothing computes the nonstructural component force that loads equipment anchors; ASCE 7-22 changed the equation | `src/anvilate/analysis/building_loads.py`; Simpson Strong-Tie 2026-05 note; HCAI 2025 CBC materials | `add-equipment-anchorage` |
| The timber pack has members and no connections; the yield-mode equations are open literature (AWC TR12) | `src/anvilate/analysis/nds_timber.py` | `add-timber-connections` |
| The structural persona's colleagues exchange IFC; a checked plate arrives as an anonymous STEP solid | export audit | `add-ifc-structural-export` |

## Verified facts the proposals rest on

| Fact | Verified 2026-10-19 |
| --- | --- |
| Pynite is MIT (Copyright 2018 D. Craig Brinck); PyNiteFEA 3.2.0 released 2026-09-13; static, P-Δ, modal, pushover, plates | GitHub LICENSE; PyPI |
| IfcOpenShell is LGPL-3.0-or-later; 0.9.0.post1 released 2026-10-15; full geometry for IFC2x3 TC1 and IFC4 Add2 TC1; parsing only for IFC4x3 Add2 | PyPI |
| NASA-STD-7009A: eight credibility factors scored 0–4, 0 for insufficient evidence; approved for public release, distribution unlimited | NTRS 20160011121 |
| MCP elicitation: spec 2025-06-18, URL mode 2025-11-25; Claude Code 2.1.76 (2026-03-14) with Elicitation hooks; Codex CLI 0.119/0.120; two reports of Claude Code builds not advertising the capability | code.claude.com changelog; codex.danielvaughan.com; claudeissues.com |
| GitHub code scanning: SARIF 2.1.0 subset, locations drive annotations, partialFingerprints for de-duplication, 5,000 results per upload | docs.github.com |
| 29 CFR 1910.29(b)(3)–(5): 200 lbf top rail within 2 in, 39 in deflection floor, 150 lbf midrail; 1910.25(b)(6): 5× live load, never under 1,000 lb concentrated; 1910.25(c): 30–50°, riser ≤ 9.5 in, tread ≥ 9.5 in, width ≥ 22 in; 1910.23: rungs 10–14 in, 16 in clear, 7 in behind, 42 in rail extension; 1910.28(b)(1): 4 ft; (b)(9): 24 ft ladders | law.cornell.edu mirror of the eCFR (eCFR refuses scripted reads) |
| EN 1993-1-8:2024 approved 2024-03-27, in force; DIN version 2025-04 | AENOR, genorma, DIN |
| Open EC3 libraries: Blueprints LGPL-2.1 (Dutch annex, formula library), steelsnakes in progress (2026-03), PySS 2020 | GitHub, readthedocs |
| AWC TR12 (generalized dowel yield equations) freely downloadable | awc.org |
| ASCE 7-22 Eq. 13.3-1 changed from 7-16 after ATC-120 / NIST GCR 18-917-43; 2025 CBC adopts it; no open implementation found | seblog.strongtie.com; hcai.ca.gov; enercalc.com |

## Kept out, with reasons

| Candidate | Reason |
| --- | --- |
| An electronics-enclosure thermal module | `thermal.py` already carries enclosure resistance networks, natural-convection enclosures and radiation networks; the ventilation and electrical packs exist. No gap large enough for a module. |
| A fluid-power module | `hydraulic_cylinder`, `hydraulic_motor`, `hydraulic_press`, `accumulator`, `pneumatics` exist; `hydraulics` pack exists. |
| A precision-motion module | `ball_screw`, `power_screw`, `living_hinge`, linear-guide checks in product screening, and performance budgets cover the screens; the stage-level question is `add-frame-analysis` stiffness plus budgets. |
| Statistical validation metrics (area metric, probabilistic) in the first credibility phase | Ratio and difference with a declared band are what reviewers read; richer metrics plug into the same record later. |
| Bundling any ASCE 7, IBC, NDS or Eurocode table | Copyrighted compilations; user-supplied with citation, as every pack does. |
| URL-mode elicitation | No hosted endpoint exists (D1); form mode is sufficient. |
| An IFC reader | The context intake reads STEP and DXF; reading IFC is a separate change once the writer exists. |
| anaStruct as a frame engine | License class; Pynite (MIT) is the referee and the in-house solve needs nothing. |

## Suggested sequencing

1. **Closes loops the doctrine already demands, pure Python:** `add-person-confirmation`
   → `add-model-credibility` → `add-service-life-planning` → `add-parts-as-code-ci`.
2. **The solve the structural changes share:** `add-frame-analysis`.
3. **Structural packs, parallelizable after 2:** `add-eurocode-steel-pack`,
   `add-walking-working-surfaces-pack`, `add-equipment-anchorage`,
   `add-timber-connections`.
4. **Handoff:** `add-ifc-structural-export`, after the packs it carries.

Full source URLs are in each change's `proposal.md` and `design.md`.
