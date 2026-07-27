# Change: Benchmarking against structured-spec suites and agent-driving evals

## Why

Two benchmark classes emerged in 2025–2026 that fit Anvilate exactly:

- **Structured-spec CAD benchmarks.** MUSE (https://arxiv.org/html/2605.28579) pairs
  structured Design Specifications with a three-stage funnel (execution → geometric
  validity → design-intent rubric); top closed models score ~31% on intent and ~20% on
  fine-grained engineering criteria. MUSE's spec format is convergent evolution with
  Anvilate's Spec IR — a deterministic spec-compiled pipeline should dramatically exceed
  that ceiling for in-scope parts, and publishing that comparison is a credibility
  headline.
- **Agent-tool-driving evals.** Eval suites are the credibility currency of 2026 agent
  tooling (CFDLLMBench for Foam-Agent; MCP-Bench for tool use). The question Anvilate
  users actually ask — "which local model can drive this reliably?" — is answerable only
  with an eval over Anvilate's own tool surface, with harness sensitivity documented.

The existing benchmarking spec already requires external benchmark evaluation generically;
this change names the structured-spec class and adds the agent-driving eval.

## What Changes

- `benchmarking`: the external-benchmark requirement is modified to include
  structured-spec suites (MUSE-class) with funnel metrics; a new requirement adds the
  agent-driving eval scoring model+client combinations against Anvilate's MCP tool
  surface, feeding the published local-model recommendation.

## Impact

- Affected specs: `benchmarking` (1 modified, 1 added requirement).
- Affected code (when implemented): AnvilateBench harness additions; licensing screen
  applies to any bundled tasks per the existing dataset-licensing requirement.
