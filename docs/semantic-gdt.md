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

**A frame refuses a field it does not declare.** `DatumReference` takes a `boundary`
(RMB/MMB/LMB), and it used to accept `material_condition=` — a name from the *tolerance*
compartment, not the datum one — silently ignore it, and hand back a datum at RMB. The frame
then rendered `|A|B|C` for something a caller had written as B at MMB, which is a different
instruction to a fabricator: a datum simulated at its maximum material boundary allows a
datum shift that one at RMB does not. Both GD&T models forbid unknown fields now.


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

## One declaration, three consumers

The same frame is read by three layers, and a declaration changed in the model has to
reach all of them. A consumer that quietly ignores a modifier is not a rounding error: on
a drawing it is a callout **looser** than the one declared, and in QIF it is one
**tighter**.

| Consumer | Where | What it produces |
| --- | --- | --- |
| Text | `FeatureControlFrame.render()` | `⌖ \| Ø0.2 mm Ⓜ \| A \| B Ⓜ \| C` |
| Quality interchange | [`export.qif.qif_characteristic_mapping`](../src/anvilate/export/qif.py) | a QIF characteristic definition, with what it still owes named in `unresolved` |
| Drawing | [`export.fcf.frame_drawing`](../src/anvilate/export/fcf.py) | the boxed, compartmented callout as lines, arcs and text |

Propagation is tested rather than assumed: add the Ø, promote RFS to Ⓜ, add a datum, or
change the characteristic, and each change is asserted to move all three.

## The drawing, and why the symbols are geometry

`frame_drawing()` returns primitives in millimetres — the frame box, its dividers, every
symbol, and the two kinds of text a frame carries — and
[`export_feature_control_frame_dxf`](../src/anvilate/export/dxf.py) writes them to a DXF on
its own `GDT` annotation layer, so a fabricator's tool path never picks the callout up.

**Every geometric symbol is drawn as lines and arcs, not typeset as a character.** A ⌖ or
an Ⓜ written into a DXF as text renders correctly only where the viewer happens to have a
font carrying the glyph; where it does not, the callout shows a missing-glyph box or
silently loses its modifier, and the drawing then says something other than what the model
declares. Only the digits of the tolerance and the datum letters are left as text, and the
permitted character set is closed — the frame's width allowance was checked for those
characters and nothing else, so anything outside the set is refused rather than laid out
on an assumption nobody tested.

The tolerance is **converted to millimetres**, because the DXF is a millimetre document. A
frame declared in inches whose number crossed unchanged would read 25.4 times tighter than
the one declared.

**The proportions were read out of a published symbol chart, not recalled.** Every symbol
is dimensioned as a multiple of the character height `h` in the Genium *Drafting Manual*
Section 6.1 (February 1997, based on ASME Y14.5M-1994). Three would have been wrong from
memory:

- **Symmetry** is three horizontal lines of 2h, 1.2h and 2h at 0.5h spacing — the middle
  one is the short one, and it is not an equals sign.
- **Cylindricity's** two lines stand at 60° and are drawn *tangent* to its circle, which
  is the property the test asserts rather than a bounding box the code produced.
- **Ø's 1.5h is the symbol's height, not the slash's length.** Read as the length it draws
  a Ø only 1.3h tall, barely taller than the circle it crosses — which is the defect
  rendering a real frame caught and a unit test would not have.

The frame stands 2h tall with each compartment padded 0.5h either side of its content, and
nothing in a compartment may cross a divider — a glyph that straddles one is a modifier a
reader assigns to the wrong compartment.

See [`examples/feature_control_frame_drawing.py`](../examples/feature_control_frame_drawing.py).

## Scope

This models and validates the callout. It does **not** verify that a part meets it, resolve
a datum reference frame into a coordinate system, or compute a virtual condition boundary.
The drawing consumer renders the frame itself, not the leader, the datum feature symbol, or
its placement on a part — those belong with the drawing-generation layer. AP242 semantic PMI
population waits on the STEP export it belongs to.
