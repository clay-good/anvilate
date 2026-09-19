# The published contracts: pipeline documents as JSON Schema

**Anvilate's input and its outputs are now documents anything can validate, without
importing Python.**

The load-bearing data contracts are the Design Spec IR going in, and the geometry summary,
scorecard, and evidence bundle coming out. As Python classes they are only checkable from
Python; as JSON Schema 2020-12 they are checkable by a CAD add-in, a CI job, or an MCP client
that has never heard of anvilate.

| Artifact | What it describes | Version |
| --- | --- | --- |
| [`docs/api/schemas/design-spec.schema.json`](api/schemas/design-spec.schema.json) | the typed part description the pipeline consumes | the same number a spec file states in `anvilate_spec` |
| [`docs/api/schemas/scorecard.schema.json`](api/schemas/scorecard.schema.json) | one typed result per check, with the rolled-up status | `SCORECARD_SCHEMA_VERSION` |
| [`docs/api/schemas/evidence-bundle.schema.json`](api/schemas/evidence-bundle.schema.json) | every layer's contribution for one part, the roll-up, the scorecard and the spec | `BUNDLE_SCHEMA_VERSION` |
| [`docs/api/schemas/geometry-summary.schema.json`](api/schemas/geometry-summary.schema.json) | one valid solid's audited pattern, dimensions, volume, and semantic face tags | `GEOMETRY_SCHEMA_VERSION` |
| [`docs/api/schemas/step-interface-candidates.schema.json`](api/schemas/step-interface-candidates.schema.json) | planar faces, solid summaries, exact contacts, projected gaps, coaxial bore/shaft candidates, solid-interference scorecards, and regular through-hole patterns measured from imported STEP solids | `INTERFACE_CANDIDATES_SCHEMA_VERSION` |
| [`docs/api/schemas/confirmed-step-interface.schema.json`](api/schemas/confirmed-step-interface.schema.json) | a named person's acceptance of one exact measured candidate and its generated `InterfaceContract` | `CONFIRMED_INTERFACE_SCHEMA_VERSION` |
| [`docs/api/schemas/confirmed-planar-contact.schema.json`](api/schemas/confirmed-planar-contact.schema.json) | a named person's acceptance of one exact coplanar contact without an invented hole pattern | `CONFIRMED_CONTACT_SCHEMA_VERSION` |
| [`docs/api/schemas/planar-contact-area-check.schema.json`](api/schemas/planar-contact-area-check.schema.json) | a confirmed planar contact checked against a caller-supplied, cited minimum overlap area | `PLANAR_CONTACT_AREA_CHECK_SCHEMA_VERSION` |
| [`docs/api/schemas/confirmed-planar-gap.schema.json`](api/schemas/confirmed-planar-gap.schema.json) | a named person's acceptance of one exact projected planar gap without an allowable-clearance verdict | `CONFIRMED_PLANAR_GAP_SCHEMA_VERSION` |
| [`docs/api/schemas/planar-gap-clearance-check.schema.json`](api/schemas/planar-gap-clearance-check.schema.json) | a confirmed planar gap checked against a caller-supplied, cited clearance band | `PLANAR_GAP_CLEARANCE_CHECK_SCHEMA_VERSION` |
| [`docs/api/schemas/confirmed-cylindrical-mate.schema.json`](api/schemas/confirmed-cylindrical-mate.schema.json) | a named person's acceptance of one exact bore/shaft candidate without an automatic fit verdict | `CONFIRMED_CYLINDRICAL_MATE_SCHEMA_VERSION` |
| [`docs/api/schemas/cylindrical-mate-engagement-check.schema.json`](api/schemas/cylindrical-mate-engagement-check.schema.json) | a confirmed measured bore/shaft pair checked against a caller-supplied, cited minimum axial engagement | `CYLINDRICAL_MATE_ENGAGEMENT_CHECK_SCHEMA_VERSION` |
| [`docs/api/schemas/cylindrical-mate-fit-check.schema.json`](api/schemas/cylindrical-mate-fit-check.schema.json) | a confirmed measured bore/shaft pair checked against caller-supplied ISO 286 fit inputs | `CYLINDRICAL_MATE_FIT_CHECK_SCHEMA_VERSION` |
| [`docs/api/schemas/viewport-image.schema.json`](api/schemas/viewport-image.schema.json) | a deterministic SVG viewport, integrity digest, and base64 payload | `VIEWPORT_SCHEMA_VERSION` |
| [`docs/api/schemas/geometry-measurement.schema.json`](api/schemas/geometry-measurement.schema.json) | one scalar read from the regenerated B-Rep, with unit and semantic feature | `MEASUREMENT_SCHEMA_VERSION` |
| [`docs/api/schemas/cli-output.schema.json`](api/schemas/cli-output.schema.json) | every completed `--format json` result from `build`, `check`, `export`, `verify`, `interfaces`, `diff`, and `doctor` | `CLI_OUTPUT_SCHEMA_VERSION` |

