# Capability research notes, wave 2 — 2026-07-27

Companion to `2026-07-27-capability-research.md` and the 13 additional OpenSpec change
proposals it produced (31 pending changes total). Three research sweeps (new discipline
verticals, cross-cutting capabilities, AI-agent landscape freshness) plus a re-audit of
`main` and all 20 accepted spec domains. Local working notes; not shipped documentation.

## The one-line synthesis

Wave 1 claimed the *evidence* moat. Wave 2 finds the gaps on either side of it: the
inputs that make a check honest (load combinations, code editions, finish/coating
callouts), the outputs that make it useful (Pareto fronts, physical test plans, carbon),
and the human and agent surfaces that decide whether any of it gets trusted.

## Audit findings that drove the portfolio

| Finding | Evidence | Change |
|---|---|---|
| Validation is strictly per-load-case; no factoring or combination exists anywhere in `specs/` — yet every cited code check assumes combinations | main-branch spec audit | `add-load-combinations` |
| Citations name clauses but not editions; the evidence bundle's whole claim is clause traceability | spec audit + fib `structuralcodes` edition-namespace prior art | `add-standards-effectivity` |
| `cost-estimation` covers per-part manufacturing cost only — no BOM, procurement, or carbon anywhere in the repo | spec audit | `add-embodied-carbon-screening` |
| Checks answer "does it pass," never "what is the lightest one that passes"; `agent-repair-loop` already owes Pareto alternatives with no engine behind it | spec audit | `add-design-space-exploration` |
| Surface finish, coating, and heat treat are check *inputs* Anvilate currently ignores; MBC 1.0 (ANSI-approved 2026) gives persistent characteristic identity | spec audit + DMSC | `add-typed-mbd-callouts` |

## New verticals: kept and killed

Four candidates survived; two were killed by maintained OSS, which is the correct outcome
of asking honestly.

| Vertical | Verdict | Basis |
|---|---|---|
| ASME BTH-1 lifting devices | **Kept** — best effort/value ratio | Zero OSS; spreadsheet-total; reuses shipped lug/spreader/rigging/weld primitives |
| Aluminum ADM 2020 | **Kept** | Zero OSS; 20 years of Eng-Tips threads answering "write your own spreadsheet"; mirrors the AISC pack architecture; ADM viewable free on ICC Digital Codes |
| ASCE 7-22 load combinations | **Kept** (as infrastructure, not a pack) | No OSS; the one PyPI package marketed for it does not exist — the promoting article is AI-generated slop (verified via PyPI 404) |
| FFS / fracture screening (SIF, FAD) | **Kept**, reframed | No maintained Python OSS (best prior art: FitnessForService.jl, dead 2021); framed as generic LEFM + open-literature FAD, *not* API 579 Level-1 figures |
| Weld fatigue detail categories | **Kept** | pyLife ships no FAT tables; fatpack has the curve math, nobody ships the cited category-selection step |
| Composite laminate (CLT/ABD) | **Killed** | composipy is maintained (last push 2025-12) and free web tools abound |
| Shaft/rotor critical speed | **Killed** as a pack | ROSS v2.1.0 (Petrobras-backed, 2026-02) and openTorsion both active; at most 2–3 screening functions in the existing module |
| Concrete anchorage (ACI 318 Ch. 17) | **Deferred** | Real OSS gap, but free vendor tools (Simpson, DeWalt) blunt it and post-installed anchor values are ESR-gated per product; the existing structural pack already covers cast-in breakout/pullout |

## Cross-cutting findings

- **Carbon data licensing is the whole design constraint.** EC3's API forbids commercial
  use and caching on the free tier ($5K–$50K/yr otherwise); the ICE database closes to
  non-educational use 2026-09-30. Both excluded. Clean path: openEPD schema (Apache-2.0)
  + Ökobaudat federal generic datasets with citable UUIDs. Granta's Eco Audit is the
  precedent that mass × cited factor is credible *as screening*.
- **EU DPP is infrastructure-only so far.** Registry went live 2026-07-19, but no
  product-specific delegated act is in force; iron & steel is the first targeted group
  (obligations ~2028-2030). Conclusion: build the honest estimate, ship no passport
  export until a delegated act defines one.
- **Check→physical-test emission has no prior art.** The pieces exist separately
  (INCOSE/SEBoK verification matrices, AS9102 ballooning, per-standard proof tests); the
  inversion — deriving the test plan from the calculation — is unclaimed.
- **QIF/MBC is the licensing gift of this space.** Free schemas, ANSI-approved persistent
  characteristic identity, and it is the substrate that links callout → check → inspection.

## Agent-landscape findings (late July 2026)

- **The constraint tax is real and threatens the local-first promise.** arXiv 2605.26128:
  hard schema-constrained decoding on 0.5B–1.7B models lifts validity 61.5%→100% while
  dropping accuracy 19.7%→11.0%, with wrong-but-valid outputs rising 49.5%→88.9%; tool-call
  executable accuracy 91.5%→48.0%. A schema-valid spec with the wrong load in it is worse
  than a malformed one, because validation cannot catch it. Mitigation: two-pass "reason
  free, constrain late," and never collapse validity and correctness into one score.
- **Skills standardized.** SKILL.md open-standardized Dec 2025, compatible implementations
  across most major agent products by March 2026; AGENTS.md is the de facto repo
  convention. Shipping a first-party skill is the cheapest lever on correct third-party use.
- **Responsible charge is now adjudicated.** NSPE Board of Ethical Review found failing to
  maintain responsible charge over AI output before sealing unethical ("AI = engineering
  intern"); Position Statement 03-1774 requires at least equal scrutiny for AI-generated
  work. Approval-UX conventions converge on what a reviewer must see; AI-generated PRs
  wait 4.6× longer for review pickup.
- **EU AI Act timing moved.** June 2026 Digital Omnibus pushed stand-alone Annex III
  high-risk duties to 2027-12-02 (Annex I to 2028-08-02); Article 50 transparency still
  applies from 2026-08-02.
- **Corroborating architecture evidence:** "Embodied CAD" (2606.31252) validates typed ops
  + exact-kernel feedback with an L0–L4 skill stratification; EngiAI (2605.19743) measures
  proprietary models at 96–97% task completion vs 55–78% for open 4B models — a concrete
  local-model gap number; the LLM-DSE literature converges on "model proposes, deterministic
  engine disposes."
- **Incumbents:** Onshape Labs launched 2026-07 with AI drawing checks; FreeCAD 1.1 shipped
  with no AI features (all AI arriving via third-party MCP servers); SOLIDWORKS AURA
  shipped alongside LEO. No new OSS text-to-CAD entrant of substance.

## Explicit rejections (researched, declined)

- Composite laminate and rotordynamics packs — maintained OSS already serves both.
- Bundling EC3 or ICE carbon factors — license-prohibited.
- Reproducing API 579 Level-1 screening curves or brittle-fracture exemption figures —
  standard-text redistribution; generic LEFM + FAD from open literature instead.
- Detail-category *inference* from weld geometry — the user declares it, as with any
  allowable.
- A Digital Product Passport export — premature until a delegated act specifies one.
- Bayesian optimization as the default trade-study engine — wrong tool for microsecond
  closed-form evaluations; seeded exhaustive/Sobol sweep with exact Pareto extraction is
  faster, reproducible, and auditable.
- Jurisdiction-to-code mapping as an authoritative source — shipped only as dated,
  advisory, user-confirmed data, if at all.

Full source URLs are in each change's `proposal.md`.
