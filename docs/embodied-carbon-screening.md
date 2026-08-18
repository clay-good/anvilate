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

## What is deliberately not here

- **No bundled factor data.** See above; it is a licensing constraint and a correctness
  one.
- **No openEPD import yet.** The openEPD schema is Apache-2.0 and binding a product EPD
  over a generic factor is the natural next step, but a `CarbonFactor` built by hand from
  an EPD already records everything the estimate needs.
- **No product passport export.** The EU Digital Product Passport registry is live, but
  no product-specific delegated act is in force. Building an export against a
  specification that does not exist yet would be inventing it.
- **No use-phase or end-of-life modules.** B and C are outside the cradle-to-gate
  boundary this screen declares, and for most mechanical parts they are dominated by how
  the part is used rather than how it was made.
