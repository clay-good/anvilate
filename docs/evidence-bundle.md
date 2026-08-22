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
#   exploration, callouts; not test-verified
#   [PASS] checks: 2 run, 0 failing, 0 not evaluated
#   [NOT_EVALUATED] verification: 0 of 1 planned tests performed, 0 verified by analysis
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
| `exploration` | PASS when a sweep found a feasible design | |
| `callouts` | the callout scorecard | see [typed callouts](typed-callouts.md) |
| `geometric tolerances` | PASS — every frame is legal at construction | see [semantic GD&T](semantic-gdt.md) |

## Sealing it

`assemble_evidence_bundle` hands the roll-up to the [attestation
layer](evidence-attestation.md), so the content-addressed statement carries the same
conclusion the reviewer saw rather than leaving a verifier to recompute it from the parts.
The sections travel in the predicate as canonical JSON text, not as a mapping: a dict field
on a frozen model is still writable after validation, and this one is inside the digest, so
a write to it would silently move the address of an already-signed statement.

The digest moves when a layer arrives, because the bundle is then claiming more.

## Worked example

`examples/lug_evidence_bundle_roll_up.py` — one lug in four states: checks only (PASS, not
covered), plan written (NOT_EVALUATED, same scorecard), proof load performed (PASS,
test-verified), and reviewed-then-changed (NOT_EVALUATED, and it says why).
