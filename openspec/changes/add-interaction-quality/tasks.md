# Tasks: Interaction quality

## 1. Progress and cancellation

- [ ] 1.1 Progress channel: current activity, completed and total units, indeterminate flag
- [ ] 1.2 Threshold rule — any operation that can exceed it reports progress
- [ ] 1.3 Estimates derived from completed same-kind work only, and labeled estimates
- [ ] 1.4 Cancellation at any point; partial artifacts removed or marked partial
- [ ] 1.5 Cancellation terminates subprocess solvers and sandboxes, verified

## 2. Message quality

- [ ] 2.1 Remedy field on every refusal: the action, its concrete subject, and where a
      value may come from
- [ ] 2.2 CI gate: every refusal message's remedy names a resolvable subject — an
      imperative with no noun fails
- [ ] 2.3 CI gate carries a population floor and enumerated exclusions with causes
- [ ] 2.4 Near-miss suggestions for unknown names, keyed on the real registry

## 3. Output adaptation

- [ ] 3.1 TTY detection, `NO_COLOR`, dumb terminals, width awareness, ASCII fallback
- [ ] 3.2 Machine-readable output on every command with a stable, versioned schema
- [ ] 3.3 Exit codes: success, refusal, failed verdict, internal error — distinct and
      documented
- [ ] 3.4 Progress to stderr so stdout stays pipeable

## 4. Accessibility

- [ ] 4.1 No information conveyed by color alone anywhere — status carries a word or mark
- [ ] 4.2 Palette safe for common color-vision deficiency, checked in CI
- [ ] 4.3 Report structure readable in document order by a screen reader; tables carry
      headers; figures carry text alternatives

## 5. Discoverability

- [ ] 5.1 "What applies to this spec" listing of available screens with what each needs
- [ ] 5.2 Runnable examples in every command's help
- [ ] 5.3 Shell completion for the supported shells

## 6. Budgets

- [ ] 6.1 Interactive responsiveness budget, measured per release on the reference profile
- [ ] 6.2 Cache repeated loads of bundled data; assert the cache is hit, not just present

## 7. Tests

- [ ] 7.1 A long operation piped to a file writes clean stdout and progress to stderr
- [ ] 7.2 Ctrl-C during export leaves no partial artifact presented as complete
- [ ] 7.3 Every refusal in the suite carries a remedy with a resolvable subject
- [ ] 7.4 Rendering with color disabled loses no information
