# Tasks: The design journey

Depends on `add-product-structure` for the worked product. The `simulated` and
`optimized` stages are reported as not applicable until `add-local-fea` and
`add-design-optimization` ship; everything else can land first.

## 1. Next step and journey state

- [ ] 1.1 `next` on every workflow result, derived from the card by the precedence rule;
      a test walks every rule against the live tool catalog
      (`anvilate.journey`, next-steps 1.0.0, on `run_validation`, `build_combination` and
      a **product** result, whose card is every item's checks and the
      whole product's as one. build_part, FEA and export results, and refusals over the
      wire, not yet)
- [x] 1.2 Journey stage and per-stage gaps on part, combination and product results
      (`journey_state`, journey-state 1.0.0, on `run_validation`, `build_combination` and
      a product result. The reducer reads `described` and not `screened`, because seven of
      its items are placeholders — which a journey over the whole-product checks alone
      would have called screened, since those all pass)
- [x] 1.3 Stage invalidated by content digest; a changed design falls back and says why

## 2. Finish line

- [ ] 2.1 `review_package` export format: bundle, dossier, release files, study record
      (bundle, dossier and manifest, over MCP and at the shell; release files and a study
      record are not in it yet)
- [x] 2.2 Draft marking in every file; refusal short of `review_ready` without `draft`
- [x] 2.3 The package records no review (held by a test against `responsible-charge-review`)

## 3. First product and optional pieces

- [x] 3.1 The gear reducer added to the gallery with a one-request journey, offline
      (`examples/gear_reducer_journey.py`: ONE `build_combination` request, handled in the
      same process, and everything else read out of the single reply — the item tree, the
      whole-product checks, the journey stage and the next step. What it teaches is the
      thing a reader would otherwise get wrong: every whole-product check passes and the
      design is still not screened, because seven items are placeholders. FEA is not
      applicable because the document demands none, and optimisation because no study is
      declared, so neither reads as a failure)
- [x] 3.2 `doctor` reports optional capabilities as not installed with a per-platform
      command, and exits 0 for them
- [x] 3.3 One remedy text shared by `doctor` and every tool that needs the capability

## 4. Measurement

- [x] 4.1 The *design a product* journey walked call by call in an offline test
      (`tests/test_mcp_product.py`: two `build_combination` calls through the server's own
      request handler in-process, where the second is the step the FIRST one named. A rig
      with one placeholder reads `described`, its `screened` gap names that placeholder and
      its first step says to declare `definitions[].spec`; doing exactly that and nothing
      else closes the gap, the stage reads `screened`, and the step moves on to writing the
      review package. The point is not that the stage advances but that an agent with only
      the result can tell what to do, do it, and see what it was told about close)
- [ ] 4.2 The journey added to the agent-driving corpus; measured on both target clients
- [ ] 4.3 The release gate holds the journey to the previous release's measurement
- [ ] 4.4 README: the reducer request as a fourth "ask in plain English" example, once it
      runs end to end