The version cells name the constants rather than quoting numbers, and
`test_the_contract_tables_versions_are_the_constants_own` holds them to the module. This row
said `1.1.0` while the scorecard contract was at 1.6.0 — a published version number, stated
wrongly, on the page that exists to document the published versions.

```python
from anvilate.contracts import freeze_release, scorecard_json_schema, write_schemas
```

`write_schemas` regenerates the published artifacts; `freeze_release` cuts a version, once.

**The evidence bundle had no contract at all** until it had this one. The `export_artifact`
MCP tool published its entire output as `{"type": "object"}` — the one thing the tool exists
to hand a client was the one thing its schema said nothing about — because there was no third
schema to `$ref`. It is generated from `anvilate.bundle.BundleDocument`, which *describes* the
document rather than building it: constructing that model and dumping it with `exclude_unset`
would reproduce the absent-versus-null rule at the top level and also strip
`informational: false`, `reference: null` and `blocking: []` out of eight nested structures,
and changing bytes the document has always emitted is the wrong price for a schema's
provenance. A gate validates every bundle the library builds against the released artifact,
which is what keeps the description true.

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

### Scorecard 1.10.0: a warning status

A check's status gains `warning`: the check met its hard limit and entered a caution band its
document declared, such as material in a keepout's clearance margin that does not reach the
core. It is not a pass, so a card holding one does not pass, and it is not a failure. It rolls
up after `fail` and `not_evaluated` and before `over_margin`, and `anvilate check` exits 6 on
it. Evidence Bundle 1.18.0, STEP interface candidates 1.12.0 and CLI output 1.45.0 carry the
status enumeration and move with it.

### Design Spec 1.16.0: where a keepout sits on its anchor

A keepout gains `offset`, the distance from its anchor face to its near end, measured into
the part, zero by default. The body is centred on the anchor face with its axis along the
face's inward normal, so it moves when the face does. `anvilate.keepouts.screen_keepouts`
builds each body on the part's own geometry and measures the part against it. Evidence
Bundle 1.17.0 and CLI output 1.44.0 carry the same document.

### Design Spec 1.15.0: the volumes the part must leave empty

`keepouts` declares each protected volume: its tag, the tag or datum it is anchored to and
moves with, a generating rule (prism, cylinder, frustum, swept profile or an imported body
named by its digest), a clearance margin, a required reason and its owner. A keepout with
no volume, no reason or no anchor is refused. Screening reports each one as not evaluated
until intrusion is checked against built geometry, naming an anchor the document no longer
tags; see [spec screening](spec-screening.md). Evidence Bundle 1.16.0 and CLI output 1.43.0
carry the same document.

### Design Spec 1.14.0: how the part is located

`constraint_topology` declares a named frame, the constraints locating the part — each with
the feature it acts at (a tag the document already carries), its kind, the freedoms it
removes and any declared redundancy — and the freedoms kept on purpose. Screening counts
them; see [constraint topology](constraint-topology.md). A constraint at a feature the
document does not tag is refused naming it. Evidence Bundle 1.15.0 and CLI output 1.42.0
carry the same document.

### Evidence Bundle 1.14.0: the order a dependency chain ran in

The exported document gains `evaluationOrder`, absent unless the checks ran as a
[dependency chain](check-dependencies.md): the order they actually ran in, every name one the
scorecard carries. Outside the signed roll-up, so no attestation digest moves. CLI output
1.41.0 carries the same document.

