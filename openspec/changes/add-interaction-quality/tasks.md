# Tasks: Interaction quality

## 1. Progress and cancellation

- [x] 1.1 Progress channel: current activity, completed and total units, indeterminate flag
      — MCP task responses carry all four under `_meta["dev.anvilate/progress"]`; queued
      and running work is explicitly indeterminate with no invented total, terminal success
      is 1/1, and cancellation or failure ends at 0/1 without claiming completion
- [x] 1.2 Threshold rule — any operation that can exceed it reports progress — a declared
      two-second threshold; check, export and build report through one helper, and a test
      fails any sweep over specs that does not
- [x] 1.3 Estimates derived from completed same-kind work only, and labeled estimates —
      the check sweep's time left, from specs already screened, none before the first
- [x] 1.4 Cancellation at any point; partial artifacts removed or marked partial — the CLI
      reports a cancelled run as its own outcome (exit 130) with what it completed, and
      exports write atomically, so an interrupt leaves no partial artifact
- [x] 1.5 Cancellation terminates subprocess solvers and sandboxes, verified — the MCP task
      worker's whole process group gets SIGTERM, then SIGKILL after a 2 s grace; verified
      with a stand-in worker whose solver child exits politely and one that ignores SIGTERM
      (tests/test_mcp_tasks.py). No sandbox exists yet to terminate

## 2. Message quality

- [ ] 2.1 Remedy field on every refusal: the action, its concrete subject, and where a
      value may come from — progress: every gap the library builds through
      `ScorecardEntry.from_safety_factor` states its reason and the field to declare
      (`unavailable=`, 34 call sites, held by a gate in tests/conftest.py). Raised
      refusals carry their remedy in the message text (2.2), with no structured field yet. The
      structured field is `ScorecardEntry.needs` (add-declaration-completeness): 61 of the
      library's 111 not-evaluated sites carry it (nine in screening, and every screen
      elsewhere that stops for a value), and so do all 34 `from_safety_factor` calls that
      state an `unavailable=` reason. tests/test_needs.py sweeps every module; the other 50
      are excused by cause in docs/api/refusals-without-needs.txt, and the backlog is empty.
      Left open because the task says "every refusal": a *raised* refusal (a ValueError)
      still carries its remedy in its message only
- [x] 2.2 CI gate: every refusal message's remedy names a resolvable subject — an
      imperative with no noun fails — tests/test_remedies.py over every one of the library's 5,000+ refusal messages; the six "delete it" and three "name it"/"state it" remedies now name their file or field
- [x] 2.3 CI gate carries a population floor and enumerated exclusions with causes — floors on the messages read and the remedies recognised, and no exclusions needed
- [x] 2.4 Near-miss suggestions for unknown names, keyed on the real registry — every bundled
      table answers a one-character typo with the entry it nearly named, held by a sweep over
      the discovered tables rather than a list of them

## 3. Output adaptation

- [x] 3.1 TTY detection, `NO_COLOR`, dumb terminals, width awareness, ASCII fallback
      — the ASCII fallback and dumb terminals are done: a stream that cannot encode the
      output gets ASCII spellings (text) or `\u` escapes (JSON) instead of exit 5, and the
      CLI emits no colour, so `NO_COLOR` has nothing to turn off; and on a terminal each text
      line is wrapped to its width, continuation indented, words never broken, while a pipe,
      a file and JSON get exactly the lines written
- [x] 3.2 Machine-readable output on every command with a stable, versioned schema
      — `cli-output` 1.3.0 covers every completed-result path plus parser, bad-input,
      and unbuilt refusals while preserving their exit codes and stderr diagnostics
- [x] 3.3 Exit codes: success, refusal, failed verdict, internal error — distinct and
      documented; unexpected command defects exit 5 and JSON schema 1.2.0 identifies them
- [x] 3.4 Progress to stderr so stdout stays pipeable — `check` over several specs prints
      `[i/n] screening <path>` to stderr when stderr is a terminal, and nothing into a pipe

## 4. Accessibility

- [x] 4.1 No information conveyed by color alone anywhere — status carries a word or mark
      — the terminal emits no colour at all, and every coloured status in the HTML report is
      a status word, held by a test over the rendered spans
- [x] 4.2 Palette safe for common color-vision deficiency, checked in CI — the report's
      status colours clear WCAG AA on the page and stay ΔE ≥ 20 apart, body text included,
      under the Machado 2009 protan, deutan and tritan simulations; the old red and green
      failed it, and the old amber failed contrast
- [x] 4.3 Report structure readable in document order by a screen reader; tables carry
      headers; figures carry text alternatives — the report's headings run in order from one h1, every table is headed,
      and every typeset formula carries a spoken MathML `alttext` ("σ sub b = M · c / I")

## 5. Discoverability

- [x] 5.1 "What applies to this spec" listing of available screens with what each needs —
      `anvilate.needs.what_applies`, in docs/declaration-needs.md
- [x] 5.2 Runnable examples in every command's help, held against the parser's command set
- [x] 5.3 Shell completion for the supported shells — `anvilate --completion bash|zsh`,
      built from the live parser and exercised in bash by a test

## 6. Budgets

- [ ] 6.1 Interactive responsiveness budget, measured per release on the reference profile — BLOCKED:
      the reference hardware profile and the release process the onboarding and benchmarking
      specs name are both unbuilt, and a timing gate on shared CI runners measures the machine
- [x] 6.2 Cache repeated loads of bundled data; assert the cache is hit, not just present —
      every discovered loader is cached, and a repeat screen is served with hits up and misses
      flat

## 7. Tests

- [x] 7.1 A long operation piped to a file writes clean stdout and progress to stderr —
      stdout is byte-identical watched or piped (tests/test_cli.py)
- [x] 7.2 Ctrl-C during export leaves no partial artifact presented as complete — DXF writes
      go to a hidden sibling renamed on completion, and the STEP writer removes its file on
      a KeyboardInterrupt as well as on an error
- [ ] 7.3 Every refusal in the suite carries a remedy with a resolvable subject
- [x] 7.4 Rendering with color disabled loses no information — the terminal carries no
      ANSI escape (tests/test_cli.py), and every coloured status in the HTML report is a word
      (tests/test_report.py)
