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
| [`docs/api/schemas/viewport-image.schema.json`](api/schemas/viewport-image.schema.json) | a deterministic PNG or SVG viewport, integrity digest, and base64 payload | `VIEWPORT_SCHEMA_VERSION` |
| [`docs/api/schemas/geometry-measurement.schema.json`](api/schemas/geometry-measurement.schema.json) | one scalar read from the regenerated B-Rep, with unit and semantic feature | `MEASUREMENT_SCHEMA_VERSION` |
| [`docs/api/schemas/part-catalog.schema.json`](api/schemas/part-catalog.schema.json) | the elements a spec can declare, and for one element its fields and an example spec | `PART_CATALOG_SCHEMA_VERSION` |
| [`docs/api/schemas/context-inventory.schema.json`](api/schemas/context-inventory.schema.json) | a context folder's engineering files, and whose each is to read | `CONTEXT_INVENTORY_SCHEMA_VERSION` |
| [`docs/api/schemas/cad-file-facts.schema.json`](api/schemas/cad-file-facts.schema.json) | one STEP, DXF, STL or 3MF file, measured: sizes, holes, profiles, never its contents | `CAD_FACTS_SCHEMA_VERSION` |
| [`docs/api/schemas/combination-summary.schema.json`](api/schemas/combination-summary.schema.json) | several parts placed by the features they share: where each landed, and the parts list | `COMBINATION_SUMMARY_SCHEMA_VERSION` |
| [`docs/api/schemas/product-document.schema.json`](api/schemas/product-document.schema.json) | a product document: items with their identity, instances and patterns, mates, layout and variants | `PRODUCT_DOCUMENT_SCHEMA_VERSION` |
| [`docs/api/schemas/product-summary.schema.json`](api/schemas/product-summary.schema.json) | a placed product as a bounded summary tree: each node's path, part number, verdict and governing finding | `PRODUCT_SUMMARY_SCHEMA_VERSION` |
| [`docs/api/schemas/node-card.schema.json`](api/schemas/node-card.schema.json) | one node of a placed product: the checks it owns and its children's cards | `NODE_CARD_SCHEMA_VERSION` |
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
version stays put is a silent breaking change**: a client pinned to `1.1.0` validates
against a different document under the same identifier and has no way to know.

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
urn:anvilate:schema:elements:lifting_lug:1.3.0
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

### Product document 1.6.0: a reference assembly

A definition may be a `reference`: an existing STEP assembly by `file`, with the least
`clearance` the product must keep to it, under an identity whose source is `reference`.
Product summary 1.2.0, node card 1.2.0 and CLI output 1.66.0 move with it: a node's kind
may be `reference`. An older product document reads unchanged.

### CLI output 1.65.0: `verify` reads a release package

`anvilate verify <folder>` on a folder holding a `manifest.json` checks every listed file
and answers `--format json` with `package`, `intact` and `problems`.

### Product document 1.5.0: a joint on a connection

A connection gains `joint`: its `kind` (rigid, revolute, linear, cylindrical, ball) and,
for a turning or sliding one, its `range`. An interface gains `feature`, the round feature a
catalog part's axial interface runs through. An older product document reads unchanged.

### Product document 1.4.0: a catalog part's interfaces, bound to its features

A part definition gains `interfaces`, each a name, a kind, the tagged `features` it is bound
to, and an optional `face`; their frame and parameters are read from the built part. A
connection that would place the ground is refused. An older product document reads
unchanged.

### Product document 1.3.0: interfaces, connections, and interfaces left open

A placeholder and a component record gain `interfaces`, each a name, a kind from the
closed vocabulary, the face or axis it is located by, its holes for a pattern, and its
parameters. A product gains `connections` (`on`, `place`, each `item.interface`) and
`open_interfaces` (`at`, `reason`). An older product document reads unchanged.

### Product document 1.2.0: a component names its vendor model, and a draft says so

A component record gains `model`, the vendor's STEP by relative path and SHA-256;
`drafted`, set on a record measured from that file by `draft_component`; and
`confirmed_by`, who checked a draft against the datasheet. A 1.0.0 or 1.1.0 product
document reads unchanged.

### Product document 1.1.0: a definition may be a purchased component

A definition gains `component`, a purchased component's record, and `demands`, what the
product asks of it; a node's `kind` may be `component`. Product summary 1.1.0, node card
1.1.0 and CLI output 1.64.0 move with it. A 1.0.0 product document reads unchanged.

