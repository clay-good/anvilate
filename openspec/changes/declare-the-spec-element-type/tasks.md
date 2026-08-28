# Tasks: Let a Design Spec say what kind of element it is

## 1. Decide

- [ ] 1.1 Choose between the typed discriminated union (A), the tagged parameter map (B),
      and conceding the boundary (C). **This is the blocking task.** A and B trade the same
      thing in opposite directions — whether the published Spec IR schema is allowed to know
      what a lifting lug is — and answering it wrong is expensive once a client has parsed
      against the schema.

## 2. Contracts (follows the decision)

- [ ] 2.1 The element declaration on `DesignSpec`, and the Design Spec schema version bump
      it forces, with what a client pinned to `1.1.0` is owed written down.
- [ ] 2.2 The `mcp` tool schemas re-point at the new version — the references are literals
      on purpose, so this fails `catalog_issues()` until someone re-reads them.

## 3. Implementation

- [ ] 3.1 `screen_spec` selects and runs the pack screen, and the T1 entry becomes a verdict
      instead of the standing gap.
- [ ] 3.2 An element the resolver does not know stays `not_evaluated` naming it, never a
      pass — the same rule the material and callout layers already follow.

## Status

Not started, and the gap is enforced rather than assumed: `screen_spec` emits a
`not_evaluated` T1 entry on every spec naming this exact reason, `docs/spec-screening.md`
says so in prose, and `tests/test_screening.py` pins the wording. Nothing reads green while
this is open.
