# Design: Timber connections

## What the source actually says

Task 1.1 was to read the source rather than recall it, and the reading changed three
things in this design.

**The equations are AWC Technical Report 12, not the NDS.** TR12 (2012 edition, written
against ANSI/AWC NDS-2012) publishes the *generalized* dowel equations in its Table 1-1,
and AWC gives it away. The NDS's Chapter 12 is the same model with the geometry already
substituted and the results tabulated, and it is copyrighted. So the module reads TR12
and says so, and what it returns is TR12's own output: the **unreduced 5% offset yield
value P**, not the NDS reference design value Z. Z is P divided by a reduction term R_d
per mode, and R_d is a table — the caller's input, with its citation. This is the same
line the member screens already draw at reference design values.

**Six modes, and two of them cannot happen in double shear.** TR12 Table 1-1 carries
Im, Is, II, IIIm, IIIs and IV. Footnote 1 to that table states that modes II and IIIm do
not apply to a double-shear connection: the geometry is symmetric about the main member,
so the rotation those two describe cannot form. The result reports them as *not
applicable with the reason* rather than omitting them, because a mode missing from a
list reads as a mode that did not govern rather than one nobody computed.

**The quadratic's sign is the trap.** Every mode but Im and Is is a quadratic, and
Table 1-1's layout puts the leading minus of `(−B + √(B² − 4AC)) / 2A` where a line
break hides it. With the positive B and negative C every mode has, `(+B + √…)` returns
roughly six times the right value — 2,414 lbf where the answer is 414 — which is large
enough to look like a capacity and not like an error. A dedicated adversary test pins
the sign, and all 54 values of TR12's own Example 3.1 (three gaps × six modes × three
geometries) are reproduced in `tests/test_dowel_yield.py`.

**The gap is carried through every mode.** TR12 keeps the space between members as a
lever arm in each quadratic. The clause an engineer reaches for first has no gap term,
and the loss is not small and has no floor: a 3/4 in double-shear splice loses 10.9% to
a quarter inch and 34.7% to an inch, and keeps falling. The gap is therefore a declared
field on the connection rather than an assumption.

## Where the code sits

`src/anvilate/analysis/dowel_yield.py` holds the equations, because they are a
closed-form analytical module with no document dependency — the same place the member
formulas sit. The pack screen that puts a connection in an itemized adjustment chain
(tasks 2.1–2.3) sits in `src/anvilate/packs/timber.py` and consumes it.

## Out of scope, deliberately

TR12 Tables 1-2 and 1-3 (hollow members, fasteners of varying diameter), withdrawal,
metal connector plates, split rings and shear plates. Each is a separate table and a
separate mode set; none is needed to screen the ordinary case.