### Design Spec 1.21.0: a part declares its duty cycle

`duty_cycle` holds a `life` (a time, a distance or a number of cycles, with its source),
named `events` (each a stress `history` or `blocks` of range, mean and count, its
occurrences per life and its source), the Basquin `curve`, and the mean-stress `correction`.
`screen_spec` adds a `duty-cycle fatigue` entry. Evidence bundle 1.29.0 and CLI output
1.63.0 move with it, because each carries the Design Spec; nothing else in them changes.

### Product document 1.0.0: the product is a published document kind

`anvilate_product: 1.0.0` names this schema; another version is refused. A definition's
`product` is a library name, a sub-product embedded whole, or `{file: drive/drive.product.yaml}`
relative to the document naming it, which `load_product` reads.

### Product summary 1.0.0 and node card 1.0.0: products through `build_combination`

`build_combination` takes a product document as its `combination`, with the sub-products
it places in `library`. It answers with `product`, the summary tree, or, given `node`, with
that node's full card as `node`. A combination's result is unchanged.

### CLI output 1.62.0: `check` reads a product document

`anvilate check stage.product.yaml --format json` answers with `product`, the product's
bounded summary tree: each node's path, part number, verdict, finding count and governing
finding, with how many passing nodes were left out and how to ask for one. With
`--node PATH` it answers with `node` instead, that node's full card. A spec's `check`
result is unchanged.

### Sections: a tilt is stated whole, and an offset is a length

Two rules on hand-built sections, both added the day the properties shipped. A
`minor_principal_second_moment` below every axis the section states is a tilt, so it now
needs a non-zero `principal_axis_tangent` beside it, and a tangent needs the moment. Without
the tangent, such a section reached a beam screen and passed bending on `M/S` about an axis
that is not principal, because the beam refusal reads the tangent. A `shear_centre_offset`
must be a length: one in newtons validated, then stopped the beam screen with a dimension
error. The schemas' shape is unchanged. Neither rule refuses a section the library's own
constructors build.

### `compile_spec` is going: its description says so

The tool's description now ends by saying it goes in the next release, and to call
`run_validation` or `build_part` instead. Both refuse a bad spec with the same remedies: a
misspelt parameter is named with its nearest real one, and a document missing a required
field is told the line to add. Until it is removed it accepts the same input and returns the
same `spec`, `errors`, `remedies` and `subject`, so a client calling it today is not broken.
Only the description text changes.

### `beam_member` 1.9.0: a channel's twist is declared, not guessed

`beam_member` gains an optional `twist_restraint`, one of `through_shear_centre` or
`restrained`. It answers the `twist` entry an open section earns: declare that the load acts
through the shear centre, so no torsion is applied, or that something holds the section
against rotating, and the entry passes — on the declaration, which its detail says plainly,
not on a calculation. Without it the entry stays `not_evaluated` and now names
`element_params.twist_restraint` as what it is waiting on, so the needs report can rank it.

Declaring it on a section whose shear centre is on the axis the load acts along is refused,
rather than accepted and ignored: there is no twist to restrain and no entry for it to
answer. `column_member` and `beam_column_member` have no twist entry — a channel is refused
there for its weak axis — so they stay at 1.8.0.

### Member schemas 1.8.0: a section records the axes its reference axes are not

A section gains two more optional properties: `minor_principal_second_moment`, the smallest
second moment it has, and `principal_axis_tangent`, the slope of the axis that goes with it.
`CrossSection.angle` fills both, and so does a member that names a rolled single angle
(`section: L8X4X1`). The minor principal moment must be at or below every axis the section
already states, since it is the smallest one there is.

`least_radius_of_gyration` now takes it into account, so a column is screened on the axis it
really bows about. This changes no section that does not state it — nothing in the library
did before — and for a single angle it is the difference between buckling it about its
diagonal and about the weaker of its two legs.

A `beam_member` or `beam_column_member` whose section states a non-zero
`principal_axis_tangent` is refused: bending it about a reference axis is not uniaxial
bending, and the screens' `M/S` would read under the real stress. `beam_member`,
`column_member` and `beam_column_member` move to 1.8.0; nothing a document already writes
changes meaning, and no document that validated before is refused now, because the
properties did not exist to write.

### Member schemas 1.7.0: a section records where its shear centre is

A section gains one more optional property, `shear_centre_offset`: the distance from the
back of an open section's web to the point a transverse load has to act through to bend it
without twisting it. `CrossSection.channel` fills it, and so does a member that names a
rolled channel (`section: C10X30`, `MC18X51.9`). It is a positive length, measured the way
AISC's `eo` column is.

