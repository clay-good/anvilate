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

## The two connection factors that are equations

Table 11.3.1 lists eight adjustment factors for a dowel connection's lateral value. Six
are table lookups and stay the caller's. Two are published equations, and a formula is
not a table, so both are derived:

- **C_g, NDS Equation 11.3-1.** Reproduces all 132 published values of Tables 11.3.6A
  (wood side members) and the four spot rows read from 11.3.6C (steel side plates),
  which is the anchor: the tables *are* the equation evaluated at a declared set of
  inputs, so a transcription error disagrees with all of them at once. The metal path
  has its own load/slip modulus, 270,000·D^1.5 against 180,000, and no wood table can
  tell whether that branch was taken — hence the second anchor.
- **C_Delta, NDS §12.5.1.2.** The proportional half is `actual / minimum for C_Delta =
  1.0`. The half a formula alone would miss is the floor: below the minimum for
  C_Delta = 0.5 the detail is *not permitted*, and `actual / minimum` keeps returning a
  number all the way to zero, every one of which reads as a legal connection with a
  small factor. That is a refusal here, not a factor.

The minimums themselves (Tables 12.5.1A-D, multiples of D) are the caller's with their
citation, as task 2.2 asks: which row applies depends on the direction of loading and on
whether the species is a softwood, and neither is something a diameter knows.

**Both factors read the same spacing**, which is the finding the example carries: fit
more fasteners into a fixed end zone and both fall, so the row's effective count
`n · C_g · C_Delta` is not monotone in n. Six 3/4 in bolts in a 15-inch row are worth
5.70 bolts; the seventh makes the row 3.9% weaker; the eighth is refused.

## The screen, and the step that looks right

`screen_timber_connection` takes a `TimberConnection` — one fastener's geometry, the
caller's reduction terms, the Table 11.3.1 chain, the fastener count and the demand — and
emits one check.

**The reference design value is the least of P/R_d over every reachable mode, not
P_governing/R_d.** NDS gives the bearing modes a reduction term of 4.0 and the hinge
modes 3.2, so P and Z do not rank the modes the same way. A 1/2 in bolt with a 0.6 in
main member has mode IIIm governing P and mode Im governing Z; dividing only the smallest
P by its own term returns 506 lbf where the answer is 420. The screen divides every mode,
names both when they differ, and `tests/test_timber_pack.py` writes down the wrong number
so it cannot come back.

A mode with no reduction term declared makes the whole check `NOT_EVALUATED`, naming the
modes. A connection screened on three of its five reachable modes has been screened on
the wrong one as often as not — so a partial declaration is not a partial answer.

R_d is recorded as an `AppliedFactor`: the check is judged at 1.0, so the conservatism the
reader is relying on would otherwise be nowhere on the card.

## What the screen does not check, deliberately

The yield limit equations describe the fastener and the wood bearing on it, and not the
wood *around* the group. A row of closely spaced fasteners loaded parallel to grain can
tear a block out of the member before any fastener reaches the mode its capacity was
computed from. NDS 2018 Appendix E (non-mandatory) covers that — net section tension E.2,
row tear-out E.3, group tear-out E.4 — and none of it is screened.

The catalogue carries no failure mode for it either, so `timber_connection` goes in
`docs/api/uncatalogued-elements.txt` and the screen in the declares-none list. A screen
that declared a mode it does not address is the lie those ratchets exist to prevent.
