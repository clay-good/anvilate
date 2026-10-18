# Material compliance

**What a product's materials are made of, and what they withstand.** Each material a
product's items name is declared once in `screening.materials`: its composition by CAS
number, its recycled fraction, and its attributes, every value with the source it was read
from. Anvilate holds no material data of its own here; every number is yours, cited.

```yaml
screening:
  materials:
    - material: PA66
      plastic: true
      composition:
        - {cas: 32131-17-2, name: polyamide 66, fraction: 0.7}
        - {cas: 65997-17-3, name: glass fibre, fraction: 0.3}
      composition_source: supplier declaration 2026-03
      recycled_fraction: {value: 0.3, source: supplier certificate}
      attributes:
        service_max_temperature: {value: {magnitude: 100, unit: degC}, source: datasheet p.4}
        flammability: {value: HB, source: UL card}
  needs:
    items: [handle]
    sterilization: {method: steam autoclave, temperature: {magnitude: 134, unit: degC},
                    source: reprocessing instructions}
```

An item names its material by its catalog spec's `material.ref`, or by the `material` of a
placeholder or component definition.

## Composition and recycled content

`composition_export(product, library=..., root=...)` places the product and gives one line
per body: its path, material, mass, substances (CAS number, name, mass fraction) and
recycled fraction with its source. Recycled plastic rolls up by mass over the bodies whose
material is declared `plastic`. A handle of 3.0 kg at 30% recycled and a shaft of 1.2 kg of
virgin plastic carry 0.9 kg recycled of 4.2 kg, 21%. When any plastic body's material
states no recycled fraction, the content is not given, and those bodies are named.

## Material needs

Each need is a limit you declare with its source, held against the attribute each affected
item's material declares, and cited on both sides. `items` limits the needs to those items;
empty, every item is held to them.

| Check | Need | Material attribute | Passes when |
| --- | --- | --- | --- |
| service temperature | `service_temperature` | `service_max_temperature` | the attribute reaches the need |
| sterilization | `sterilization` | `service_max_temperature` | the attribute reaches the method's temperature |
| vacuum outgassing | `vacuum` | `total_mass_loss` | the loss is at most the screen |
| flammability | `flammability` | `flammability` | the UL 94 class is at least the one needed |
| body contact | `body_contact` | `biocompatibility` | the category is among those declared |

UL 94 classes rank HB, V-2, V-1, V-0, 5VB, 5VA, least to most flame-retardant. A
`biocompatibility` attribute lists categories separated by commas.

A material that declares no attribute for a need is **not evaluated**, naming the
attribute to declare; it is never passed. A value of the wrong kind (a temperature without
its unit, a mass loss past 1, a class UL 94 does not name), a material declared twice, and a
need naming an item the product does not have are refused where they are written.

The entries appear in [product screening](product-screening.md) after the product-level
checks.

## Not yet

Screening the composition against substance lists (REACH candidate list, RoHS, the
automotive declarable list) and galvanic compatibility between metals in contact wait on
lists and tables read from their publishers.
