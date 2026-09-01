# Screening a Design Spec, and the tier it has to name rather than run

**Every discipline pack screens a typed element you build by hand. Nothing screened the
spec document itself, so the pipeline had a hole in the middle: a spec compiled to the IR
and stopped, and the scorecard came from a separate object the caller assembled.**
`screen_spec` closes the part of that hole the IR can support today and is explicit about
the part it cannot.

```python
from anvilate.screening import screen_spec

card = screen_spec(spec)
```

It is also what `run_validation` dispatches to over the
[MCP surface](mcp-tool-contracts.md), which makes it the second operation an agent can call
over the wire and get an answer to.

## What the document supports

| Check | Source | Verdict |
| --- | --- | --- |
| tolerance achievability, one per toleranced dimension | the declared process's finest achievable band | FAIL when the demanded band is tighter than the floor, with the capability record cited |
| stack-up, one per declared chain | the chain's own worst-case analysis | judged on the **worst case**, never the RSS spread |
| load classification | every force-carrying load case | NOT_EVALUATED, naming the cases, when any carries no declared nature |

Tolerance achievability runs when the spec's acceptance criteria demand T2. Chains and load
cases are screened whatever tiers the spec names — a declared chain is the document asking
for it.

**The worst case is the gate.** The two answers differ over a real band: two ±0.05 mm
dimensions on a 0.2 mm nominal gap span 0.1..0.3 mm worst-case and about 0.129..0.271 mm on
RSS, so a requirement of 0.12..0.28 mm passes statistically and fails in the worst case. A
part that can be built out of tolerance is one that will be.

## Saying what the part is

For a long time a `DesignSpec` could not say what kind of structural element it described.
It stated a material, a process, interfaces, dimensions, tolerances, loads and acceptance
criteria — and nothing that let a screen choose between a lifting lug, a beam and a shallow
footing. So no discipline-pack screen could be selected from a document, and **the T1
analytical tier reported `NOT_EVALUATED` on every spec**: 236 closed-form modules that no
amount of further analysis code would have made reachable from the front door.

Two fields close it:

```yaml
element_type: lifting_lug
element_params:
  name: padeye
  material: ASTM-A36
  width: {magnitude: 120.0, unit: mm}
  hole_diameter: {magnitude: 40.0, unit: mm}
  thickness: {magnitude: 20.0, unit: mm}
  load: {magnitude: 60.0, unit: kN}
constraints:
  min_safety_factor: {value: 2.0, origin: user_stated}
```

`anvilate check` on that document returns two cited ASME BTH-1 checks rather than a gap.

**A tag and a parameter map, not a typed union**, and the trade is worth stating. A union of
every pack element would validate a document completely at parse time and would make
`spec-ir` depend on all twenty-odd packs, so every new element became a bump to this
published schema *and* to the MCP tool contracts that reference it at its version. The tag
keeps the two surfaces independently versionable. What it costs is that a malformed element
is caught at screening rather than at parse — paid for by quoting the pack model's own
refusal, naming the field, so the answer is as specific as a parse error would have been.

**The registry is derived from the packs, not listed here.** Every `screen_*` a pack exports
whose first argument is a typed element is reachable by that element's name in snake case —
`LiftingLug` is `lifting_lug` — so a pack that ships a new element registers it by existing.
`anvilate.screening.element_registry()` is the list, and a gate holds it against the packs in
both directions.

### A document can name a whole structure

One tag addresses one element, and a frame is not one element. The structural pack has always
had `screen_structure`, which takes a *list* of members — and a list is not addressable by a
tag, so a document describing an assembly could name only one of its parts.

`structure` is that tag. Its members are written the way the top level is written, so moving
a part into an assembly is a change of indentation rather than a rewrite:

```yaml
element_type: structure
element_params:
  members:
    - element_type: lifting_lug
      element_params:
        name: front eye
        material: ASTM-A36
        width: {magnitude: 120.0, unit: mm}
        hole_diameter: {magnitude: 40.0, unit: mm}
        thickness: {magnitude: 20.0, unit: mm}
        load: {magnitude: 60.0, unit: kN}
    - element_type: bolted_connection
      element_params:
        name: splice
        bolt_diameter: {magnitude: 20.0, unit: mm}
        plate_thickness: {magnitude: 10.0, unit: mm}
        load: {magnitude: 15.0, unit: kN}
        bolt_material: ASTM-A36
        plate_material: ASTM-A36
constraints:
  min_safety_factor: {value: 2.0, origin: user_stated}
```

Each member goes back through the same registry a top-level element goes through, so it
reaches exactly the screen it would have reached on its own — refusals included. Entries
carry the member that produced them (`member 2 (bolted_connection): splice bolt shear`),
because two beams in one frame otherwise contribute two checks with the same name and a
reader cannot tell which one failed. **One member that cannot be screened does not
un-screen the others:** it contributes its own `NOT_EVALUATED` entry, which the roll-up
already refuses to treat as a pass, and the rest of the frame is still screened.

It is the one tag the packs do not supply — a structure belongs to no discipline, since its
members can come from any of them — and it is the one element whose members can come from
several packs at once. A structure cannot be a member of a structure; list the members
alongside the others.

**The required safety factor comes from the document.** Thirteen of the twenty-four screens
are judged against one and have no default, so it is read from
`constraints.min_safety_factor`. A spec that states none reports `NOT_EVALUATED` saying so
rather than screening against a figure this library made up — a safety factor nobody stated
is the assumption least worth inventing.

## What it still cannot do

