# Industrial covers and panels

The machine-builder's flat work: an access cover, a guard panel, a tank lid — a plate under
uniform pressure, screened for bending and for flatness. One pack, one entry point, and a
scorecard with the same rules as every other.

```python
from anvilate.packs.industrial import CoverPlate, PlateEdge, screen_cover_plate
from anvilate.units import Quantity

cover = CoverPlate(
    name="access cover",
    pressure=Quantity.parse("50 kPa"),
    thickness=Quantity.parse("6 mm"),
    material="ASTM-A36",
    edge=PlateEdge.SIMPLY_SUPPORTED,
    length=Quantity.parse("600 mm"),
    width=Quantity.parse("400 mm"),
    deflection_limit=Quantity.parse("1.5 mm"),
)
card = screen_cover_plate(cover, required_safety_factor=2.0)
```

```text
access cover plate bending   PASS   safety factor 2.31 vs required minimum 2.00
                             Kirchhoff plate theory (Navier series)
access cover flatness        FAIL   deflection 2.499 mm vs limit 1.500 mm
                             Kirchhoff plate theory (Navier series)
```

**The cover is strong enough and still fails, and that is the ordinary case.** A plate this
size passes its stress check with 15% to spare and deflects 2.5 mm — well past the 1.5 mm a
gasket or a sliding fit can live with. Stiffness and strength are different problems: the
stress goes as t², the deflection as t³, so a cover chosen on stress alone is chosen on the
wrong one. The screen reports both, and the card is FAIL because the worst entry decides.

## The edge condition is a claim about the fastening

Change nothing but the rim and the same cover passes:

```text
access cover plate bending   PASS   safety factor 2.48 vs required minimum 2.00
                             Roark's Formulas, Table 11.4
access cover flatness        PASS   deflection 0.709 mm vs limit 1.500 mm
                             Roark's Formulas, Table 11.4
```

Clamping cuts the deflection by more than a factor of three. That is the largest single
lever on the page, which is why the default is `SIMPLY_SUPPORTED` and why declaring
`CLAMPED` is a statement about the hardware: a welded rim or a bolt circle stiff enough that
the edge really does not rotate. A bolted cover on a soft gasket is not clamped, and
claiming it is buys three times the stiffness the part does not have.

The citation changes with the edge, and it should: the simply supported case comes out of
the Navier series for Kirchhoff plates, the clamped case from Roark's tabulated
coefficients. The entry names whichever was used.

## What it takes and what it refuses

Declare the plan geometry one way or the other — `length` and `width` for a rectangle, or
`diameter` for a round blank, exactly one. Declaring both, or neither, is refused rather
than resolved: a cover is one shape or the other and guessing which would put a different
plate's coefficients on this one.

`deflection_limit` is optional and the flatness check appears only when it is given. That is
deliberate: a limit this library invented would be a number a reviewer could not trace, and
a plate with no stated flatness requirement genuinely has none to screen against — so the
card carries the bending check alone rather than an entry with a made-up threshold.

The material is a database id, and its E and yield drive both checks. A material the
database does not carry reports `not_evaluated` naming it, which is the same rule every
other pack follows: nothing here invents a modulus to produce a number.

## What this is not

Screening. Flat plate theory under uniform pressure, with the edge condition you declare —
not a stiffened panel, not a pressure-vessel head (see
[pressure equipment](pressure-equipment.md) for those), and not a substitute for the finite
element run a governing cover deserves. Every entry cites its source and carries the
screening label, and sign-off stays with the engineer of record.
