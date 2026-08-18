# Tasks: Responsible-charge review

## 1. Contracts

- [x] 1.1 Dossier assembly type over existing provenance, scorecard, and iteration history
- [x] 1.2 Decision-origin attribution (user / deterministic / model + version /
      unattributed)
- [x] 1.3 Review record type (reviewer, date, artifact digest, scope, outcome,
      exceptions)

## 2. Implementation

- [x] 2.1 Deterministic, documented review-priority ordering
- [x] 2.2 Review record binding to content digest; invalidation on any change
- [ ] 2.3 Report-pane and evidence-bundle rendering — PARTIAL: ReviewerDossier.summary()
      and ReviewItem.headline are the renderings, and both are gated for prohibited
      language; wiring them into the HTML report pane is report-layer work
- [x] 2.4 AI-involvement summary suitable for disclosure

## 3. Tests

- [x] 3.1 Any spec or toolchain change invalidates a prior review record
- [x] 3.2 Thin-margin, unevaluated, and model-assumption items surface in priority order
- [x] 3.3 Review never alters a verdict; failing check with accepted exception still
      renders failing
- [x] 3.4 Prohibited-language check over all review-status renderings

## 4. Docs & examples

- [x] 4.1 Example: dossier for a part with one thin margin and one unevaluated check
- [x] 4.2 Explanation page: responsible charge, what Anvilate provides, and what it
      cannot certify

## Scope as shipped

- **The priority order is "most likely to change the decision", not "worst first"**, and
  the consequence is that NOT_EVALUATED sorts ahead of FAIL. A failure is already visible
  and already blocking; an unevaluated check is the one a reviewer can miss entirely.
- **A check absent from the origin map is UNATTRIBUTED, not routine.** Defaulting an
  unrecorded origin to something reassuring would make the attribution feature worse than
  useless by making its absence invisible.
- **The digest covers the toolchain as well as the scorecard** (2.2). The same inputs
  through a different library version are a different piece of work, and a review that
  silently survived an upgrade would be assurance nobody gave. A stale record is flagged,
  never dropped: "reviewed, and it no longer applies" is different information from
  "never reviewed", and the two look identical from outside.
- **3.4's language gate landed twice**: once over every rendering the review module
  produces, and once in tests/test_contract.py over every scorecard detail and reference
  string the packs emit — because the risk is not confined to this module.
