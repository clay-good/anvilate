# Change: Reviewable calculation reports — show the work, not just the verdict

## Why

Anvilate's scorecard states verdicts; its evidence roll-up states provenance. Neither
renders the *worked calculation* — formula, substituted values, result — that a checker,
an engineer of record, or a permitting jurisdiction actually reviews. That artifact is the
single most-validated missing capability found in research:

- handcalcs (~6k stars) exists purely to render Python as symbolic → substituted → result
  derivations (https://github.com/connorferster/handcalcs); efficalc was built by a
  structural engineer specifically for submittal-ready PDF reports with code references
  (https://github.com/youandvern/efficalc).
- Calcs.com's entire commercial pitch is a report where every formula carries the specific
  governing clause, formatted for permit submission (https://calcs.com/features/structural-report).
- Jurisdiction submittal norms are unambiguous: paginated PDF with project header, code
  editions, assumptions, then member checks with clause references
  (https://www.enginedge.com/how-to-format-structural-calculations/).
- Mathcad refugees (subscription pricing, files unreadable across versions —
  https://www.eng-tips.com/threads/things-you-love-hate-with-mathcad.525360/) are leaving
  the one tool whose virtue was readable math; nothing open-source and local-first replaces it.

Anvilate already computes every number in a typed unit system with citations attached. The
gap is purely the emitter — and a machine-readable calc record alongside it makes Anvilate
the verifiable substrate that the emerging "AI checks your calcs" tools check against.

## What Changes

- New capability spec `calculation-report`: every check can render a worked derivation
  (symbolic formula → numeric substitution → result, in the project unit system, with its
  citation), assembled into a submittal-shaped HTML/PDF document and a stable
  machine-readable JSON calc record.
- Derivation metadata (symbolic form, variable glossary) becomes part of the check
  contract; a check without derivation metadata renders inputs/outputs in tabular
  fallback and is flagged in CI.
- Rendering is deterministic, offline, and pure-Python (no TeX toolchain dependency).

## Impact

- Affected specs: new `calculation-report` capability. Touches the contracts described in
  `validation-gauntlet` (scorecard entries gain derivation references), `artifact-export`
  (the report joins the evidence bundle), and `units-and-quantities` (rendering precision
  rules apply).
- Affected code (when implemented): a derivation-metadata registry over
  `src/anvilate/analysis/`, a renderer package, scorecard/evidence serialization.
- No behavior change to any existing check verdict; purely additive output surface.
