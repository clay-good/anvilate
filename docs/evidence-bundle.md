# The assembled evidence bundle

**One roll-up over every layer, and it is never better than its worst section.**

Anvilate grew its cross-cutting layers one at a time, and each ships its own verdict: the
scorecard rolls up the checks, the [verification plan](verification-planning.md) rolls up
the physical tests, the [reviewer dossier](responsible-charge-review.md) rolls up what a
licensed engineer still has to look at. Separately they are all correct. Nobody had written
down what the *part* is.

```python
from anvilate.bundle import BundleSections

sections = BundleSections(scorecard=card, verification=plan)
print(sections.render())
# bundle NOT_EVALUATED over 2 layers (checks, verification); not covered: review,
#   exploration, callouts, geometric tolerances; not test-verified
#   [PASS] checks: 2 run, 0 failing, 0 not evaluated
#   [NOT_EVALUATED] verification: 0 of 1 planned tests performed, 0 verified by
#     analysis, 0 unresolved
```

## Three rules, and each is a judgement

**A layer that is absent is not a layer that passed.** `missing()` names what is not there
and `covers()` names what is, so "we did not test it" and "we tested it and it held" are
never the same sentence. A bundle carrying only a scorecard is a perfectly legitimate
screening bundle — it simply says so, in the same line as its verdict.

**A plan is not evidence, and the bundle inherits that.** A verification plan with nothing
performed is `NOT_EVALUATED` in its own layer, and it pulls the bundle down with it even
when every check passed. The physics passing is the *reason* to test, not a substitute for
having tested. `verified` is stricter than `status`: it is True only when a plan is present
and every item in it has a recorded, passing outcome.

**A review that no longer applies is not a review.** The dossier already detects that the
artifact moved under a review record. Here that degrades the bundle rather than sitting as
a flag somebody has to notice — the state looks identical to "reviewed" from the outside,
which is exactly why it has to be loud from the inside.

## The precedence

FAIL, then NOT_EVALUATED, then OVER_MARGIN, then PASS — identical to
[`Scorecard`](../src/anvilate/scorecard.py) by construction rather than by coincidence. A
second roll-up that ordered them differently would be a second place for one layer's
blocking failure to hide behind another layer's gap.

| Section | Contributes | Notes |
| --- | --- | --- |
| `checks` | the scorecard's own status | required; a bundle over an empty scorecard is refused |
| `verification` | the plan's status | NOT_EVALUATED until every planned test has a result |
| `review` | the dossier's status, or NOT_EVALUATED if the record is stale | |
| `exploration` | **nothing** — informational | a sweep says what the *space* contains, not whether this part is sound |
| `callouts` | the callout scorecard | see [typed callouts](typed-callouts.md) |
| `geometric tolerances` | **nothing** — informational | that the callouts parse is not a verdict on the part; see [semantic GD&T](semantic-gdt.md) |

An **informational** section is carried, rendered, and counted in `covers()`, and it does
not enter the roll-up. Letting exploration in would mean an exhaustive sweep with nothing
feasible in it condemning a part that passes every check on its own drawing.

## Sealing it

`assemble_evidence_bundle` hands the roll-up to the [attestation
layer](evidence-attestation.md), so the content-addressed statement carries the same
conclusion the reviewer saw rather than leaving a verifier to recompute it from the parts.
The sections travel in the predicate as canonical JSON text, not as a mapping: a dict field
on a frozen model is still writable after validation, and this one is inside the digest, so
a write to it would silently move the address of an already-signed statement.

**The statement carries one verdict, and it is the roll-up.** The predicate's headline
`status` reads the assembled sections when there are any, not the scorecard — a signed
document reading `"status": "pass"` at the top with `"sections": {"status": "fail"}`
underneath would put the optimistic one where standard tooling looks.

The digest moves when a layer arrives, because the bundle is then claiming more.

## Worked example

`examples/lug_evidence_bundle_roll_up.py` — one lug in four states: checks only (PASS, not
covered), plan written (NOT_EVALUATED, same scorecard), proof load performed (PASS,
test-verified), and reviewed-then-changed (NOT_EVALUATED, and it says why).
