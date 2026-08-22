# The published contracts: Spec IR and scorecard as JSON Schema

**Anvilate's input and its output are now documents anything can validate, without
importing Python.**

The two load-bearing data contracts are the Design Spec IR going in and the scorecard
coming out. As Python classes they are only checkable from Python; as JSON Schema 2020-12
they are checkable by a CAD add-in, a CI job, or an MCP client that has never heard of
anvilate.

| Artifact | What it describes | Version |
| --- | --- | --- |
| [`docs/api/schemas/design-spec.schema.json`](api/schemas/design-spec.schema.json) | the typed part description the pipeline consumes | the same number a spec file states in `anvilate_spec` |
| [`docs/api/schemas/scorecard.schema.json`](api/schemas/scorecard.schema.json) | one typed result per check, with the rolled-up status | `1.0.0` |

```python
from anvilate.contracts import freeze_release, scorecard_json_schema, write_schemas
```

`write_schemas` regenerates the published artifacts; `freeze_release` cuts a version, once.

2020-12 specifically, because that is the dialect the MCP tool-schema contract expects —
which is why these exist in this form rather than as an ad-hoc dump.

## Generated, never written

A hand-written copy of a live model is a document that is wrong the first time somebody adds
a field. Both artifacts come out of the models themselves, in serialization mode: the
published contract is what Anvilate *writes*, and a schema built from the input side would
describe the coercions pydantic accepts rather than the document a consumer receives.

## The gate has two halves, and the second one is the point

Drift is the obvious failure: a model changes, the artifact does not, and the schema
describes a document nobody produces. That half is a byte-for-byte comparison.

The other half is invisible from outside. **A contract whose content changes while its
version stays put is a silent breaking change**: a client pinned to `1.1.0` fetches a
different document under the same identifier and has no way to know.

The first attempt at that half did not work, and the way it failed is worth keeping. It
compared the checked-in artifact against a freshly generated one — which is *already* the
drift check, so the version assertion could only be reached from a state that was red for
another reason. The moment an author did what the drift failure told them to do, both halves
went green with the version untouched. An audit removed a required property from the
scorecard contract, regenerated exactly as instructed, and shipped it under
`.../scorecard/1.0.0.json` with the suite green.

**A gate whose failing condition is already covered by another gate is not a gate.** So a
released version's content is frozen once, in its own file under
[`docs/api/schemas/released/`](api/schemas/released/), and never regenerated. The comparison
is against that. Changing what a released version means now requires deleting a frozen file —
a deliberate act visible in a diff, rather than the natural consequence of following an error
message — and `freeze_release` refuses to overwrite a frozen version, so the hole cannot
reappear one function call further away.

`$id` carries the version, so the identifier and the document cannot disagree.

## The tri-state is in the contract

`CheckStatus` publishes all four values — `pass`, `fail`, `over_margin`, `not_evaluated` —
so a client reading the schema cannot model the result as a boolean without noticing what it
is dropping. That is the same rule the library follows, moved to the one place a consumer
who never reads the docs will still see it.

## Checking a schema

`schema_issues(schema)` does the checks that need no validator library: the dialect and
identifier are declared, the identifier carries the version the document states, and every
internal `$ref` resolves to a definition that is present. A dangling `$ref` is the failure
mode of a schema assembled from models — a type referenced but never inlined — and it
produces a document that looks complete and validates nothing.

Meta-schema validation needs a validator, and `jsonschema` is a **dev** dependency rather
than a runtime one, because it checks what Anvilate emits rather than anything Anvilate
needs to run. CI installs it, so both the meta-schema check and a round trip — a scorecard
the library actually produced, validated against the published contract — run on every push
to `main` and on every pull request, rather than skipping the way an opt-in check would.

## What is not published yet

Tool definitions. These are the schemas a tool contract would point at; mapping pipeline
operations onto MCP tools is
[`modernize-mcp-server`](../openspec/changes/modernize-mcp-server/tasks.md) task 1.2, and
the server itself is unbuilt.
