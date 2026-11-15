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

## Galvanic couples

Two metals in contact with an electrolyte between them make a cell, and the more active
one corrodes in place of the other. The series that decides which, and how far apart they
are, is **MIL-STD-889C Table II**, read from the standard itself — a US Department of
Defense standard approved for public release, so it ships, 93 names in the published
order from magnesium to graphite.

```python
from anvilate.standards import GalvanicCouple, GalvanicEnvironment, screen_galvanic_couple

screen_galvanic_couple(
    GalvanicCouple(
        first="Al alloy 6061-T6",
        second="Copper 110",
        environment=GalvanicEnvironment.MARINE_ATMOSPHERE,
        separation_limit=10,                      # yours, with its basis
        limit_basis="the project's corrosion-control plan, rev B",
    )
)
# Al alloy 6061-T6 (anode) against Copper 110: 37 places apart in marine atmosphere,
# not acceptable; ... §5.1.2 requires metals widely separated in the series to be
# protected against contact
```

**No threshold ships.** 889C gives none: it says only that "the closer one metal is to
another in the series, the more compatible they will be", and that metals "widely
separated" shall be protected. The figures that circulate for this calculation — 0.15 V,
0.25 V and 0.50 V of "anodic index" — are **not in 889C**, and secondary sources
attribute them to a different standard. So `separation_limit` is yours, with its basis,
and the verdict quotes that basis back.

Three rules of the standard that a separation alone misses, each checked:

| Rule | Clause | What it catches |
| --- | --- | --- |
| A humidity-controlled environment may only be claimed if it is **assured** | note (g) | Control is assured only by a hermetically sealed compartment; where it is not, the contact is screened as if it were in **sea water**, and the verdict says so |
| The **cathode is the smaller area** | §5.2(a) | "Stainless bolts in an aluminium sheet, but not the reverse" — a small anode feeding a large cathode carries the whole couple's current in very little metal |
| **Magnesium** takes the maximum protective system, always | §5.1.6 | Whatever the separation and whatever else is declared, and whether or not the joint carries current |

An isolation measure clears a separation past the limit. It does not clear the other two:
they are about the couple itself, not the distance between its metals.

**What is not transcribed.** 889C's Table I, the per-pair guide to protective systems, is
a scanned image in the published PDF rather than text. Two hundred compatibility cells
read off a 1967 scan by eye is a table nobody could check, so it is not here, and the
environment is carried and reported rather than acted on beyond note (g).

**What is not wired yet.** Which items of a product touch, and which material record maps
to which name in the series, is still the caller's: this screens a couple you hand it,
not a product you declare.

## Not yet

Screening the composition against substance lists (REACH candidate list, RoHS, the
automotive declarable list) waits on lists read from their publishers.
