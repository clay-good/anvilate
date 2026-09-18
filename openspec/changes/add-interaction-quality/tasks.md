# Tasks: Interaction quality

## 1. Progress and cancellation

- [x] 1.1 Progress channel: current activity, completed and total units, indeterminate flag
      — MCP task responses carry all four under `_meta["dev.anvilate/progress"]`; queued
      and running work is explicitly indeterminate with no invented total, terminal success
      is 1/1, and cancellation or failure ends at 0/1 without claiming completion
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
- [x] 2.4 Near-miss suggestions for unknown names, keyed on the real registry — every bundled
      table answers a one-character typo with the entry it nearly named, held by a sweep over
      the discovered tables rather than a list of them

## 3. Output adaptation

- [ ] 3.1 TTY detection, `NO_COLOR`, dumb terminals, width awareness, ASCII fallback
- [x] 3.2 Machine-readable output on every command with a stable, versioned schema
      — `cli-output` 1.3.0 covers every completed-result path plus parser, bad-input,
      and unbuilt refusals while preserving their exit codes and stderr diagnostics
- [x] 3.3 Exit codes: success, refusal, failed verdict, internal error — distinct and
      documented; unexpected command defects exit 5 and JSON schema 1.2.0 identifies them
- [ ] 3.4 Progress to stderr so stdout stays pipeable

## 4. Accessibility

- [ ] 4.1 No information conveyed by color alone anywhere — status carries a word or mark
- [ ] 4.2 Palette safe for common color-vision deficiency, checked in CI
- [ ] 4.3 Report structure readable in document order by a screen reader; tables carry
      headers; figures carry text alternatives

## 5. Discoverability

- [ ] 5.1 "What applies to this spec" listing of available screens with what each needs
- [x] 5.2 Runnable examples in every command's help, held against the parser's command set
- [ ] 5.3 Shell completion for the supported shells

## 6. Budgets

- [ ] 6.1 Interactive responsiveness budget, measured per release on the reference profile
- [x] 6.2 Cache repeated loads of bundled data; assert the cache is hit, not just present —
      every discovered loader is cached, and a repeat screen is served with hits up and misses
      flat

## 7. Tests

- [ ] 7.1 A long operation piped to a file writes clean stdout and progress to stderr
- [ ] 7.2 Ctrl-C during export leaves no partial artifact presented as complete
- [ ] 7.3 Every refusal in the suite carries a remedy with a resolvable subject
- [ ] 7.4 Rendering with color disabled loses no information
