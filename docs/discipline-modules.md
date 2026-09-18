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

A **check-name namespace** is not a field here. The spec asks a module to reserve one, and
nothing in this library could hold a pack to it today: a check is named after the element
instance that produced it (`col_base plate bending`), not after its module. A declared
namespace would be a string no gate could check, so it arrives with the naming change that
makes it true.

## Status

This is the manifest contract, the ten shipped manifests and the completeness gate
(`openspec/changes/add-physical-domain-modules`, tasks 1.1, 1.3, 2.1 and 3.1). The loader
with enable/disable and lazy import, duplicate-limit-state detection across modules, the
per-module exercise floor, the both-directions standards gate, and out-of-tree modules are
what remain.
