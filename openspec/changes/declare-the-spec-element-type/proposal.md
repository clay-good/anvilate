# Change: Let a Design Spec say what kind of element it is, or say screening stops at T2

## Why

`anvilate.screening.screen_spec` closed the gap between a compiled spec and a scorecard —
and writing it found what that gap actually was.

**A `DesignSpec` cannot say what kind of structural element the part is.** It states a
material, a process, interfaces, dimensions, tolerances, loads and acceptance criteria.
Every one of the twenty-odd discipline-pack screens takes a *typed element* instead — a
`LiftingLug`, a `PipeRun`, a `ShallowFooting` — built by hand, with its own required fields.
Nothing in the IR selects between them.

So the T1 analytical tier reports `not_evaluated` on **every** spec, with that reason, and
will keep doing so however much analysis is written. The library's whole T1 surface — 236
closed-form modules, the thing a user comes for — is unreachable from a spec document.

This is not a missing feature in the screen. It is a missing field in a published schema.

## What Changes

- `spec-ir` gains a way for a spec to declare the element it describes, so a screen can be
  selected from the document rather than guessed at.

Three options were considered.

**A. A typed `element` discriminated union.** `element: LiftingLug | BeamMember | PipeRun |
...`, discriminated on a literal tag, each variant carrying exactly the fields its screen
requires. Validation is total: a lug missing its pin diameter fails at parse rather than at
screen time. The cost is that the IR grows a dependency on every pack, and every new pack
element is a spec-schema change — the `spec-ir` and `analysis-library` surfaces stop being
independently versionable.

**B. A tagged `element_type` plus an untyped parameter map.** `element_type: "lifting_lug"`
and `element_params: {...}`, resolved to the pack's model at screen time. The IR stays
independent of the packs and a new element ships without a schema bump. The cost is that a
malformed element is caught at screening rather than at parse, and the published schema
stops describing what a valid document contains — which is most of what publishing it buys.

**C. Neither: say the boundary out loud.** Record that a Design Spec screens through T0/T2
only, that T1 is reached by constructing a pack element, and stop reporting T1 as a gap on
every spec. Cheapest, and it concedes the pipeline the specs describe.

**No recommendation is made here.** A and B trade the same thing in opposite directions —
whether the published Spec IR schema is allowed to know what a lifting lug is — and that is
a question about what Anvilate's data contract *is*, not an implementation detail. It is
the user's to answer.

## Impact

- Affected specs: `spec-ir` (1 requirement), and consequentially `validation-gauntlet`'s T1
  scenario, which today cannot be reached from a document at all.
- Affected code: `anvilate.spec.ir`, `anvilate.screening`, the published Design Spec JSON
  Schema (a version bump under the two-halves gate in `docs/published-contracts.md`), and
  the `mcp` tool schemas that `$ref` it at their version.
- The cost of waiting is bounded and stated: `screen_spec` names the gap on every card
  today, so nothing is silently wrong while the decision is open.
