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

## What a model proposed is on the first line

`ReviewerDossier.summary()` is the line at the top of a review pane, and it listed the
counts, the verdict and whether a review had happened. It said nothing about which values a
language model proposed — priority 4 in the table above, collected by the dossier, and
visible only to a reader who walked the items. The case where that mattered most is the one
it hid: a model-origin check that is *also* failing sorts as failing, so its involvement
disappeared from the counts entirely. The summary now names them.

## And on every line, not only the first

"Visible only to a reader who walked the items" was the argument for putting model
involvement in the summary, and walking the items did not show it either. `ReviewItem`
carries the origin and its `headline` — the one line a reviewer skimming reads — dropped it:
all four origins produced the identical sentence. `origin_detail`, the only thing that ever
varied, is a caller-supplied string that defaults to empty, and `priority` states the origin
for two of the eight bands, neither of which a **failing** or **unevaluated** check can be
in. Those are the two a reviewer reads first.

The line says it now — `padeye net tension: fails (inputs a model proposed)` — through a
total map over the four origins, so a fifth is a `KeyError` at the one place that has to
decide what to say about it. `deterministic` is the one member that adds no clause, because
a value a cited closed form computed is the case a reviewer is *not* being asked to look at,
and a clause on every routine line makes the other three harder to see rather than easier.

The attribution is a bracketed tag rather than a clause appended to the sentence, and
rendering a real dossier is what settled that: appended bare it ran into the end of the
reason's own prose, and an unevaluated check read `did not run — the check is not there on
inputs nobody sourced`, which states something about inputs a check that did not run does
not have. Both halves — the origin and the detail — go inside one bracket, so a line never
ends in two of them.

## An origin stated as a string sorts where the member does

`{"padeye": "model"}` is what an origins map read out of JSON looks like, and it made the
check **routine**. `review_priority` compares the origin with `is`, against members, and
nothing coerced a caller's mapping on the way in — so a plain string matched none of them and
fell through to the passing rung. The check then dropped out of `attention_first`, which is
the list a reviewer reads first, while the `ReviewItem` it built carried
`DecisionOrigin.MODEL` all the same, because *that* field is coerced by pydantic. A dossier
whose summary named a model's involvement and whose attention list pointed at nothing.

The value is coerced where it is read, and an origin this library does not have is refused by
name rather than sorted as routine — which is the same standard as the section below, from
the other side.

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
*fit for service*, *code compliant*, *sealed by*, *guaranteed* — and the sweep in
`tests/conftest.py` runs it over **every entry the suite builds** — each name, detail,
reference, verdict sentence and substituted derivation — rather than over a corpus
somebody listed. The failure mode here is not a wrong number. It is a sentence someone
forwards.

Three of the phrases used to be bare words, and bare words are the wrong shape for this
list. *Sealed*, *stamped* and *warrants* each have an ordinary mechanical-engineering
sense with nothing to do with assurance — a sealed bearing, a **near-net stamping**, a
margin that *warrants* a reviewer's attention — and the library-wide sweep caught the
second one in the embodied-carbon pack, describing a forming process correctly. A gate
that fires on correct prose gets disarmed rather than obeyed. They are spelled in their
assurance sense now (*sealed by*, *signed and sealed*, *under seal*, *stamped by*, *bears
a stamp*, *warrants that*), which takes a person or a document as its object: no
description of a press operation says "stamped by".

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
