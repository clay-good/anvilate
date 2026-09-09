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

## Spur gear meshes

The same shape one level up: four checks, and this time they are moved by **three different
parameters**, so a mesh failing two of them cannot be fixed by moving one number.

```python
from anvilate.packs.machinery import SpurGearMesh, screen_gear_mesh
from anvilate.units import Quantity

mesh = SpurGearMesh(
    pinion_teeth=18, gear_teeth=54,
    module=Quantity.parse("2 mm"),
    face_width=Quantity.parse("40 mm"),
    pressure_angle=20.0,                                 # degrees
    pinion_torque=Quantity.parse("180 N*m"),
    bending_geometry_factor=0.34,                        # AGMA Y_J, from the charts
    contact_geometry_factor=0.115,                       # AGMA I
    allowable_bending_stress=Quantity.parse("250 MPa"),
    allowable_contact_stress=Quantity.parse("1100 MPa"),
    pinion_modulus=Quantity.parse("207 GPa"),
    gear_modulus=Quantity.parse("207 GPa"),
    overload_factor=1.25, dynamic_factor=1.3, load_distribution_factor=1.2,
)
card = screen_gear_mesh(mesh, required_safety_factor=1.2)
```

| Check | Safety factor | What moves it |
| --- | --- | --- |
| tooth-root bending | 0.35 | `module` ↑ — and σ goes as **1/m²** |
| surface pitting | 0.53 | `module` ↑ — but σ_c goes as **1/m** |
| contact ratio | 1.37 | `pressure_angle` ↓; the module cannot move it at all |
| undercut | 1.00 | `pinion_teeth` ↑, to a whole count |

**The module enters twice, and that is the trap.** At a fixed pinion torque the tangential
load is `W_t = 2·T/(m·N₁)`, so it *falls* as the module grows. Bending stress therefore goes
as 1/m² and pitting as 1/m, and the two checks name two different modules for the same
shortfall — 3.71 mm for bending, 4.50 mm for pitting. The library's
`agma_module_for_bending_stress` inverts at a fixed tangential load and is **not** the hint
here; delegating to it would name a module far past the margin.

**The contact ratio is scale-invariant.** Every length in it is a multiple of the module, so
a bigger gear does nothing at all. What moves it is the tooth form: the contact ratio falls
monotonically with pressure angle across 14.5°–30° (swept in the test suite), so the hint is
directional on `pressure_angle` rather than a solved value.

**A geometric threshold takes no design margin on top.** The contact ratio and the undercut
limit are judged against their own thresholds, not against `required_safety_factor`:
screening them at 1.2 would silently demand a contact ratio of 1.44 and 22 teeth where the
standard asks for 1.2 and 18.

See [`examples/gear_mesh_scorecard.py`](../examples/gear_mesh_scorecard.py).

## The shaft's neighbours: the key and the bearings

A shaft that passes all three of its own limits says nothing about the joint that drives it
or the bearings that hold it. Both are in the pack for the same reason the three shaft
checks are on one card: they are the parts of a drive train that fail first and that a
shaft's own scorecard cannot see.

### The key

```python
from anvilate.packs.machinery import ShaftKey, screen_shaft_key
from anvilate.units import Quantity

key = ShaftKey(
    shaft_diameter=Quantity.parse("40 mm"),
    key_width=Quantity.parse("12 mm"),
    key_height=Quantity.parse("8 mm"),
    key_length=Quantity.parse("10 mm"),
    torque=Quantity.parse("400 N*m"),
    allowable_shear=Quantity.parse("100 MPa"),
    allowable_bearing=Quantity.parse("180 MPa"),
)
card = screen_shaft_key(key, required_safety_factor=2.0)
```

Shear acts across the key's **width**, `τ = 2·T/(d·w·L)`, and side bearing on half its
**height**, `σ_b = 4·T/(d·h·L)`. So the two limit states name two different lengths — 33.33
mm and 55.56 mm for this key — and which one governs is a question about the key's
proportions and its two allowables, not about the torque. It is the same shape as the shear
plate's two areas, one level down.

### The bearings

```python
from anvilate.packs.machinery import RollingBearing, screen_rolling_bearing
from anvilate.units import Quantity

unit = RollingBearing(
    dynamic_load_rating=Quantity.parse("35.1 kN"),      # C, from the catalogue
    static_load_rating=Quantity.parse("19.3 kN"),       # C0
    radial_load=Quantity.parse("4.2 kN"),
    axial_load=Quantity.parse("1.1 kN"),
    radial_factor=0.56, axial_factor=1.45,              # X and Y, from the table
    speed=Quantity.parse("1450 rpm"),
    required_life_hours=Quantity.parse("20000 hour"),
    required_static_factor=1.5,
)
card = screen_rolling_bearing(unit)
```

The equivalent dynamic load is `P = X·F_r + Y·F_a` = 3.95 kN, and `L₁₀ₕ = (C/P)^p·10⁶/(60·n)`
reaches 8,084 hours against the 20,000 asked for — a factor of 0.40. **Both levers are
catalogue ratings rather than dimensions**, because a bearing is selected and not machined:
the card names 47.47 kN as the least C that reaches the life, which is a number a reader
takes straight to the table.

`life_exponent` is a field rather than a default the screen guesses: 3 for a ball bearing
and 10/3 for a roller, and the same bearing rated as a roller reaches a substantially
different life. The static check is judged against the bearing's own
`required_static_factor` — s₀ is already a safety factor, and stacking the life check's
margin on top of it asks for a rating no catalogue table is written against.

**These two screens cite the textbook, not ISO 281 and ISO 76**, and that is deliberate. The
rules are the standards' and `anvilate.analysis.bearing` records that provenance; but a
scorecard entry naming a normative standard has to name its edition, and neither
`L₁₀ = (C/P)^p` nor `s₀ = C₀/P₀` identifies which edition it came out of — they are
unchanged across them. Inventing an edition would manufacture exactly the confidently-wrong
citation the [effectivity ratchet](standards-effectivity.md) exists to prevent.

See [`examples/drive_train_scorecard.py`](../examples/drive_train_scorecard.py).
