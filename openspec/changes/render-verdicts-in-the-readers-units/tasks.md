# Tasks: Render a verdict line in the reader's units

## 1. Decide

- [ ] 1.1 Whether the comparison **replaces** `detail` — the sentence derived from the
      numbers in the constructor, as `from_safety_factor` already does — or sits beside it.
      **Blocking**: beside it puts two statements of one fact on the same object, and this
      repository has found that failure three times.

## 2. The type (follows 1.1)

- [ ] 2.1 What was measured, what it was judged against, and which direction passes. A
      one-sided limit is the only shape the four builders need; a band is not.
- [ ] 2.2 Refused when the two quantities are of different dimensions, because a comparison
      between a length and a frequency is not a comparison.

## 3. The four builders

- [ ] 3.1 `deflection_scorecard` (`anvilate.analysis.beam`)
- [ ] 3.2 `frequency_scorecard` (`anvilate.analysis.dynamics`)
- [ ] 3.3 The BTH-1 identification line (`anvilate.analysis.lifting_device`)
- [ ] 3.4 The callout roughness comparison (`anvilate.callouts`)

## 4. The report

- [ ] 4.1 `ReportSection` renders the sentence from the comparison under the document's
      unit system, falling back to `detail` where there is none.
- [ ] 4.2 Extend `tests/test_rendered_lines.py`'s corpus to the verdict line, which is the
      gate this change exists to satisfy: no line in a document may carry a unit from a
      system the document did not declare.

## 5. Contract

- [ ] 5.1 Bump and freeze the scorecard schema; move the MCP tool reference with it.

## Status

Not started. Written rather than half-built: the field is an hour and the decision in 1.1
is not, and a second statement of the same fact is harder to remove than to add.