### Design Spec 1.13.0: a value a profile supplied says so

`origin` gains `profile_supplied`: a value a bound [profile](declaration-needs.md) filled in,
neither stated by the engineer nor chosen by the library. Like `default`, it must carry a
rationale, which names the profile, its version and its citation. Evidence Bundle 1.13.0 and
CLI output 1.40.0 carry the same document.

### Scorecard 1.9.0: a check says which failure modes it addresses

A scorecard entry gains `addresses`: the ids of the [failure modes](failure-mode-coverage.md)
the check addresses, empty by default. Coverage reads it off the card rather than matching
check names, and counts it only for a check that ran. An entry naming one mode twice is
refused. Evidence Bundle 1.12.0, Interface Candidates 1.11.0 and CLI output 1.39.0 carry the
same entry.

### Design Spec 1.12.0: an environment, and what a joint is

`environment` is one of a closed vocabulary — indoor dry, outdoor sheltered, marine, thermal
cycling, vibration, submerged — and an interface gains an optional `kind` (bolted face,
clamped, welded, bonded, press fit, sliding) and `mating_material`. They are the declared
facts the [failure-mode catalogue](failure-mode-coverage.md) keys on, and none could be stated
before. Whether a joint is a dissimilar-metal pair is derived from the two material
references, not declared by the author. All optional: a document that says nothing is not
assumed to mean anything.

### Design Spec 1.11.0: a document can declare its screening depth

`acceptance.depth` is `concept` or `detailed`, defaulting to `detailed` — which is what this
library screened before depth existed, so no document already written changes meaning. A
`concept` screen defers the drawing's work and reports each deferred family as an
`out_of_depth` scorecard entry. That status is new in the scorecard contract (1.8.0): a fifth
value a consumer will see, which is why the version moved. It is not blocking and it is not
`not_evaluated`; every surface states both counts.

### Design Spec 1.10.0: a budget contributor can be a budget

`budgets[].contributors[].sub_budget` makes a contributor another budget, evaluated under its
own combination rule and entering its parent as a single value — the way a system allocation
decomposes into subsystem allocations. A term states exactly one of a value, a reason it has
none, or a sub-budget. Nesting is bounded at eight levels, and a sub-budget carrying an
ancestor's name is refused naming the chain: an allocation cannot be one of the terms that
spend it. A sub-budget that could not be evaluated leaves its parent not evaluated, naming it.

### Design Spec 1.9.0: a budget can declare growth allowances

`budgets[].growth` is an optional list of per-basis growth allowances: a factor applied to
every contributor of one basis (measured, calculated, estimated) with the authority for it.
The allowance is applied to the value the combination rule sees and recorded as a
[margin-ledger](margin-ledger.md) entry of kind contingency-or-growth, so it is never
absorbed into a number that then reads as a measurement. At most one allowance per basis.

### Design Spec 1.8.0: a spec can declare performance budgets

`budgets` is an optional list of [performance budgets](performance-budgets.md): an allocated
limit with its own provenance, the contributors that spend it with their bases and
correlation groups, and the declared combination rule. The screen evaluates each declared
budget last, binding contributors to the checks that just ran, and emits it as a scorecard
entry — so a card of individually passing checks fails when their combination exceeds the
allocation. A budget the screen could not evaluate is `not_evaluated` naming it, never absent.

### Design Spec 1.7.0: a spec can declare its margins

`constraints.margins` is an optional list of margin-ledger entries: the conservatism an author
applied beyond the physics, each with its kind (code-required, user-elected, statistical basis,
contingency or growth, rounding, derating), the quantity it bears on, its origin and its
authority. A blank origin or authority, or a factor below 1, is refused. The kind is declared
rather than inferred, because no screen can tell an obligation from a choice by the number.
See [the margin ledger](margin-ledger.md).

### Design Spec 1.6.0: counterbores retain both diameters

The circular locator adds `counterbore`, which requires a through diameter smaller than its
recess diameter; `axial_extent` is the recess depth. Detection only offers the stepped
feature when exactly one smaller coaxial inward cylinder continues from the shoulder to the
opposing exterior plane. Nested blind steps remain unclassified rather than guessed.

