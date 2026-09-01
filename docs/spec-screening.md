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
      element_params: {name: front, material: ASTM-A36, ...}
    - element_type: bolted_connection
      element_params: {name: splice, ...}
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

**A tier the spec demanded always produces an entry.** Including — especially — when the
document carries nothing to run it against: a spec that demands T2 and declares no
toleranced dimension gets one `NOT_EVALUATED` entry saying so.

The alternative is what makes this worth writing down. A demanded tier that quietly produced
no entries would leave `Scorecard.passed` green on the strength of whatever checks happened
to exist, and a part screened on zero checks would be indistinguishable from a part that
passed. Every tier the caller asked about is answered, and a tier the spec did not demand is
not screened and not reported — the acceptance criteria are the contract for which tiers
must run.

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
