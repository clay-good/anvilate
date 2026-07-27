# Change: Fitness-for-service fracture screening — SIF, reference stress, FAD

## Why

Crack-like flaw assessment is the widest commercial price umbrella surveyed: practice is
split between expensive seat-licensed suites (Codeware INSPECT, TWI IntegriWISE) and
field Excel, and there is no maintained open-source implementation in Python — the best
prior art is a dead Julia package (FitnessForService.jl, last push 2021). The underlying
math is exactly Anvilate-shaped and license-clean when framed correctly: handbook stress
intensity factor solutions are NASA public-domain reports (Newman–Raju,
https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/19840015857.pdf), and the Level-2
failure assessment diagram curve is the R6/BS 7910 expression ubiquitous in open
literature. The shipped `fracture` module already has K, critical crack length, and
Paris growth — this adds the assessment layer that turns those primitives into a verdict.

The framing is deliberately *generic LEFM + FAD screening citing the assessment codes*,
not a reimplementation of API 579 Part 9 Level 1: the Level-1 screening curves and
brittle-fracture exemption curves are figures inside the copyrighted standard and are
not reproduced.

## What Changes

- One ADDED requirement to `analysis-library` (depends on
  `codify-analysis-library-contract`): a fracture screening set — named handbook SIF
  solutions with enforced validity ranges, reference-stress plastic collapse, FAD
  assessment-point placement with margin along the load line, user-supplied toughness
  with estimate-labeled Charpy correlations, and hard screening/qualification framing.

## Impact

- Affected specs: `analysis-library` (one ADDED requirement; the contract requirements
  it inherits — citations, unit-typed API, worked-example anchoring, inverses,
  user-supplied allowables — are unchanged).
- Affected code (when implemented): extends `analysis/fracture.py`; composes existing
  stress functions for reference stress.
- Explicitly out: API 579 Level-1 screening figures, weld-residual-stress profiles
  beyond user-supplied values, and any "fit for continued service" wording — verdicts
  are screening margins for a qualified assessor.
