# Typed MBD callouts

**Callouts are inputs, not annotations.** A drawing that says "as forged, black oxide,
heat treat to Rc 38" is describing three things the checks already take as parameters and
were never given. A part screened as a bare, polished, annealed specimen is not the part
on the drawing, and the difference is not cosmetic: on a 25 mm AISI 4140 journal it is a
safety factor of 2.52 against 1.08.

[`anvilate.gdt`](semantic-gdt.md) types the geometric half of model-based definition. This
is the other half.

```python
from anvilate.callouts import CalloutSet, ProductionMethod, SurfaceFinish, callout_scorecard
from anvilate.units import Quantity

finish = SurfaceFinish(
    scope="shaft_journal", roughness=Quantity.parse("12.5 um"), method=ProductionMethod.AS_FORGED
)
card = callout_scorecard(CalloutSet(callouts=(finish,)), ultimate_strength=Quantity.parse("655 MPa"))
print(card.entries[0])
# [PASS] surface finish at shaft_journal: [3ae5c2487be1c5dd] as forged, Ra 12.5 µm
#        → Marin surface factor k_a = 0.429 at S_u = 655 MPa [Shigley's ... k_a = a·S_u^b ...]
```

## What each callout does to a check

| Callout | The check it feeds | What it changes |
| --- | --- | --- |
| `SurfaceFinish` | fatigue | the Marin surface factor k_a, which the fatigue module takes as a bare float |
| `Coating` | fits, thread engagement | states the effect — outside dimensions grow 2t, a 60° thread's pitch diameter grows **4t** — and reports NOT_EVALUATED, because no fit or thread class is supplied to check it against |
| `HeatTreatment` | material resolution | which database record is legitimate — or NOT_EVALUATED when none is |
| `ProcessNote` | nothing yet | typed and carried; the scorecard says plainly that no check reads it |
| `FreeTextNote` | nothing, ever | stored, distinguishable, excluded from `consumable()` |

## Identity is what the characteristic *is*

The persistent identifier is derived from the callout's kind, its scope tag, and what
distinguishes two callouts of that kind at that scope — a structured note's category, a
free-text note's sequence number — **never from its value**. So:

- revising a finish from 12.5 to 3.2 µm Ra keeps the identifier, and the diff reports one
  *change* rather than a deletion plus an unrelated addition;
- adding a finish to a new face mints a new one;
- it needs no counter and no database to stay stable across a geometry regeneration.

That is what lets a callout, the check that consumed it, and the inspection that verifies
it name the same characteristic over revisions — the MBC-class property, without the
registry.

One characteristic carries one value. Two finishes on the same face is a construction
error, not a refinement — and the scope is normalized, so a trailing space cannot walk one
past that rule. The encoding behind the identifier is length-prefixed rather than
delimiter-joined, for the same reason DSSE's pre-authentication encoding is: a delimiter is
unambiguous only while no field can contain it.

Resolution against the tag graph is separate and explicit. `CalloutSet.resolved_against`
refuses a callout scoped to a face nothing defines, and `callout_scorecard` does the same
when it is handed `known_tags` — because a callout nothing can consume screens exactly like
a callout nobody wrote.

## Three positions worth stating

**A roughness number is not a production method.** Shigley's surface-factor table is
indexed by *how the surface was made*, not by its Ra, so the callout carries both and the
derivation uses the method. Polished returns k_a = 1.0 by definition rather than by fit,
and the fit is capped at 1.0 because no real surface improves on the rotating-beam
specimen.

The Ra is not decoration either: it is checked against the range that method typically
attains, so **"as-forged, 0.4 µm Ra" is surfaced as a contradiction** rather than averaged
into something plausible. The bands overlap on purpose — the point is not to grade a
surface but to catch a callout that cannot be both things at once.

And the bands are Ra bands, so an **Rz** callout does not get graded against them. Rz runs
roughly four to seven times Ra for the same surface, so the mismatch is wrong in both
directions at once: an ordinary ground surface at Rz 3.2 µm reads as a contradiction, and
an impossible as-forged surface at Rz 6.3 µm passes. No Rz bands are published here, so the
consistency check does not run and the entry says so — the surface factor is still derived,
because it comes from the method rather than the roughness.

**The plated thread multiplier is four, and it is derived.** The coating is deposited
normal to a flank inclined at 30° to the thread axis, so a radial thickness t displaces the
flank by t/sin(30°) = 2t, and the pitch diameter spans two flanks: 4t. Getting this wrong
by the factor of two is the classic plated-thread interference — an external thread plated
to the top of its range can lose its entire class allowance and refuse to assemble. The
constant in the module is written as `2.0 / sin(radians(30.0))` and the suite checks the
derivation against it.

**A declared condition the database cannot back stops the check.** Conditions live in the
record identity here (`AA-6061-T6`, `AISI-1018-CD`), so resolution is a lookup, not an
inference. `AISI-4140` in condition `QT` has no record, so the check reports NOT_EVALUATED
naming the condition rather than screening the untreated row and calling the result a
screening of the treated part. A hardness range travels with the callout for the drawing
and the inspection, and is never converted into a strength.

## Anchoring the surface-factor constants

The published table gives the constants for S_u in MPa *and* in kpsi, and the two sets are
not independent: k_a is a pure number, so `a_kpsi = a_MPa · (MPa per kpsi)^b` must hold at
every S_u. It does, to about 0.2% on every row:

| finish | derived a_kpsi | published |
| --- | --- | --- |
| ground | 1.34086 | 1.34 |
| machined | 2.70377 | 2.70 |
| hot-rolled | 14.42511 | 14.4 |
| as-forged | 39.83296 | 39.9 |

Three round to the published figure exactly; as-forged lands 0.17% low, which is the
rounding of the published constants themselves (b = −0.995 is quoted to three decimals and
the exponent is nearly −1, so a_kpsi is acutely sensitive to it). That identity is the
cheapest available check that the constants were transcribed correctly — no external source
needed — and the suite asserts it at 3e-3 rather than trusting the transcription.

## Scope

Screening, in the library's usual sense. Anvilate consumes declared callouts; it does not
recommend a finish or a coating, and it does not author a coating-process ontology. The
typical-roughness bands are screening ranges for catching a self-contradictory callout,
not a process-capability database.

## Worked example

`examples/plated_shaft_callouts_change_the_verdict.py` — the journal above: passing at
2.52 with the drawing ignored, failing at 1.08 once the as-forged finish is read, back to
2.04 after a revision the diff reports as one change to one characteristic.
