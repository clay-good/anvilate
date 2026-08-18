# Responsible-charge review

Anvilate's output eventually reaches a licensed engineer who must decide whether to put
their seal on it. **That decision is theirs, and nothing here can be delegated into it.**
The NSPE Board of Ethical Review has held that failing to maintain responsible charge
over an AI tool's output before sealing is unethical, with the framing that such a tool
is like an engineering intern: the engineer sets the constraints, does not blindly accept
the output, and must satisfy themselves before sealing.

This module produces the raw material for that scrutiny, assembled *for a reviewer*.

## It orders by what deserves attention, not by severity

A scorecard in declaration order does not help the person deciding where to look. The
dossier fixes the order — and the order is "most likely to change the engineer's
decision", which is not the same as "worst first":

| Priority | Why it is there |
| --- | --- |
| 1. not evaluated | **Ahead of the failure.** A FAIL is already visible and already blocking; a NOT_EVALUATED is the check that silently is not there, and it is the one a reviewer can miss entirely. |
| 2. failing | |
| 3. unattributed assumption | The verdict is only as good as the input nobody recorded the origin of — even at a safety factor of 3.0. |
| 4. model assumption | A value a language model proposed, with its version. |
| 5. thin margin | Passes within 10% of its requirement: the band where an assumption the reviewer disagrees with flips the answer. |
| 6. over margin | Passes above its band — possibly over-designed. |
| 7. routine | |

The ordering is fixed and documented rather than tuned, so two runs over the same inputs
produce the same dossier and a diff between them means something. Ties keep the
scorecard's own order, so it is total.

## A check with no recorded origin is unattributed, never routine

`build_dossier` defaults a missing origin to `UNATTRIBUTED`, which sorts third. Defaulting
it to something reassuring would make the whole attribution feature worse than useless, by
making its absence invisible — the same silent green this library exists to refuse.

## A review is bound to what was reviewed

`ReviewRecord.covers_digest` is a hash of the scorecard's full content **and the toolchain
identifier**. Change a load, a material, or the library version and the digest moves and
the record stops applying:

```
AFTER REVIEW
  ... reviewed by A. Engineer, P.E. on 2026-08-17.
AFTER SOMEBODY TRIMS THE SECTION
  ... a prior review no longer applies — the artifact changed under it.
```

Including the toolchain is the part that is easy to leave out and matters most: the same
inputs through a different library version are a different piece of work. A stale record
is carried through and *flagged*, not dropped — "there was a review and it no longer
covers this" is different information from "there was never a review", and from the
outside the two look identical.

## Review never changes a verdict

An engineer may record an accepted exception against a failing check. That is their
prerogative and it is recorded. **The check still renders FAIL and the scorecard still
rolls up to FAIL.** A tool that let a review turn a failure into a pass would be
laundering the engineer's judgement into an appearance of analysis.

## The language gate

Anvilate has no "approved" state and does not certify. `PROHIBITED_ASSURANCE_LANGUAGE`
lists the vocabulary a screening tool must never use about its own output — *certified*,
*fit for service*, *code compliant*, *sealed*, *guaranteed* — and two gates sweep for it:
one over every rendering this module produces, and one in `tests/test_contract.py` over
every scorecard detail and reference string the packs emit. The failure mode here is not
a wrong number. It is a sentence someone forwards.

Docstrings are deliberately out of scope. Prose about the policy has to be able to name
the thing it prohibits, and gating that is how a language gate becomes unusable and then
gets deleted.

See [`examples/bracket_reviewer_dossier.py`](../examples/bracket_reviewer_dossier.py).

## What Anvilate cannot certify

All of it. This is a screening library: it computes closed forms, cites the clause each
came from, and says plainly when a check did not run. It does not know your jurisdiction,
your project's acceptance criteria, or what the drawing does not show. Responsible charge
is the engineer's, and the most useful thing this dossier does is make it cheap to
exercise rather than pretending to discharge it.
