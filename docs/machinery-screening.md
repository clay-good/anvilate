# Machinery screening (rotating shafts)

A transmission shaft is sized by three limits that do not agree with each other. Static
strength under combined bending and torsion goes as the cube of the diameter; the fatigue
a *rotating* shaft sees — bending fully reversed every revolution while the torque stays
steady — goes as the cube too but against a different allowable; and torsional windup goes
as the **fourth** power. Which one governs moves with the shaft's length, its material and
its surface finish, so a shaft sized on the static check alone is routinely the wrong
diameter, and the error is not conservative.

The machinery pack runs all three on one card. The loads, the material and the corrected
endurance limit are the caller's; the arithmetic is Shigley's, on a prismatic solid round
shaft.

## What you get

```python
from anvilate.packs.machinery import TransmissionShaft, screen_shaft
from anvilate.units import Quantity

shaft = TransmissionShaft(
    diameter=Quantity.parse("40 mm"),
    bending_moment=Quantity.parse("250 N*m"),
    torque=Quantity.parse("400 N*m"),
    yield_strength=Quantity.parse("370 MPa"),
    length=Quantity.parse("600 mm"),
    shear_modulus=Quantity.parse("79.3 GPa"),
    allowable_twist=Quantity.parse("0.5 degree"),
    endurance_limit=Quantity.parse("200 MPa"),      # corrected: Marin factors applied
    ultimate_strength=Quantity.parse("690 MPa"),
)
card = screen_shaft(shaft, required_safety_factor=2.0)
```

- **combined bending and torsion** — the distortion-energy stress at the surface,
  `σ' = 32·√(M² + ¾·T²)/(π·d³)`, against the yield strength.
- **torsional twist** — `θ = T·L/(G·J)` end to end, against the allowable the caller
  declares. Nothing in the formula knows what a machine can tolerate; a positioning drive
  and a stirrer do not have the same answer, which is why the limit is an input.
- **rotating-shaft fatigue** — the DE-Goodman criterion, reported as a design factor
  rather than a diameter. The whole bracket goes as `1/d³`, so the factor at the declared
  diameter is exactly `(d/d₁)³` against the diameter the criterion allows at n = 1.

## The three checks disagree, which is the point

The 40 mm shaft above is comfortable on yielding and on fatigue and **fails on windup**:

| Check | Safety factor at d = 40 mm | Diameter it wants at n = 2 |
| --- | --- | --- |
| combined bending and torsion | 5.44 | 28.65 mm |
| rotating-shaft fatigue | 3.59 | 32.92 mm |
| torsional twist | 0.72 | 51.56 mm |

Sized on strength it ships at 28.65 mm and twists 2.6 degrees against a half-degree
limit. Every failing
entry names `diameter` and carries the value that clears its *own* limit — the shaft is
the largest of them, and which one that is cannot be read off the loads.

## What is not screened

A check whose inputs the shaft does not declare comes back `NOT_EVALUATED` naming the
missing field, never a quiet pass: no `endurance_limit` means no fatigue verdict, not a
fatigue verdict of "fine". The endurance limit is the **corrected** one — the Marin
surface, size and reliability factors, and the fatigue stress concentration of a keyway,
fillet or shoulder, are applied before the value arrives, because they are properties of
the shaft's surface and geometry rather than of the loads the model carries.

See [`examples/transmission_shaft_scorecard.py`](../examples/transmission_shaft_scorecard.py).