### Design Spec 1.5.0: a confirmed interface can carry its circular locator

`InterfaceContract.locator` is an optional typed through/blind pilot bore or boss, with its diameter and
axial extent. STEP discovery offers only circular features concentric with a fitted pattern,
and confirmation names the exact locator ID separately; it is never selected by proximity
alone. The candidate, confirmed-interface, evidence-bundle, and CLI schemas move with it.

### Design Spec 1.4.0: interface geometry keeps its coordinate frame

`InterfaceContract.frame` locates a deterministic right-handed coordinate frame in the
source geometry, and `HolePattern.hole_centers` lists each hole in that frame. Both are
optional, so every older 1.x contract remains valid. Confirmed STEP candidates populate both:
diameter, count, and hole size alone cannot distinguish a rectangular pattern's clocking.
The evidence-bundle, confirmed-interface, and CLI schemas move with the nested contract.

### Design Spec 1.3.0: a document can ask to be told it is over-engineered

`constraints.max_safety_factor` is the top of the target band. `OVER_MARGIN` was first-class
everywhere a verdict is read and reachable only from a pack argument no document could set,
so the status shipped for months with no way to ask for it. Additive, like every 1.x change
before it, so an older spec loads unchanged — and comes back declaring the version its
author wrote, not this release's. The field is a record of what the document is; see
[screening a document](spec-screening.md#anvilate_spec-is-a-record-not-an-assertion) for why
it used to be an assertion and what that cost the evidence bundle.

### 1.2.0: a derivation with nothing substituted into it

`Derivation.inputs` now requires at least one entry, so the scorecard schema states
`minItems: 1` on it. A derivation carrying no inputs renders as its own formula with nothing
substituted — the reconstruction the type exists to replace, dressed as a worked
calculation. No card this library has ever written carried one, which is why this tightens
what Anvilate writes without changing what a reader must accept.

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

## The whole status enum is in the contract

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

## The CLI identifies its contract on the wire

Every completed `--format json` result carries the same three fields before its
command-specific content:

```json
{
  "schema": "https://anvilate.dev/schemas/cli-output/1.3.0.json",
  "schema_version": "1.3.0",
  "command": "check"
}
```

The schema is a closed union of the five completed-result variants plus a refusal variant:
`check`, evidence-bundle export, QIF export, `verify`, `diff`, and `refused`. The export
variants also carry `artifact`, so a
reader never has to infer whether `documents` or `bundles` should be present. The contract
is generated from the wire models, checked against real output from all five paths, and
frozen under `released/` by the same two-part drift gate as the other contracts.

Version 1.1.0 adds the refusal variant. A bad request or unbuilt operation requested as JSON
keeps its established exit code and stderr text, and also writes a document carrying
`outcome: refused`, the code, every diagnostic line, and a concrete remedy. That includes
parser-level refusals such as a missing positional argument, before a command namespace
exists.

Version 1.2.0 adds the internal-error variant. Unexpected exceptions from command execution
exit 5 and carry `outcome: error`, the diagnostic, and the retry/report remedy. Ordinary
Python exceptions are contained; `KeyboardInterrupt` and `SystemExit` remain control flow
and are not mislabeled as product defects.

Version 1.3.0 adds the `doctor` result: one independently reported pass/fail record for each
required runtime area, including a remedy on every failure.

## What is not published as a schema artifact

Tool definitions. This section used to report all three of them — the definitions, the
mapping of pipeline operations onto MCP tools, and the server that would serve them — as
still ahead of us. All three have been here for a while: `modernize-mcp-server` task 1.2 is
checked off, `anvilate-mcp` runs on stdio, and `tools/list` serves the eight definitions,
which is what [the MCP tool surface](mcp-tool-contracts.md) is a whole page about.

What is still true is the narrower thing this page is for. The three artifacts in the table
above are files with URLs; a tool definition is not. Its schemas are assembled in
`anvilate.mcp` and reach a client inline in the `tools/list` reply, pointing at those three
URLs by `$ref` for everything load-bearing — so a client validating a spec, a scorecard or a
bundle is validating against a published document, and only the thin argument wrappers are
inline. Publishing those wrappers as their own versioned artifacts would be a fourth
contract to version, and nothing has needed one.
