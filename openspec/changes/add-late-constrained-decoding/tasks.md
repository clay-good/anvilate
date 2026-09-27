# Tasks: Reason free, constrain late

## 1. Implementation

- [x] 1.1 Two-pass compilation: unconstrained reasoning, constrained packaging —
      `compile_intent` injects the model backend, calls its unconstrained reasoning pass once,
      and supplies the exact Design Spec schema to each constrained packaging attempt. Only
      a candidate accepted by `parse_spec` is returned (`tests/test_compilation.py`)
- [x] 1.2 Provenance capture of reasoning output and pass configuration —
      `CompilationProvenance` retains the reasoning separately from the typed spec and names
      the backend, model, pass shape, schema version, retry budget, attempts, and validation
      failures. `CompilationReport` continues to require the evaluation configuration
- [x] 1.3 Single-pass fallback path, recorded when used — a backend declaring no two-pass
      support skips reasoning, still packages under the schema, and records
      `single_pass_fallback`; it can never be mistaken for a two-pass run

## 2. Evaluation

- [x] 2.1 Versioned compilation task set with reference specs — `CompilationTask` is the
      format: a prompt plus the spec *fields* a correct compilation must carry, deliberately
      not a whole reference spec, because two correct compilations can differ in the parts
      nobody stated and scoring against a full document would count a compiler wrong for
      filling a default differently. A task stating no reference fields is refused: every
      output would score fully correct, including an empty one. Now that the compiler
      boundary exists, `default_compilation_task_set()` supplies version 1.0.0: six tasks
      across structural, mechanical, timber, hydraulic, and tolerance intent. Every dotted
      reference is gated against the published Design Spec or selected pack-element schema
- [x] 2.2 Separate metrics: schema validity, field-level correctness, wrong-but-valid rate —
      and **no fourth number that averages them**. `CompilationReport` has no `score`, no
      `success_rate` and no `passed`; a contract test asserts none can be added. A scalar
      over a constrained decoder is dominated by validity, the number constraint drives to
      100%, so it rises while the thing a user cares about falls
- [ ] 2.3 Gate the published local-model recommendation on all three — there is no published
      recommendation yet, and gating one that does not exist is not a thing that can be done

## 3. Tests

- [x] 3.1 Reasoning output never reaches downstream stages — the result keeps provenance
      beside the `DesignSpec`, never inside it. A sentinel test screens the returned spec and
      proves the private reasoning appears in neither the spec nor the scorecard
- [x] 3.2 Metric separation asserted; a synthetic wrong-but-valid case is counted as a defect
      — a legal `DesignSpec` that read 50 kN as 50 kip scores `schema_valid` True,
      `wrong_but_valid` True, and is named by `wrong_but_valid()` rather than only counted.
      Also pinned: an omitted field counts against correctness, an unparseable candidate
      scores zero fields rather than no fields, and a task nobody attempted is an error
      rather than an omission
- [ ] 3.3 Schema field-name change triggers the evaluation gate in CI — the corpus half is
      now live: `task_set_issues()` makes a stale Spec IR or pack-element field fail CI and
      adversary tests prove both directions. This remains open because a real model run and
      its correctness delta still need an external harness; path validity is not evaluation

## 4. Docs

- [x] 4.1 Explanation page: why a valid spec can still be the wrong spec, and what the spec
      card confirmation step is for — `docs/valid-is-not-correct.md`. The confirmation step
      itself is the existing draft-until-confirmed flow in `anvilate.ingest`, which the page
      does not restate

## Note

The orchestration contract and the first versioned task corpus are built; model adapters are not.
That boundary is deliberate: Anvilate supplies the schema, validation, retries, provenance,
and pass isolation without choosing a local server or initiating a cloud call. The
measurement vocabulary shipped first so a compiler could not look better by hiding the
wrong-but-valid case.
