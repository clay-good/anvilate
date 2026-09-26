# What a discipline module declares

Nine disciplines — ten packs — sit on a foundation that knows nothing about steel, timber or
piping: units, the Spec IR, the scorecard, the citation doctrine, the evidence bundle. That
is why a tenth domain is possible at all. What was missing was the contract: adding a domain
meant editing a shared specification that enumerated the packs one by one, and it never had
to answer what a module declares about itself.

A `ModuleManifest` is those answers as data.

```python
from anvilate.modules import MODULE_MANIFESTS, manifest_for

manifest_for("machinery").screens    # the screen_* functions the pack exports
manifest_for("machinery").standards  # ("AGMA",) — the bodies its checks cite
manifest_for("machinery").tiers      # the pipeline tiers it touches
print(MODULE_MANIFESTS)              # every module this build ships
```

| Field | What it states |
| --- | --- |
| `id`, `version` | The stable name a document, a dependency or a bug report uses, and the version of the module's own contract. |
| `unit_default` | The system the module's figures are written in. |
| `standards` | The standards bodies its checks cite. Each must be one the [effectivity layer](standards-effectivity.md) recognises, so an edition can be pinned to it. |
| `material_properties` | The property sets its screens need from a material record. |
| `tiers` | The pipeline tiers it touches. |
| `depends_on` | Other modules it composes with. A dependency this build does not carry is refused, and so is a module depending on itself. |
| `screens` | The `screen_*` functions the element registry selects. |
| `covers` | The `element_type` tags a document may declare and have this module screen. Derived from the registry and gated against it, and named in the refusal a document gets for a tag nothing covers — so a missing module is a reported gap rather than a screen that quietly did not run. |
| `summary` | What the module is for, in a sentence. |
| `deprecated` | When it goes, and what to use instead — rendered wherever the manifest is. |

## The manifest is held to the pack, not trusted

`tests/test_modules.py` derives each pack's screens from the package the same way
`element_registry` does, and fails a manifest that names a different set, a pack with no
manifest, a manifest for no pack, two modules claiming one id, and a standard no body
matches. It carries a floor on the number of screens it is reading, so a refactor cannot
turn the gate green by emptying it. Both mutations — dropping a screen from a manifest and
deleting a manifest — were run against it.

## Choosing which modules a run uses

```python
from anvilate.modules import load_modules

run = load_modules()                              # every shipped module
run = load_modules(["structural", "industrial"])  # or a named subset
run.screens()                                     # what a document can reach in this run
run.disabled                                      # and what it cannot, recorded
module = run.load("structural")                   # imported here, not at declaration
```

Nothing is imported when the registry is read: a caller that wants one discipline does not
pay for the other nine, and a test proves it in a subprocess, because a suite that has
already imported every pack cannot see the claim. Two refusals, both about a set that would
screen less than it looks like it does: a name no manifest carries, because a typo that
silently enabled nothing would screen a document against a subset nobody chose; and a
module whose dependency is not in the set, named with what it needs. The enabled set is
carried as data because two builds of one document that enabled different modules screened
different things, and a verdict alone cannot say so.

## Every declared screen has to run

A screen a module declares and nothing exercises is a check that ships and has never
produced a verdict. At the end of a clean full run the suite reports the fraction of
declared screens that ran, against the population it measured, and fails on any that did
not. All 29 run today.

The record comes off the call stack of each scorecard entry, not from wrapping the screen
functions: a test that writes `from anvilate.packs.structural import screen_base_plate`
binds the original at import time, and a wrapper installed on the module would record
nothing for it — the gate would then report a screen nobody runs. It records **every**
screen frame on the stack rather than the nearest one, because `screen_structure`
dispatches to member screens and builds no entry of its own; with a nearest-frame detector
the one screen that composes the others was the single screen reported as unexercised.

## What a module claims it can screen

`covers` is the set of `element_type` tags a module's screens are selected by, held to the
element registry the same way its screens are. A document naming a tag nothing covers is
refused with the modules and their tags listed — the next move is choosing an element, not
guessing at the list — and the near-miss suggestion still comes last, where a reader looks
for it. One tag belongs to no module: `structure`, which the screening layer registers
itself, because a structure's members can come from any discipline.

