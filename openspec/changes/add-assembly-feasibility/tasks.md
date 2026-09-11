# Tasks: Assembly feasibility

## 1. Declarations

- [ ] 1.1 Tool envelope records for the common drivers and wrenches, with provenance
- [ ] 1.2 Per-feature access requirement: tool, approach direction, swing arc needed
- [ ] 1.3 Assembly-state declaration: the ordered states a build passes through
- [ ] 1.4 Part insertion direction and the features a part occupies

## 2. Screens

- [ ] 2.1 Tool-access sweep generated as a keepout and checked by the existing intrusion
      mechanism — not a second collision implementation
- [ ] 2.2 Swing-arc screen against available clearance, reporting the arc achieved
- [ ] 2.3 Access evaluated per declared assembly state, not on the bare part
- [ ] 2.4 Order feasibility: report a valid order or the blocking parts
- [ ] 2.5 Serviceability and post-closure adjustment reachability
- [ ] 2.6 Inspectability of toleranced dimensions across achievable states

## 3. Reporting

- [ ] 3.1 Findings name the feature, the tool, the state, and the blocking geometry
- [ ] 3.2 Repair hints in the form the repair loop consumes
- [ ] 3.3 Contribute assembly-stage entries to the failure-mode catalog

## 4. Tests

- [ ] 4.1 A cap screw whose head clears and whose driver does not is caught
- [ ] 4.2 An adjustment reachable open and unreachable closed is caught, with the state
      named — the opto-mechanical case this exists for
- [ ] 4.3 A three-part assembly with no valid order reports the cycle, not a pass
- [ ] 4.4 Widening a clearance changes the verdict, proving the screen reads geometry
- [ ] 4.5 A part with no declared insertion direction reports not-evaluated, never a pass

## 5. Docs & examples

- [ ] 5.1 Example: a sealed housing whose internal adjustment fails post-closure access,
      and the revision that fixes it
