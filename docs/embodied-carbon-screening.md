# Embodied carbon screening (EN 15978 cradle-to-gate)

**What this produces is a screening estimate, not an EPD, a declaration, or a
certification.** It is comparable against your own variants computed the same way. It is
not quotable as an absolute figure in a disclosure. The point is to make mass reduction
legible as a carbon decision while the design is still cheap to change.

Anvilate already computes the two inputs a screening estimate needs — material and mass.
This turns them into kgCO2e beside the physics verdict. (There is no cost row to sit next
to yet: `engineering_economics` returns bare numbers and does not produce a scorecard
entry.)

## The arithmetic is trivial; the bookkeeping is the work

Mass times a factor. That is why so many published figures are wrong. Three things decide
whether the number means anything, and each is enforced rather than noted.

**Which life-cycle modules it covers.** EN 15978 splits a product's life into modules:
A1-A3 is cradle to gate, A4-A5 adds delivery and installation. A factor is only ever
quoted *for a scope*, and adding an A1-A3 figure to an A1-A5 one produces a number that
is neither. The units agree, the arithmetic is right, and the total is meaningless — so
the estimator refuses the sum:

```python
embodied_carbon_estimate([gate_contribution, site_contribution])
# ValueError: the contributions are quoted over different EN 15978 module scopes
# (A1-A3 (cradle to gate), A1-A5 (cradle to practical completion)), and their sum
# would not be an estimate of anything. Re-source the factors onto one scope.
```

**Where the factor came from.** A generic industry average and a product-specific EPD for
the actual supplier can differ threefold for the same material — recycled-content steel
against blast-furnace steel is the standard case. Following the user-supplied-allowables
doctrine, **no factor table ships with this library**: every `CarbonFactor` carries its
source, dataset identity, version and geography, and a blank source is refused. That is a
licensing position as much as a correctness one — the widely-used commercial datasets
forbid redistribution, and the clean route is a federal generic dataset the user cites by
UUID, or an EPD from the supplier.

**How wide the band is.** `band_low` and `band_high` are required, not defaulted. A
screening factor is a central value with real spread, and defaulting the band to 1.0
would quietly assert a precision nobody has.

## The finding that changes designs

Count only the finished mass and a machined part is understated by the whole of its
swarf. A 12 kg bracket at a 35% yield starts as a 34.3 kg billet, and the 22.3 kg removed
was smelted, cast and rolled exactly like the part:

```
machined from solid (35% yield)    fail    53.14 kgCO2e (39.86-79.71) over A1-A3;
                                           machined process loss carries 65% of it
near-net stamping (88% yield)      pass    16.73 kgCO2e (12.55-25.1) over A1-A3;
                                           stamped finished part carries 88% of it
stamping + unsourced fasteners     not_evaluated
                                           no carbon factor was supplied for the fasteners
```

The redesign takes 2.5 kg off the part and 36.4 kgCO2e off the estimate — 69% of it. See
[`examples/bracket_redesign_embodied_carbon.py`](../examples/bracket_redesign_embodied_carbon.py).

`material_loss_mass` computes that loss from the yield fraction. Scrap that is recycled is
neither free nor full price; how much credit it earns is a module D boundary decision this
screen does not make, and counting the loss at full factor is the conservative reading.

## A missing factor is not zero

That third row is the one that matters. A bill of materials with one unfactored item has
not been estimated, and reporting the sum of the items that happened to have factors
understates the design in the one direction nobody audits. `carbon_contribution` returns
`None` for a missing factor, and the scorecard turns that into `NOT_EVALUATED` naming
what was absent.

A missing *budget* is also `NOT_EVALUATED` — but a reporting one. The estimate is computed
and shown; only the verdict is withheld, because there is nothing to judge it against.
That is the honest state for a first pass and it still puts the number in front of you.

## A product's own declaration

`carbon_factor_from_openepd` reads one openEPD declaration, the JSON a program operator
publishes, into a `CarbonFactor`. The factor is the declared A1A2A3 global warming potential
over the mass of one declared unit. Its source names the declaration, its product and
maker, and the impact method, so an estimate built on it says which EPD it rests on:

```python
from pathlib import Path

from anvilate.analysis import carbon_factor_from_openepd

text = Path("supplier-6061.openepd.json").read_text()
factor = carbon_factor_from_openepd(text, material="AA-6061-T6", as_of="2026-09-24")
```

The band is the declaration's own: one declared relative standard deviation either side, or
none when it states none. A generic table's band describes a population of products, not
this one. Everything the conversion would otherwise have to guess is refused with the fix
named:

- a document that is not a product EPD (`doctype` other than `openEPD`);
- GWP under several impact methods, until `method` picks one;
- no A1A2A3 GWP (modules are not summed here), or a unit other than kgCO2e;
- a declared unit that is not a mass, with no `kg_per_declared_unit` beside it;
- with `as_of` stated, a declaration past its `valid_until`.

Declarations belong to their manufacturers and program operators, so none ships with this
library, and the function reads text the caller supplies rather than calling any service.

`with_declared_factors(generic, [declared])` binds declarations over a generic table. The
declaration wins for its material, a material with no generic factor gains one, and two
declarations for one material are refused rather than one being picked. An evidence bundle
built with `BundleSections(carbon=estimate)` carries the estimate under `carbon` (evidence
bundle 1.22.0) and prints one line per contribution with its factor's source. That is how
the bundle records which factor came from which declaration. The estimate stays out of the
roll-up and the signed predicate, because a figure with no budget has no verdict.

## Declared in the document

Since Design Spec 1.18.0 a document can carry its carbon inputs:

```yaml
carbon:
  lines:
    - label: frame
      mass: {magnitude: 12.0, unit: kg}
      factor: {material: AA-6061-T6, value: 8.4, scope: A1-A3 (cradle to gate),
               source: "openEPD ec3synthetic: Example 6061 extrusion, TRACI 2.1 GWP A1A2A3",
               band_low: 0.9, band_high: 1.1, dataset_id: ec3synthetic}
  budget: {magnitude: 150, unit: kg}
```

`anvilate check` then reports one `embodied carbon` entry, judged against `budget`. Without
a budget it states the estimate and is not evaluated, and the needs report names
`carbon.budget`. The exported evidence bundle carries the same estimate.

## What is deliberately not here

- **No bundled factor data.** See above; it is a licensing constraint and a correctness
  one.
- **No reading of EPD files from a Design Spec.** A document declares carbon inline (below):
  each line's factor is the whole record, so one read from an EPD and written in keeps the
  declaration's identity, but the CLI does not open EPD files a spec names.
- **No product passport export.** The EU Digital Product Passport registry is live, but
  no product-specific delegated act is in force. Building an export against a
  specification that does not exist yet would be inventing it.
- **No use-phase or end-of-life modules.** B and C are outside the cradle-to-gate
  boundary this screen declares, and for most mechanical parts they are dominated by how
  the part is used rather than how it was made.
