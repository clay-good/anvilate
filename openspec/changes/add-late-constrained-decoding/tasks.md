# Tasks: Reason free, constrain late

## 1. Implementation

- [ ] 1.1 Two-pass compilation: unconstrained reasoning, constrained packaging
- [ ] 1.2 Provenance capture of reasoning output and pass configuration
- [ ] 1.3 Single-pass fallback path, recorded when used

## 2. Evaluation

- [ ] 2.1 Versioned compilation task set with reference specs
- [ ] 2.2 Separate metrics: schema validity, field-level correctness, wrong-but-valid rate
- [ ] 2.3 Gate the published local-model recommendation on all three

## 3. Tests

- [ ] 3.1 Reasoning output never reaches downstream stages
- [ ] 3.2 Metric separation asserted; a synthetic wrong-but-valid case is counted as a
      defect
- [ ] 3.3 Schema field-name change triggers the evaluation gate in CI

## 4. Docs

- [ ] 4.1 Explanation page: why a valid spec can still be the wrong spec, and what the
      spec card confirmation step is for
