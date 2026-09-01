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
| [`docs/api/schemas/scorecard.schema.json`](api/schemas/scorecard.schema.json) | one typed result per check, with the rolled-up status | `1.1.0` |

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

## The pack elements publish their own schemas

`DesignSpec.element_params` is an untyped map, which is what keeps the Spec IR from
depending on twenty-odd discipline packs — and what it trades away is a published contract
that describes a *complete* document. These are the other half of that trade:
[`docs/api/schemas/elements/`](api/schemas/elements/) carries one schema per element,
addressed by the same tag a document writes, so a client can validate what it is about to
send without the Spec IR having to know what a lifting lug is.

```
https://anvilate.dev/schemas/elements/lifting_lug/1.0.0.json
```

They are generated from the same registry the screen resolves through, so an element that
ships is an element that is published, and a gate holds the two sets equal in both
directions — an element with no schema is a document a client cannot check, and a schema
with no element is a tag that resolves to nothing. That includes `structure`, the composite
element a document names to describe a whole assembly, which is registered by the screening
module rather than by a pack and published on the same terms as the rest.

They are frozen and drift-gated exactly like the two contracts above, and **each element
carries its own version**. A new element publishes at `ELEMENT_SCHEMA_INITIAL_VERSION`, so a
pack still ships an element by existing; bumping one means adding its tag to
`ELEMENT_SCHEMA_VERSIONS`, and that edit moves that one `$id` and no other. A client pinned
to `bolted_connection/1.0.0` is not told its contract moved because a pump duty gained a
field. What none of it does is move `SPEC_SCHEMA_VERSION`, which is the coupling the tag
exists to avoid.

### 1.1.0: the contract said "with the rolled-up status" and did not carry one

The scorecard schema described `entries` and nothing else, because `Scorecard.status` was a
plain Python property and a plain property does not serialize. The document a consumer
receives — the attested `scorecard.json`, the `scorecard` inside a signed predicate,
`anvilate check --format json` — was the checks with no verdict on them.

**The roll-up is not a maximum**, which is what makes that dangerous rather than
inconvenient. An empty card is `not_evaluated`; the obvious reimplementation, worst status
among the entries, has nothing to take a worst of and reports a pass over no checks. A
consumer rebuilding the verdict from its own reading of this library's output could produce
exactly the silent green the library exists to refuse.

It was not the only one. A `status` property returning a `CheckStatus` is a **rolled-up
verdict**, and eight models had one: the scorecard, the attestation predicate, the
verification report, the bundle sections, a load-combination evidence record, a calculation
report, and both halves of a verification plan. The plan is the one worth naming beside the
scorecard — its own docstring says *a plan is not evidence*, and the serialized plan carried
its items, every one of them with `outcome: null`, and nothing that said so. All eight are
computed fields now, and a gate keyed on the **annotation** holds them: a `status` returning
a plain `str` — `ExportAuthorization`'s `"VALIDATED"` label, one line off a boolean already
in the document — is deliberately not swept in by a rule about names.

`status` is a computed field in 1.1.0: required, read-only, and dump-only, so a document
cannot assert a verdict that disagrees with its own checks. 1.0.0 is unchanged and still
frozen — a client pinned to it receives what it always did. The bundle digest moved with it,
which is the pin working: a scorecard document that says something new is a different
bundle, and a content address that had *not* moved would have meant the verdict was not
covered by it.

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