A beam whose section carries it gets one more check, `twist`, which is `not_evaluated` on
every channel: the bending and deflection entries beside it are pure bending, and the screen
has no way to be told where the load acts. A `column_member` or `beam_column_member` whose
section carries it and states no `second_moment_transverse` is refused, because the axis
those screens buckle a member about would otherwise fall back to the strong one — four times
too stiff on a C10X30. `beam_member`, `column_member` and `beam_column_member` move to
1.7.0; nothing a document already writes changes meaning, and no document that validated
before is refused now, because the property did not exist to write.

### Member schemas 1.6.0: a rolled box states its corner

A section that records its box gains an optional `corner_radius`, the outside corner radius
of a rolled one. `CrossSection.hollow_rectangular(corner_radius=...)` fills it, and so does
a member that names a rolled HSS (`section: HSS6X4X1/4`, once the AISC workbook is
fetched). Its properties are then the rounded box's. `beam_member`, `column_member` and
`beam_column_member` move to 1.6.0.

### `interfaces` flags: one `--accept`, one `--limit`

No schema moved; the command line did. `anvilate interfaces --accept ID` accepts a hole
pattern, a planar contact, a cylindrical mate or a planar gap, read from the id's own prefix,
and `--limit NAME=QUANTITY` states `min-contact-area`, `min-engagement`, `basic-size`,
`min-gap` or `max-gap`. `--accept-contact`, `--accept-mate`, `--accept-gap` and the five
limit flags stay one release with the same meaning.

### CLI output 1.61.0: one command writes a part's files, and a healthy install is healthy

`export --artifact step` and `export --artifact 3mf` write the part itself to the file
`--output` names. The result is an `export` document whose `artifact` is `step` or `3mf` and
whose `built` object is what `build` reports as its `artifact`. `build` is unchanged and
stays one release as the same writer.

A `doctor` check's `status` gains `not_shipped`, for a capability this release does not
build. The FEA solver check reported `fail` on every install; it is `not_shipped` now, the
report's own `status` is `pass` when nothing else is wrong, and the command exits 0. A
script that read exit 1 as "no solver" should read the check's status instead.

### Member schemas 1.5.0: a section records the tube or box it is of

A section gains two optional properties, `outside` and `wall_thickness`: a round tube's one
outside diameter or a box's breadth and depth, and its wall. `CrossSection.hollow_circular`
and `hollow_rectangular` fill them, and so does a member that names its bar by its
dimensions (`section: TUBE 60x4`, `BOX 100x50x4`) or names pipe by its nominal size and
schedule (`section: NPS 4 SCH 40`). A section that states them is refused
unless its area, second moment and extreme fibre are that tube's or that box's. A beam whose
section carries them gets one more check, `wall local buckling`. `beam_member`,
`column_member` and `beam_column_member` move to 1.5.0; nothing a document already writes
changes meaning.

### Scorecard 1.14.0: a result from a third-party module says so

