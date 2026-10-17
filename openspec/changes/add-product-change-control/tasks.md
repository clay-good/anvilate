# Tasks: Product change control

Depends on `add-product-structure`, `add-interface-contracts`, `add-release-package`, and
the STEP reader from `add-agent-context-intake`.

## 1. Diff

- [ ] 1.1 Item-by-item comparison of two products, or a product against a release
      manifest
- [ ] 1.2 Change kinds: parameters, geometry deltas, interfaces, ratings, identity,
      verdicts
- [ ] 1.3 Form/fit/function classification with evidence; new-number vs revision flags

## 2. Reach

- [ ] 2.1 Where-used paths across the product and its variants
- [ ] 2.2 Affected files from the baseline manifest

## 3. Record and gate

- [ ] 3.1 Change record, Markdown and JSON; reason missing marked
- [ ] 3.2 Release refusal for changed content under an unchanged revision
- [ ] 3.3 Identical regeneration of unchanged content gated in CI

## 4. Existing assemblies

- [ ] 4.1 STEP assembly tree reader: names, placements, envelopes, duplicate names
- [ ] 4.2 Reference items: mates, interference and clearance; excluded from made outputs
- [ ] 4.3 A docs page for changes: comparing revisions, reading the record, designing against
      an existing machine