## A declared standard is one its own checks cite

The standards a manifest declares are held to what its screens write, in both directions.
A body a check cites and the manifest omits is a dependency nobody can pin an edition to; a
body a manifest declares and no entry of that module cites is a claim its own output does
not support. The record is attributed to the innermost pack frame — the screen that wrote
the citation — because a member's clause belongs to the member's pack, not to whatever
composed it, and it is taken on `model_copy` as well as on construction: a pack builds an
entry through `from_safety_factor`, which knows no clause, and attaches the reference
afterwards. Reading only `__init__` saw one standard in the whole library.

This gate found its first drift before it shipped: `industrial` declared AISC because the
pack's docstring calls its members "AISC-flavored", and no entry it builds cites AISC at
all. The declaration was removed.

A **check-name namespace** is not a field here. The spec asks a module to reserve one, and
nothing in this library could hold a pack to it today: a check is named after the element
instance that produced it (`col_base plate bending`), not after its module. A declared
namespace would be a string no gate could check, so it arrives with the naming change that
makes it true.

## Writing a module

A tenth domain is a pack plus a manifest. The order that works, and what holds you to each
step:

1. **Write the screens.** A `screen_*` function per element, taking the element's model and
   returning a `Scorecard`. [Contributing analysis](contributing-analysis.md) is the
   contract for the checks themselves — cited formulas, dimensioned quantities, an anchored
   number, a runnable example.
2. **Export them.** The element registry derives the tags from each pack's `__all__`, so a
   screen that is not exported is a screen no document can reach.
3. **Add the manifest** to `MODULE_MANIFESTS`: id, version, unit default, the standards its
   checks cite, the material properties it needs, the tiers it touches, its dependencies,
   its screens, its coverage, and a sentence saying what it is for.
   Then register each limit state its checks evaluate in
   `anvilate.limit_states.DEFAULT_LIMIT_STATES`: an id, what the limit state is, and the
   (screen, check) pairs that evaluate it.
4. **Run the suite.** Five gates will disagree with you if the manifest and the pack do not
   match: the screens it names against the pack's exports, the tags it covers against the
   registry, the standards it declares against the citations its own entries write, the
   exercise floor over every screen it declares, and the registry's own refusal of a
   duplicate id or an unresolvable dependency.
5. **Write the capability spec** for the domain under `openspec/changes/`, not as an
   appendix to `discipline-packs`. A domain that needs the shared contract changed is
   telling you the contract is wrong, which is a different change.

Composition over duplication: a module reuses an existing screen where one exists rather
than shipping a second implementation of the same limit state. A check's name can't show
this, because it is named after its element instance, and one name can cover two limit
states: the base plate's `concrete bearing` is AISC §J8 unconfined, while the pedestal's is
ACI 318 §22.8.3 with confinement. So identity is a registry id (`anvilate.limit_states`),
and three gates key on it:

| Gate | Fails when |
| --- | --- |
| Registry | An id is registered twice (naming both implementations), a check is bound to two ids, or two screens share an id without naming the one implementation they call. |
| Composition (`tests/test_limit_states.py`) | A screen evaluating a shared limit state does not call its named implementation. The check reads the screen's own call graph and the symbol's identity, so a same-named local function does not count. |
| Emission (`tests/conftest.py`) | A module check the suite built resolves to no registered limit state. On a full run, it also fails when a registered check was never emitted. |

## Status

This is the manifest contract, the ten shipped manifests, the completeness gate and the
exercise floor (`openspec/changes/add-physical-domain-modules`, tasks 1.3, 2.1, 3.1, 3.2 and
3.3), the loader (2.2), declared coverage (1.2), the authoring page (5.1) and
duplicate-limit-state detection by registry id (2.3): 60 limit states across the 64 checks
the shipped modules emit, two of them shared by two screens: column buckling through AISC
§E3's `aisc_flexural_buckling_stress`, and gross yielding in tension through `axial_stress`.
Out-of-tree modules are what remain.
