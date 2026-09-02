# Tasks: Render a verdict line in the reader's units

## 1. Decide

- [x] 1.1 The comparison **replaces the authored sentence**: `detail` is written *from* the
      numbers at the moment the entry is built, exactly as `from_safety_factor` has always
      done. One source, and every existing reader — the CLI, the evidence bundle, the QIF
      export, the README's own quickstart output — still finds the sentence it has always
      found. A field beside `detail` would have put two statements of one fact on one
      object, which is the failure this repository has found in citations, in materials
      counts and in derivation coverage.

## 2. The type

- [x] 2.1 `Comparison`: what was measured, what it was judged against, which direction
      passes, the two labels, and a precision floor. One-sided only — the two builders
      that need it compare against a single limit, and a band is not a shape anything asked
      for.
- [x] 2.2 Refused when the two quantities are of different dimensions. A length judged
      against a frequency is not a comparison, and the rendered sentence would give it the
      appearance of one: two numbers, a "vs", and a unit that changed between them.

## 3. The builders

- [x] 3.1 `deflection_scorecard` (`anvilate.analysis.beam`)
- [x] 3.2 `frequency_scorecard` (`anvilate.analysis.dynamics`)
- [x] 3.3 **Not a comparison, and the proposal was wrong to list it.** The BTH-1 line the
      sweep found is an *identification* line — rated load, self weight, design load,
      Category — which states four quantities and judges none. It carries an `Underived`
      saying exactly that. Its other two baked units sit on entries whose verdict is
      already the safety-factor sentence.
- [x] 3.4 **Not a comparison either.** The callout line reads `k_a = 0.689 at S_u = 1200
      MPa`: a factor and the strength it was read at, not a value against a limit. The
      strength is deliberately a bare number in MPa, because the Marin fit's constants are
      quoted for that unit and converting it would make the formula beside it wrong.

## 4. The report

- [x] 4.1 `ReportSection.verdict(system=…)` restates the comparison in the document's own
      units and falls through to `detail` for everything else — a safety-factor line, a
      refusal, an identification line.
- [x] 4.2 `tests/test_rendered_lines.py` holds the verdict to the same rule as the
      derivation: no line may carry a unit from a system the document did not declare. The
      report ignoring the comparison fails it, and so does a screen dropping it.

## 5. Contract

- [x] 5.1 Scorecard schema 1.6.0, frozen, with the MCP tool reference moved. The bundle
      digest moved with it, and the pin says why.

## Status

Shipped. A US-customary report now reads `deflection 0.117 in vs limit 0.630 in` under a
derivation in inches, where it read `2.963 mm` before.

Two of the four builders the proposal named turned out not to compare anything. The sweep
that found them looked for a formatted number beside a unit word, which is the shape of a
comparison and also the shape of an identification line — worth remembering, because the
same sweep is the obvious way to look for the next one.
