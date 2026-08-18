# Below-the-hook lifting devices (ASME BTH-1)

**Screening, not stamped design.** BTH-1 also governs the lifter's welds and
connections, its stability under an off-centre pick, its proof test, and its marking.
This screens member and pin-plate stresses against BTH-1 allowables and reports the
fatigue obligation. A green scorecard does not make a lifter compliant, and does not replace a
qualified engineer's stamp.

Every custom lifter — spreader beam, lifting beam, plate-clamp frame — legally needs
BTH-1-compliant design under OSHA and ASME B30.20, and the practice is almost entirely
spreadsheet-bound. No open-source implementation existed.

## The design factor is a judgement, and it is 50% of the answer

BTH-1's allowable stresses are not fixed numbers. They are the material's strength over
a **design factor** the designer selects:

| | N_d | When |
| --- | --- | --- |
| **Design Category A** | 2.00 | Predictable loads, defined and controlled conditions, closely supervised use |
| **Design Category B** | 3.00 | Anything less — including the ordinary case of a lifter that leaves the bay it was designed for |

Nothing in the geometry says which applies. The worked example is a 3 m spreader beam
running 107.6 MPa in bending: the allowable is 124.0 MPa as Category A and 82.7 MPa as
Category B, so the same beam under the same load **passes at SF 1.15 and fails at 0.77**.

A margin quoted without its category cannot be checked. That is why the category is a
typed input here rather than a bare `required_safety_factor` a caller passes in and a
reviewer cannot trace — and why every scorecard detail names it.

## The allowables

| Limit state | BTH-1 | Value |
| --- | --- | --- |
| Tension, gross section | §3-2.1 | `F_t = S_y / N_d` |
| Tension, net section | §3-2.1 | `F_t = S_u / (1.20·N_d)` |
| Shear | §3-2 | `F_v = 0.60·S_y / N_d` |
| Bending, compact and braced | §3-2 | `F_b = S_y / N_d` |
| Pin bearing, clearance fit | §3-3.3 | `F_p = 1.25·S_y / N_d` |

They all scale with the same category, so Category B is exactly 2/3 of Category A for
every one of them — the identity the test suite pins, since a coefficient transcribed
into the wrong allowable would break the ratio for that one alone.

Note the net-section row is not `S_u/N_d`. BTH-1 does not use one factor per category:
yielding and buckling take N_d (2.00 / 3.00), while **fracture and connection design take
1.20·N_d**, which the Code tabulates directly as 2.40 and 3.60. That extra 1.20 is why a
net-section rupture check is stricter than a gross-section yield check on the same
member, and it is a property of the Code rather than of the material.

Two limits before leaning on the bending value: `F_b = S_y/N_d` assumes the member is
**compact and laterally braced**, and `F_p` is the **clearance-fit** pin value. A
non-compact or unbraced member takes BTH-1's reduced forms, which are not computed here;
a pin in sliding contact under load takes a much lower allowable, because that one is a
wear limit rather than a strength one.

## The fatigue obligation is a cliff, not a slope

Service Class comes from the design life in load cycles:

| Class | Cycles | Fatigue analysis |
| --- | --- | --- |
| 0 | 0 – 20,000 | **Not required** |
| 1 | 20,001 – 100,000 | Required |
| 2 | 100,001 – 500,000 | Required |
| 3 | 500,001 – 2,000,000 | Required |
| 4 | over 2,000,000 | Required |

Class 0 is the only exempt class, and the 20,000-cycle boundary is the only one in the
table that changes whether a whole analysis is required rather than which curve it uses.
A design life estimated as "about twenty thousand lifts" lands exactly on it, so it is
worth being deliberate about which side the estimate falls.

A device at Class 1 or above with no cycle data comes back `NOT_EVALUATED`, never a pass:

```
Category A (N_d = 2.00) -> not_evaluated
  beam bending               pass           SF 1.15
  lug net tension            pass           SF 8.15
  fatigue (Class 1)          not_evaluated  SF   —
```

Both member checks pass and the card still does not. That is the honest roll-up — the
exemption Class 0 earns does not transfer to a device that has not earned it. See
[`examples/spreader_beam_bth1_category.py`](../examples/spreader_beam_bth1_category.py).

## The device: rated load is not design load

`LifterDevice` types the whole lifter — rated load, self weight, category and service
class — and `screen_lifter_device` routes every check through it. Two properties of the
model do real work:

**`self_weight` has no default.** BTH-1 §3-1.2 has the design consider the device's own
weight alongside the rated load, and the hook carries both. Requiring the field means
the most common omission in lifter design cannot happen silently: a designer who has
established it as negligible passes zero deliberately, and that shows on the card.

**`design_load` = rated load + self weight, and it applies at the *upper* attachment.**
A lug below the pickup point carries the rated load alone. The distinction is in the
model's docstring because applying the device weight everywhere is as wrong as applying
it nowhere.

A 100 kN spreader beam weighing 8 kN, with a 17 mm upper bail plate (180 mm wide, 60 mm
hole), A36, Category B:

| Bail pin bearing, checked against | Stress | vs F_p = 104.2 MPa | Verdict |
| --- | --- | --- | --- |
| rated load, 100 kN | 98.0 MPa | SF 1.06 | PASS |
| rated + self weight, 108 kN | 105.9 MPa | **SF 0.98** | **FAIL** |

Eight percent more load turned a pass into a fail, because the margin was 6% to begin
with. The same 108 kN bail as Category A passes at 1.48. See
[`examples/spreader_beam_device_screen.py`](../examples/spreader_beam_device_screen.py).

### The limit state is named, not the allowable

`LifterMemberStress` carries a `BTH1LimitState` rather than an allowable, so the design
factor reaches every check through the standard's own routing. A shear stress checked
against the tension allowable would pass at 1/0.60 = **1.67x the margin it has earned**,
and that is a typing decision, not a convenience one. `screen_lifter_device` also refuses
allowables built for a different category than the device declares, rather than screening
every member 50% high.

`bth1_pin_plate_scorecard` screens a pin-connected plate's net-section tension against
`S_u/(1.20·N_d)` and its pin bearing against `1.25·S_y/N_d`. Note the general
`screen_lifting_lug` in the structural pack checks both states against **yield** at a
caller-chosen margin — a reasonable generic check, but not the BTH-1 one. Use the
BTH-1 form when the answer has to cite BTH-1.

Yield and ultimate strengths, and any fatigue allowable stress range, follow the
user-supplied-allowables doctrine: they are the caller's, read from the certificate or
the applicable detail table. None of BTH-1's tables are reproduced here.
