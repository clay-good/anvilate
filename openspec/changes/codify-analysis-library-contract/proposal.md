# Change: Codify the analysis-library contract

## Why

The analysis library is Anvilate's shipped product today — ~495 public symbols across ~50
modules, 1,100+ tests, 138 CI-run examples — yet no spec domain governs it. Its de-facto
rules (every check cites its source, every function is unit-typed, worked examples anchor
tests, user-supplied allowables are guardrail-safe) live in convention and project memory,
not in a capability spec. The README teaches the Python API as the primary interface, but
nothing specifies its stability.

External context sharpens the need: the StructuralPython ecosystem
(https://github.com/orgs/StructuralPython/repositories) is Anvilate's exact adopter
profile and consumes libraries with stable contracts; the "LLM plans, deterministic code
resolves numbers" pattern now validated across 2026 research (Embodied CAD,
https://arxiv.org/abs/2606.31252) makes the deterministic library the load-bearing asset
worth spec-protecting.

## What Changes

- New capability spec `analysis-library` codifying: the citation contract, the unit-typed
  API, worked-example regression, the design-inverse pairing contract, the runnable
  example contract, public-API stability (semver + deprecation), and the user-supplied
  allowables doctrine (copyrighted table values are never bundled; user-supplied
  coefficients carry user provenance).

## Impact

- Affected specs: new `analysis-library` capability. This is largely codification of
  existing practice — most requirements are already met by the code; the spec makes them
  enforceable and contributable-against.
- Affected code (when implemented): CI additions (citation coverage, example coverage,
  deprecation policy checks); no behavioral changes to existing functions.
- Future changes (interop, thermal/isolation screening) attach to this domain.
