# Weld fatigue screening (why you have to choose the detail category)

Anvilate will not pick your weld detail category. It is the one input the screen
refuses to guess, and this page explains why — because it looks like an input you
should be able to default, and it is the input that decides the answer.

## The category, not the stress, decides the life

An EN 1993-1-9 fatigue check runs a stress range against an S-N curve anchored at the
**detail category** Δσ_C, the fatigue strength at 2 million cycles. Everything else on
the curve follows from it: the constant-amplitude limit Δσ_D ≈ 0.737·Δσ_C at 5M cycles,
the cutoff Δσ_L ≈ 0.405·Δσ_C at 100M, and the m = 3 / m = 5 slopes between.

Hold the stress range fixed at 80 MPa and change only the category:

| Detail category Δσ_C | Δσ_D | Δσ_L | Life at an 80 MPa range |
|---|---|---|---|
| 56 (a poor as-welded detail) | 41.3 MPa | 22.7 MPa | 686,000 cycles |
| 90 (a good one) | 66.3 MPa | 36.4 MPa | 2,850,000 cycles |
| 160 (plain rolled material) | 117.9 MPa | 64.8 MPa | 34,700,000 cycles |

Same load, same stress, same steel. The category spans a factor of **50 in life**. No
other input in the check has that leverage, which is exactly why defaulting it would be
a silent green with a fifty-fold error hiding inside it.

[`examples/welded_bracket_fatigue.py`](../examples/welded_bracket_fatigue.py) makes the
same point on a real spectrum: identical loading gives Miner damage 2.54 (FAIL, SF 0.39)
on a category-56 detail and 0.33 (PASS, SF 3.02) on a category-90 one.

## Why a machine cannot pick it for you

The category is not a property of the stress or the material. It is a judgement about
**geometry, weld type, direction of loading, inspection, and fabrication** together —
whether the toe is ground, whether the weld is transverse or longitudinal, whether a
backing bar was left in, whether the detail was inspected and to what standard. Two
brackets that a stress model cannot tell apart routinely sit three categories apart.

So Anvilate takes the category as a `Quantity` you supply, cites the clause, and — if
you do not supply one — returns `NOT_EVALUATED` rather than a number:

```python
from anvilate.analysis import weld_fatigue_scorecard

entry = weld_fatigue_scorecard(
    "weld fatigue",
    applied_cycles=cycles,
    stress_ranges=ranges,
    detail_category=None,          # you have not chosen yet
)
entry.status   # CheckStatus.NOT_EVALUATED — not a pass
```

That is the whole doctrine: a check you have not made reads as a check you have not
made.

## The corrections, and why they are visible

Two corrections move the category, and both are reported as their own factor rather
than folded silently into the number.

**Thickness (EN 1993-1-9 §7.2.2).** A thicker plate cracks at a lower range:
k_s = (t_ref/t)^n above the 25 mm reference, n = 0.2. A 40 mm plate keeps 91.0% of its
category; a 50 mm plate 87.1%. Below the reference there is no penalty.

```python
from anvilate.analysis import weld_size_effect_factor, weld_size_corrected_detail_category

k_s = weld_size_effect_factor(thickness=Quantity.parse("40 mm"))          # 0.9103
category = weld_size_corrected_detail_category(
    detail_category=Quantity.parse("90 MPa"), thickness=Quantity.parse("40 mm")
)
```

**Mean stress (EN 1993-1-9 §7.2.1).** A crack grows while it is held open, so the
compressive half of a cycle is less damaging — *but only if no tensile residual stress
is holding it open anyway*. In an as-welded detail the residual stress sits at yield and
the whole range counts. In a stress-relieved or non-welded detail the compressive part
counts at 0.6:

```python
from anvilate.analysis import weld_effective_stress_range, weld_mean_stress_factor

cycle = {"max_stress": Quantity.parse("100 MPa"), "min_stress": Quantity.parse("-100 MPa")}
weld_effective_stress_range(**cycle)                        # 200 MPa — as-welded, no bonus
weld_effective_stress_range(**cycle, stress_relieved=True)  # 160 MPa
weld_mean_stress_factor(**cycle, stress_relieved=True)      # 0.80
```

`stress_relieved` defaults to `False`. Claiming the bonus is a statement about how the
part was *fabricated*, not about its geometry, so it is yours to make deliberately. The
factor is 1.0 whenever there is no compressive part to discount, and reaches its 0.6
floor on a wholly compressive cycle.

## Scope

**Screened:** the EN 1993-1-9 nominal-stress trilinear curve from a declared category,
the constant-amplitude and cutoff knees, per-range endurance, Palmgren-Miner spectrum
damage, the allowable-range design inverse, and the thickness and mean-stress
corrections above.

**Not screened:** choosing the category (yours), hot-spot and fracture-mechanics
methods, weld residual-stress fields, variable-amplitude sequence effects beyond linear
Miner, environmental or corrosion-fatigue knockdowns, and any partial factor γ_Mf your
national annex applies — apply it to `required` yourself. These are T1 screens for early
design, not a substitute for a full fatigue assessment by a licensed engineer.
