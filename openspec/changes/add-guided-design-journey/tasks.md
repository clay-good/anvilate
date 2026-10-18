# Tasks: The design journey

Depends on `add-product-structure` for the worked product. The `simulated` and
`optimized` stages are reported as not applicable until `add-local-fea` and
`add-design-optimization` ship; everything else can land first.

## 1. Next step and journey state

- [ ] 1.1 `next` on every workflow result, derived from the card by the precedence rule;
      a test walks every rule against the live tool catalog
- [ ] 1.2 Journey stage and per-stage gaps on part, combination and product results
- [ ] 1.3 Stage invalidated by content digest; a changed design falls back and says why

## 2. Finish line

- [ ] 2.1 `review_package` export format: bundle, dossier, release files, study record
- [ ] 2.2 Draft marking in every file; refusal short of `review_ready` without `draft`
- [ ] 2.3 The package records no review (held by a test against `responsible-charge-review`)

## 3. First product and optional pieces

- [ ] 3.1 The gear reducer added to the gallery with a one-request journey, offline
- [ ] 3.2 `doctor` reports optional capabilities as not installed with a per-platform
      command, and exits 0 for them
- [ ] 3.3 One remedy text shared by `doctor` and every tool that needs the capability

## 4. Measurement

- [ ] 4.1 The *design a product* journey walked call by call in an offline test
- [ ] 4.2 The journey added to the agent-driving corpus; measured on both target clients
- [ ] 4.3 The release gate holds the journey to the previous release's measurement
- [ ] 4.4 README: the reducer request as a fourth "ask in plain English" example, once it
      runs end to end
