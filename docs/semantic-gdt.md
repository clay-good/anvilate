# Semantic GD&T

**A feature control frame is a sentence with a grammar, and the grammar is enforceable.**
Drawings carry the frame as symbols and leave the checking to whoever reads it, which is
why the same handful of errors keep reaching the shop. Here the rules live in the
constructor: an illegal frame is not built.

```python
FeatureControlFrame(
    characteristic=Characteristic.POSITION,
    tolerance=Quantity.parse("0.2 mm"),
    feature_type=FeatureType.FEATURE_OF_SIZE,
    material_condition=MaterialCondition.MMC,
    modifiers=(FrameModifier.DIAMETER,),
    datums=(DatumReference(letter="A"),
            DatumReference(letter="B", boundary=DatumBoundary.MMB, is_feature_of_size=True),
            DatumReference(letter="C")),
).render()
# ⌖ | Ø0.2 mm Ⓜ | A | B Ⓜ | C
```

## The legality rules

| Rule | Why the illegal version is wrong |
| --- | --- |
| Form takes **no** datum | Flatness is the surface against itself; a datum means the author meant parallelism |
| Orientation, location, runout **require** one | A relationship needs the other end |
| Profile takes datums **or not** | With them it locates; without them it controls form only |
| At most **three** datum references, no repeats | Three constrain six degrees of freedom; a fourth over-constrains |
| Ⓜ/Ⓛ only on a **feature of size** | A surface has no size, so it has no material condition — the modifier fails to parse |
| MMB/LMB only on a datum that is a **feature of size** | A datum plane has no boundary to shift |
| Ø zone only on a feature of size | A Ø zone is the zone of an axis, and a surface has no axis |
| Ⓟ only on position/orientation of a feature of size | A projected zone controls a fastener's attitude above the surface |

## The edition is not decoration

**ASME Y14.5-2018 eliminated concentricity and symmetry.** Both were median-point controls
that a position or runout callout expresses better and that almost nobody inspected
correctly. The 2009 edition carries them.

So `Y14Edition` is a declared input, and a 2018 frame using either is refused with the
reason. A drawing that uses them is a 2009 drawing — and saying so is the difference
between a legacy callout and a mistake. Everything else in the fourteen-characteristic set
is common to both, so the gate is exactly those two.

## What a position tolerance contributes to a stack

The one number a GD&T callout owes the [tolerance-stack](../src/anvilate/tolerance/stackup.py)
layer.

A zone of total width t permits the axis anywhere within **±t/2** of basic in any single
direction. For a *diametral* zone Ø t the extreme in any one direction is likewise ±t/2, at
the point where the axis touches the cylinder along that direction. So Ø0.2 contributes
±0.1 mm, and at MMC with 0.1 mm of bonus earned, ±0.15 mm.

**That conversion is worst case, and deliberately so.** The true 2D distribution puts most
of the probability well inside the extreme, so feeding this half-band to an RSS or Monte
Carlo stack as though it were a 1D uniform band overstates the spread — and produces a
number that is neither worst case nor statistical. Use it in a worst-case stack; a
statistical stack wants the 2D distribution, not this scalar.

Bonus tolerance is refused outright on an RFS frame. It is not a conservative
simplification of anything: it is tolerance the drawing did not grant.

See [`examples/feature_control_frame_legality.py`](../examples/feature_control_frame_legality.py).

## Scope

This models and validates the callout. It does **not** verify that a part meets it, resolve
a datum reference frame into a coordinate system, or compute a virtual condition boundary.
Drawing rendering beyond `render()`'s text form, AP242 semantic PMI population, and QIF
characteristic mapping wait on the export layers they belong to.
