# Change: Verification planning — every check emits its physical-test counterpart

## Why

A screening check says a lug will hold; a proof test proves it. Today Anvilate stops at
the calculation, leaving the user to invent the verification plan that the calculation
implies — and the standards Anvilate cites often prescribe that test explicitly (a BTH-1
lifter's proof load, an AS9102 first-article characteristic list, weld NDE per the
governing category, preload verification for a torqued joint).

This is a genuinely open niche. The systems-engineering canon has the vocabulary
(Analysis / Inspection / Demonstration / Test verification matrices — SEBoK,
https://sebokwiki.org/wiki/System_Verification), domain generators exist for narrow cases
(a free DO-160G test-plan generator, https://app.do160.org/), and the FAI ballooning
market automates characteristic accountability — but nothing derives a physical
verification plan *from analysis results*. Inverting the requirements-verification matrix
(from calculation to test, rather than from requirement to method) is a capability nobody
ships, and it lands naturally in the evidence bundle Anvilate already produces.

It also completes the responsible-charge story: an engineer sealing work wants the
analysis and the verification that backs it in one dossier.

## What Changes

- New capability spec `verification-planning`: a deterministic, table-driven mapping from
  check classes to test archetypes; emitted test items carrying the driving check, the
  cited test method, pass criteria derived from the check's own allowable, and required
  instrumentation accuracy; a verification matrix in the evidence bundle with explicit
  coverage reporting including checks that map to no test; and a firm rule that a planned
  test is never evidence until its result is recorded.

## Impact

- Affected specs: new `verification-planning`. Interacts with `artifact-export` (bundle
  section), `add-quality-evidence-interchange` (dimensional items are the natural QIF
  characteristics), `add-uncertainty-margins` (instrumentation accuracy), and
  `add-lifting-device-pack` (proof tests) — none change.
- Affected code (when implemented): a check-class-to-test-archetype registry and a plan
  emitter over scorecard entries.
- Out of scope: test execution, lab data acquisition, and any claim of qualification or
  certification testing.