T0 reports the same way: it checks a built solid, and no geometry is generated from a spec
today. T3 is bounded by a convergence criterion rather than by the size of its input, so it
is not part of a synchronous screen at all.

## The rule that makes the card safe to read

**Every claim the document makes gets an answer.** A tier it demands produces an entry even
when there is nothing to run it against; a declaration it makes is answered whatever tiers it
names; and a claim nothing in this library can screen is reported as unscreened, with what
checking it would take. The one thing the card never does is stay silent, because a claim
nobody looked at must not be indistinguishable from one that passed.

That is the whole rule. What it means field by field:

| The document says | The card answers |
| --- | --- |
| a tier in `acceptance.tiers` | its checks, or one `NOT_EVALUATED` entry saying why none ran |
| `element_type` + `element_params` | the pack screen's cited verdicts — or, if no demanded tier screens it, an entry naming the element and the tier that would have |
| `dimensions` | each band against the process floor — or, under no demanded T2, an entry naming what went unscreened |
| `chains` | each stack-up on its worst case |
| `combination_basis` | the governing combination, its factored demand and its clause |
| `material`, a standard-component `interface` | resolved, with the near misses named on a refusal |
| an *imported* interface | `NOT_EVALUATED`: a screen of one document cannot fetch another |
| `manufacturing.tolerance_class` | resolved like any other identifier |
| `constraints.min_safety_factor` | the figure every judged screen is measured against |
| `constraints.max_safety_factor` | the top of the band; a check above it is `OVER_MARGIN`, passing and flagged |
| `constraints.max_mass`, `envelope`, `max_cost`, `manufacturing.min_wall`, `acceptance.max_displacement`, `geometric_tolerances` | `NOT_EVALUATED`, naming the declared value and what checking it would take |

A census test holds that table: every field of a `DesignSpec` is either answered by a named
check or listed as not being a claim about the part — the schema version, the name, the
prose, the unit system, the contracts this part publishes for others. A field that is neither
fails the build.

**Three of these are worth the story**, because each was a silent green that a green suite
could not see.

A spec that named its element, its material and its 60 kN load and demanded only T2 screened
to **PASS** on a tolerance band, with nothing saying the lug had never been looked at. It
goes both ways: a ±0.0001 mm band — achievable on no process this library knows — passed
under T1 alone. The tier is still not forced; the acceptance criteria remain the contract.
But the answer to something nobody screened is "not evaluated", never a pass.

`max_mass: 150 g` read as a stated requirement and was consumed by nothing anywhere in the
library — and `min_safety_factor > 0` is True for infinity, so the bound validators, written
one field at a time, passed `.inf` too. No field of a document may now be an infinity or a
NaN: a dimension whose nominal was NaN had screened to PASS on its band, because the
achievability check compares the band against the process floor and never looks at the size
the band belongs to.

`tolerance_class` written the way a drawing writes it — `ISO2768-m` — screened to PASS and
then raised `'iso2768-m' is not a valid ToleranceClass` out of `anvilate export`. The class
was resolved when the evidence bundle was assembled and nowhere else: two surfaces
disagreeing about one document, and the one a user runs first said nothing.

**A refusal is an entry, never a traceback.** The pack screens raise for what they cannot
work with — an alloy the database does not carry, a quantity outside a standard's range — and
those raises were uncaught, so `element_params` naming a bad alloy took the whole card with
it. They are `NOT_EVALUATED` entries quoting the pack's own message now. `ValueError` and
`LookupError` only: a `TypeError` out of a screen is this library's bug rather than the
document's, and filing our own defect under "not evaluated" on somebody's card would be the
worst silence of the lot. A standing corpus of documents that are valid per the schema and
hostile to the screen is run at the library, the CLI and the MCP surface, and asserts each
comes back with a card that does not pass.

## References resolve, and the answer is a verdict

A spec names its material and its standard components as *identifiers* — `AA-6061-T6`,
`NEMA23` — and every property the screens use is retrieved from those. So an identifier the
databases do not carry is not a detail: it is the point at which nothing downstream can run.

This page used to say interfaces "resolve at reference validation, which is
`validate_references`, not a check with a verdict". `validate_references` existed, and
**nothing on any shipped path called it** — a spec naming `NOT-A-REAL-ALLOY` screened
identically to one naming `AA-6061-T6`, all the way through `anvilate check`. The two halves
of the resolution, the spec layer's `ReferenceResolver` protocol and
`anvilate.standards.StandardsResolver` which was written to satisfy it, had never been wired
together.

They are wired in `screen_spec`, and the answer is a scorecard entry: PASS naming what
resolved, FAIL naming the near misses.

```text
fail           material resolution
               unknown material 'AA-6061-T61' — did you mean AA-6061-T6, AA-6063-T6,
               AA-6082-T6? Every property the screens use is retrieved from this
               identifier, so nothing downstream can run on it.
```

The near misses are the half that matters: "unknown material" invites the reader to supply a
remembered number, which is the one thing this library exists to stop.

A team whose alloy is not one of the bundled records passes their own resolver —
`screen_spec(spec, resolver=...)`, built from `MaterialsDatabase.extended` — rather than
losing the check. One entry per standard-component interface, named by its tag; a spec that
declares none gets no interface entry, because nothing to resolve is not a check that ran.

## What is not screened

Geometric tolerances declared on the spec are legal at construction — the
[semantic GD&T layer](semantic-gdt.md) enforces Y14.5's grammar in the constructor — so
there is nothing left for a screen to catch, and a section that only ever passes is a
section a reader learns to skip.
