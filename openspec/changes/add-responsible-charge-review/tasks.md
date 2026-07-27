# Tasks: Responsible-charge review

## 1. Contracts

- [ ] 1.1 Dossier assembly type over existing provenance, scorecard, and iteration history
- [ ] 1.2 Decision-origin attribution (user / deterministic / model + version /
      unattributed)
- [ ] 1.3 Review record type (reviewer, date, artifact digest, scope, outcome,
      exceptions)

## 2. Implementation

- [ ] 2.1 Deterministic, documented review-priority ordering
- [ ] 2.2 Review record binding to content digest; invalidation on any change
- [ ] 2.3 Report-pane and evidence-bundle rendering with disclaimer retention
- [ ] 2.4 AI-involvement summary suitable for disclosure

## 3. Tests

- [ ] 3.1 Any spec or toolchain change invalidates a prior review record
- [ ] 3.2 Thin-margin, unevaluated, and model-assumption items surface in priority order
- [ ] 3.3 Review never alters a verdict; failing check with accepted exception still
      renders failing
- [ ] 3.4 Prohibited-language check over all review-status renderings

## 4. Docs & examples

- [ ] 4.1 Example: dossier for a part with one thin margin and one unevaluated check
- [ ] 4.2 Explanation page: responsible charge, what Anvilate provides, and what it
      cannot certify
