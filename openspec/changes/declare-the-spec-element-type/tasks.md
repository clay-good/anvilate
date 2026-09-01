# Tasks: Let a Design Spec say what kind of element it is

## 1. Decide

- [x] 1.1 Choose between the typed discriminated union (A), the tagged parameter map (B),
      and conceding the boundary (C). **Answered: B**, by the user, on 2026-08-31. The
      deciding argument was the one the proposal names — a union makes `spec-ir` depend on
      all twenty-odd packs, so every new pack element becomes a bump to the published Design
      Spec schema *and* to the MCP tool contracts that reference it at its version.

## 2. Contracts

- [x] 2.1 `element_type` and `element_params` on `DesignSpec`; Design Spec schema to
      **1.2.0**, with 1.1.0 frozen and unchanged, so a client pinned to it receives what it
      always did.
- [x] 2.2 The `mcp` tool schemas re-point at 1.2.0. The references are literals on purpose
      and `catalog_issues()` refused the catalog until they were re-read, which is the gate
      working.
- [x] 2.3 B's cost paid rather than waved through: each pack element's own schema is
      published under `docs/api/schemas/elements/<tag>.schema.json`, addressed by the same
      tag a document writes, generated from the same registry the screen resolves through,
      and frozen and drift-gated like the two named contracts. Versioned as a set at first,
      and stated on the page rather than left to be discovered; 4.1 has since made the
      versions per element.

## 3. Implementation

- [x] 3.1 `screen_spec` selects and runs the pack screen, and the T1 entry is a verdict
      rather than the standing gap. The registry is **derived** from the packs — every
      `screen_*` whose first argument is a typed element, keyed by that model's name in
      snake case — so a pack ships a new element by existing. 23 elements, 23 distinct tags.
- [x] 3.2 Every way of failing to reach the pack stays `not_evaluated` naming it: an unknown
      tag (with the near miss suggested), parameters the element's own model refuses (with
      the pack's message quoted), and a screen that needs a required safety factor the spec
      does not state.

## 4. Still open

- [x] 4.1 Per-element schema versions. Each element now carries its own: a tag absent from
      `ELEMENT_SCHEMA_VERSIONS` publishes at `ELEMENT_SCHEMA_INITIAL_VERSION`, so a pack
      still ships an element by existing, and bumping one moves that `$id` and no other. The
      gate is on the blast radius — bump one tag and every other document must come back
      byte for byte identical — because the shared constant made every version agree by
      construction, which is why nothing failed while it was wrong. A pin naming a tag no
      pack registers is refused, so a rename cannot leave a bump silently not applying.
- [ ] 4.2 `screen_structure` takes a *list* of members rather than one element, so it is not
      addressable by a single tag. A spec describing a whole structure still cannot name it.

## Status

The main path works: `anvilate check` on a YAML document returns cited ASME BTH-1 checks for
a padeye. `docs/spec-screening.md` shows the block and a test screens it rather than reading
it.
