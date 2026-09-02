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

## The roll-up is not the bundle a reviewer receives

`render()` above is the **roll-up**: one line per layer, and the checks layer's line reads
`2 run, 0 failing, 0 not evaluated`. That is the right document for the attestation
predicate, which carries the scorecard in its own field beside it. It is the wrong document
to hand a person, and both export surfaces were handing it to one — `anvilate export`
printed it and the MCP `export_artifact` returned it, each calling it the evidence bundle
while it named no check, no margin and no clause.

`artifact-export` asks the bundle to carry "the scorecard with thresholds and measured
values", and its scenario is a senior engineer who receives **only the bundle** and re-runs
the analysis. So there are two renderings, and which one you want depends on who reads it:

| | who reads it | what it carries |
| --- | --- | --- |
| `render()` / `to_json_dict()` | the attestation predicate | the roll-up over layers, the assumptions, the disclaimer |
| `render_document()` / `to_document_dict()` | a person, and both export surfaces | all of that, plus every check on the card with its detail, its clause and its worked calculation, plus the spec they were computed from |

### The work, not just the verdict

A check that carries a derivation renders it under its line — the formula, the values put
into it, the result, and a line per symbol:

```text
checks:
  [PASS] padeye net tension: safety factor 6.67 vs required minimum 2.00 [ASME BTH-1 §3-3]
      σ_t = P / ((W − d) · t)
      σ_t = 60.0 kN / ((120.00 mm − 40.00 mm) · 20.00 mm)
      σ_t = 37.5 MPa
    where:
      P = 60.0 kN  (lifted load)
      W = 120.00 mm  (lug width across the hole)
      d = 40.00 mm  (pin hole diameter)
      t = 20.00 mm  (lug plate thickness)
      σ_t = 37.5 MPa  (net-section tensile stress)
```

A verdict and a clause are not enough to re-run anything, and re-running it is what this
document is for. The block is the one [the calculation report](calculation-reports.md)
prints and the one `anvilate check --show-work` prints, from the same renderer, so a
derivation cannot be described three ways. Checks that carry none — a material lookup, an
exemption — show their line and nothing under it.

The split is not tidiness. Folding the card into `to_json_dict()` would move the canonical
form hashed into every predicate — invalidating attestations already signed — and put two
copies of one scorecard inside one signed document, which is two chances for them to
disagree. A test asserts the predicate still carries the roll-up and not the document.

## The bundle carries the spec, so the scenario is performable

`artifact-export` asks for "the spec, the scorecard with thresholds and measured values ...
sufficient for an independent engineer to reproduce the run", and its scenario is a reviewer
who receives **only the bundle** and obtains the same scorecard. Carrying the checks made
half of that true. The other half was still false: a bundle named what passed and not the
load, the thickness or the material it passed on, so there was nothing to re-run.

`BundleSections.spec` is that half. It renders as the YAML a reader can paste straight back
into `anvilate check` — which is what "reproduce the run" has to mean in a tool with a text
front door, because then the bundle does not *describe* the inputs, it **is** them. A bundle
carrying none says so in a line of its own rather than leaving a reader to notice an absence.

The scenario is now a test rather than a sentence: screen a spec, export it through each
surface, discard the original, rebuild the spec out of the bundle, re-screen it, and require
the card to come back identical. A second test asks the question that matters for a text-first
tool — can the parser read back what the renderer wrote? — by pulling the YAML out of the
rendered bundle and screening it.

**Over MCP the handle names the pair.** At the shell the spec is in hand, but the export tool
receives only a subject handle, so `run_validation` publishes `{spec, scorecard}` together and
that is what the handle names. The alternative was an optional second `spec` handle on the
export call, which would make a bundle reproducible or not depending on how a client happened
to be written — and a bundle that is *sometimes* reproducible is one a reviewer cannot rely
on. This way there is no call sequence that produces the lesser bundle.

What the requirement asks for and the bundle still does not carry is everything downstream of
geometry: FEA assumptions, stress-field imagery, mesh statistics and convergence history,
solver input decks. None of it exists to carry.

## Five rules, and each is a judgement

**A layer that is absent is not a layer that passed.** `missing()` names what is not there
and `covers()` names what is, so "we did not test it" and "we tested it and it held" are
never the same sentence. A bundle carrying only a scorecard is a perfectly legitimate
screening bundle — it simply says so, in the same line as its verdict.

**A plan is not evidence, and the bundle inherits that.** A verification plan with nothing
performed is `NOT_EVALUATED` in its own layer, and it pulls the bundle down with it even
when every check passed. The physics passing is the *reason* to test, not a substitute for
having tested. `verified` is stricter than `status`: it is True only when a plan is present
and every item in it has a recorded, passing outcome.

**An artifact that left unvalidated is disclosed here, not only in its own header.** The
[export gate](export-gating.md) watermarks the file it writes. The fact the *bundle* adds is
that the artifact exists in the world carrying that mark. So a bundle whose checks all pass
and whose drawing was exported under an override is `NOT_EVALUATED`: nothing failed, and
something left the tool with no verdict behind it. An empty `exports` is not "nothing was
exported" — it is "this bundle does not say", and `missing()` names it.

**The screening label is not a field a caller can leave out.** Every rendered bundle carries
the screening disclaimer and an assumptions heading, and the disclaimer is a constant rather
than an argument — in a library, "non-dismissable" can only mean that there is no call that
renders a bundle without it. The assumptions are the caller's, and an empty list renders as
`none declared`, because a bundle that declared none and a bundle whose author forgot must
not look the same. Both travel in the attestation predicate, not only in the rendering.

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
| `export` | PASS only when every emitted artifact left validated | an unvalidated one is NOT_EVALUATED, and the artifact is named; see [the export gate](export-gating.md) |
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
