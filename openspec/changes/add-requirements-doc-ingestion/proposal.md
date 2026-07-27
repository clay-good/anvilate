# Change: Requirements-document ingestion

## Why

Engineers start from requirement sheets, not chat. Leo AI's traction with spec-document
ingestion (https://www.getleo.ai/) and VFEAgent's extract-a-typed-spec-first pattern
(https://arxiv.org/abs/2605.28978) both show the front door for real work is an existing
document: a customer requirement sheet, an RFQ table, an internal design brief. Anvilate's
input-ingestion capability covers datasheets (component dimensions) but not requirement
documents (loads, environments, constraints, acceptance criteria) — a different extraction
target with the same governing rule: extracted values are drafts until confirmed.

## What Changes

- `input-ingestion` gains a requirement: local extraction of candidate spec fields (loads,
  masses, environments, materials, interfaces, constraints) from requirement-class
  documents into a *draft* Spec IR, with per-value source locations, per-value
  confirmation, and document provenance — no extracted value becomes load-bearing
  unconfirmed, identical in spirit to the datasheet flow.

## Impact

- Affected specs: `input-ingestion` (1 added requirement).
- Affected code (when implemented): reuses the local PDF extraction stack and the
  confirmation flow; adds a requirements-oriented extraction pass and draft-spec
  assembly.