`ScorecardEntry` gains an optional `origin`, set only on an entry a third-party module
contributed: the module's id, version, the path it was loaded from and the SHA-256 of the
source that ran. It is absent from every other entry, so in-tree cards serialize exactly as
before. Evidence Bundle 1.27.0, STEP interface candidates 1.16.0 and CLI output 1.58.0 embed
the entry and move with it. See [third-party modules](discipline-modules.md#third-party-modules).

### Viewport image 1.2.0: a PNG the model can see

`mime_type` may now be `image/png` as well as `image/svg+xml`, and `image` is bounded at
16,000,000 characters of base64 instead of the 4,096 every other document string has. MCP
`render_viewport` attaches a PNG by default, because a model reads PNG, JPEG, GIF and WebP and
an SVG attachment reached the agent as an image it could not look at. `format: "svg"` still
returns the drawing. The PNG is rasterized from that SVG by `anvilate.raster` with the
standard library and is deterministic, so the digest still names the picture.

### Geometry summary 1.4.0 and CLI output 1.57.0: a timber beam's pattern

`timber_beam/1` joins the `pattern` enum of the geometry summary and of a build result's
`artifact`. The pattern shipped without it: MCP `build_part` returned an internal error on
every timber beam, and `anvilate build --format json` printed output this schema refused.
Both now take their pattern type from `anvilate.geometry.GeometryPattern`, and a test holds
that type equal to the module's pattern constants.

### Scorecard 1.12.0: module checks have stable ids

`ScorecardEntry.check_id` separates machine identity from the instance-specific name a
person reads. Document-driven discipline checks resolve through the limit-state registry
and use the module manifest's reserved namespace, so renaming an element does not rename
the check a downstream client tracks. The field is optional for non-module and historical
entries. Evidence Bundle 1.24.0, STEP interface candidates 1.14.0 and CLI output 1.53.0
carry the same entry, and the MCP result schemas reference the new scorecard and bundle
versions.

### CLI output 1.52.0: a build can be 3MF

`anvilate build` writes 3MF when `--output` ends in `.3mf`, so a build result's
`artifact.format` is now `step` or `3mf`. The file is the ISO/IEC 25422 core, written by
`anvilate.geometry.render_3mf` and read back by lib3mf in the tests.

### Design Spec 1.18.0: embodied carbon, declared in the document

A spec gains an optional `carbon` block: `lines`, each a `label`, a `mass` and a `factor`
(a whole `CarbonFactor`, source and band included), and an optional `budget` mass. A factor
read from a product's EPD and written into the document keeps the declaration's identity,
which is how a document binds a declaration to a material. `screen_spec` adds one
`embodied carbon` entry, judged against the budget, or not evaluated naming `carbon.budget`
when there is none. Evidence Bundle 1.23.0 carries the same estimate under `carbon`, and
CLI output 1.51.0 carries that bundle.

### Evidence Bundle 1.22.0: an embodied-carbon estimate, and which EPD each factor is

The bundle document gains an optional `carbon` key: the part's screening-grade estimate,
absent when none was made. Each contribution carries its factor, and a factor read from a
product's openEPD declaration (`carbon_factor_from_openepd`, bound over the generic table by
`with_declared_factors`) names that declaration in its `source` and `dataset_id`. So the
bundle records which factor came from which declaration. The estimate stays out of the
roll-up and out of the attested predicate, like `spec`, so no signed digest moves. CLI
output 1.50.0 carries the same bundle.

### Evidence Bundle 1.21.0: a named section's source

A provenance record's `kind` gains `section`. A member that names a rolled profile
(`section: IPE 200`) takes its dimensions from the bundled EN 10365 table, and the trail
records that table's citation. CLI output 1.49.0 carries the same bundle.

### Element schemas describe what a document may write

The element schemas were generated as what a model resolves to. That is right for the
documents Anvilate writes and wrong for `element_params`, which a user writes: once a member
could name its section, the published schema still said a section is an object. Element
schemas are now published in validation mode. `beam_member`, `column_member` and
`beam_column_member` move to 1.2.0, and `section` accepts a profile name or the properties.
Every other element's schema is unchanged. A test validates every shipped example's
`element_params`, as written, against its published schema.

### Scorecard 1.11.0: factors applied inside a capacity

A check entry gains `applied_factors`. These are the conservatisms a check applied inside
the capacity it judged, which a verdict of "1.0 required" cannot show: a pile's factor of
safety, BTH-1's design factor N_d, a bearing's required static factor, a gear's minimum
contact ratio. Each carries a label, a value of at least 1, where it came from and, when a
clause obliges it, that clause. The [margin ledger](margin-ledger.md) itemizes them. Evidence
Bundle 1.20.0, STEP interface candidates 1.13.0 and CLI output 1.48.0 carry the same entry.

### CLI output 1.47.0: a cancelled run

A run the user stops is its own outcome. `outcome: "cancelled"` with `exit_code: 130` states
what it completed, such as `1 of 2 specs screened`, and how to finish the rest. It is never a
verdict, a refusal or an error, and nothing from the run is reported as a result.

### Design Spec 1.17.0: how the build goes together

`assembly` declares the build's states in order, its parts with their insertion directions
and the features they occupy and sweep, the adjustments made in each state and the route to
each, and the toleranced dimensions to inspect and the route an instrument takes. An
operation in a state the document does not define, an install of an undeclared part and a
part declared twice are refused naming them. Screening reads it: the order, each adjustment's
reach in its state, and whether each dimension can be measured in any state; see
[assembly order](assembly-order.md). Evidence Bundle 1.19.0 and CLI output 1.46.0 carry the
same document.

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
command-specific content (shown at 1.3.0, when this section was written;
`CLI_OUTPUT_SCHEMA_VERSION` is the current one):

```json
{
  "schema": "urn:anvilate:schema:cli-output:1.3.0",
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
