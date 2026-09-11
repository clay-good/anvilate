# Tasks: Check dependency graph

## 1. Contract

- [ ] 1.1 Declared-consumption annotation: which upstream check id and which output
- [ ] 1.2 Dimension agreement between the declared output and the consuming parameter
- [ ] 1.3 CI gate: a check that reads another check's result without declaring it fails —
      detected structurally, with a population floor and enumerated exclusions

## 2. Evaluation

- [ ] 2.1 Topological ordering within a tier; stable order for equal-depth checks
- [ ] 2.2 Cycle detection refusing with every member of the cycle named
- [ ] 2.3 Realized evaluation order recorded in the evidence bundle

## 3. Propagation

- [ ] 3.1 Not-evaluated propagates downstream naming the upstream check
- [ ] 3.2 Staleness invalidates the transitive closure, never a partial one
- [ ] 3.3 Margin-ledger entries inherit down the chain into the cumulative factor
- [ ] 3.4 Derivation rendering shows the chain, not only the final substitution

## 4. Tests

- [ ] 4.1 A six-link chain evaluates in dependency order regardless of declaration order
- [ ] 4.2 An upstream not-evaluated makes every downstream check not-evaluated — the
      defect class this capability exists to catch
- [ ] 4.3 Changing an upstream input changes every downstream value in one evaluation; no
      scorecard mixes two evaluations of one chain
- [ ] 4.4 A cycle is refused naming all its members, not just the edge that closed it
- [ ] 4.5 Mutating a link's return value fails a downstream assertion, proving the chain
      is wired rather than merely declared

## 5. Docs & examples

- [ ] 5.1 Worked example: an internal heat source through temperature, modulus, frequency,
      and shock response to a displacement verdict
