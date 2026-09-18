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
| `summary` | What the module is for, in a sentence. |
| `deprecated` | When it goes, and what to use instead — rendered wherever the manifest is. |

## The manifest is held to the pack, not trusted

`tests/test_modules.py` derives each pack's screens from the package the same way
`element_registry` does, and fails a manifest that names a different set, a pack with no
manifest, a manifest for no pack, two modules claiming one id, and a standard no body
matches. It carries a floor on the number of screens it is reading, so a refactor cannot
turn the gate green by emptying it. Both mutations — dropping a screen from a manifest and
deleting a manifest — were run against it.

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

## Status

This is the manifest contract, the ten shipped manifests, the completeness gate and the
exercise floor (`openspec/changes/add-physical-domain-modules`, tasks 1.3, 2.1, 3.1, 3.2 and
3.3). The loader with enable/disable and lazy import, duplicate-limit-state detection
across modules, and out-of-tree modules are what remain.
