# Tasks: Reason free, constrain late

## 1. Implementation

- [ ] 1.1 Two-pass compilation: unconstrained reasoning, constrained packaging — needs the
      compiler, which is unbuilt
- [ ] 1.2 Provenance capture of reasoning output and pass configuration — the *configuration*
      half is done: `CompilationReport` refuses to exist without stating how it was decoded,
      because validity and accuracy both move with the pass structure and a number without
      its configuration cannot be compared with another one. Capturing the reasoning output
      itself needs the compiler
- [ ] 1.3 Single-pass fallback path, recorded when used — follows 1.1

## 2. Evaluation

- [x] 2.1 Versioned compilation task set with reference specs — `CompilationTask` is the
      format: a prompt plus the spec *fields* a correct compilation must carry, deliberately
      not a whole reference spec, because two correct compilations can differ in the parts
      nobody stated and scoring against a full document would count a compiler wrong for
      filling a default differently. A task stating no reference fields is refused: every
      output would score fully correct, including an empty one. The corpus itself is not
      written — a task set is a claim about what the compiler should have understood, and
      writing one before the compiler exists would be writing it against nothing
- [x] 2.2 Separate metrics: schema validity, field-level correctness, wrong-but-valid rate —
      and **no fourth number that averages them**. `CompilationReport` has no `score`, no
      `success_rate` and no `passed`; a contract test asserts none can be added. A scalar
      over a constrained decoder is dominated by validity, the number constraint drives to
      100%, so it rises while the thing a user cares about falls
- [ ] 2.3 Gate the published local-model recommendation on all three — there is no published
      recommendation yet, and gating one that does not exist is not a thing that can be done

## 3. Tests

- [ ] 3.1 Reasoning output never reaches downstream stages — follows 1.1
- [x] 3.2 Metric separation asserted; a synthetic wrong-but-valid case is counted as a defect
      — a legal `DesignSpec` that read 50 kN as 50 kip scores `schema_valid` True,
      `wrong_but_valid` True, and is named by `wrong_but_valid()` rather than only counted.
      Also pinned: an omitted field counts against correctness, an unparseable candidate
      scores zero fields rather than no fields, and a task nobody attempted is an error
      rather than an omission
- [ ] 3.3 Schema field-name change triggers the evaluation gate in CI — follows a task corpus

## 4. Docs

- [x] 4.1 Explanation page: why a valid spec can still be the wrong spec, and what the spec
      card confirmation step is for — `docs/valid-is-not-correct.md`. The confirmation step
      itself is the existing draft-until-confirmed flow in `anvilate.ingest`, which the page
      does not restate

## Note

The compiler is unbuilt, so what shipped is the measurement vocabulary rather than the
thing measured. That order is deliberate: a compiler shipped against a metric that hides
the wrong-but-valid case would look like it was improving as it got worse.
