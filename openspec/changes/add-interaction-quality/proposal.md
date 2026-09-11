# Change: Interaction quality — the part the engineer actually feels

## Why

`onboarding` budgets the first ten minutes carefully and then stops. Nothing in the
corpus governs minute eleven onward: whether a four-minute mesh shows progress or a dead
terminal, whether Ctrl-C leaves a half-written STEP file behind, whether a refusal tells
you what to do or only what is wrong, whether the output is readable when piped, whether
any of it works for someone who cannot distinguish red from green.

This matters more here than in most tools, because of what the last nine change sets did.
Anvilate now refuses a great deal — by design — and a tool that refuses often is judged
almost entirely on the quality of its refusals. "Not evaluated: damping" is correct and
useless. "Not evaluated: the shock screen needs a quality factor (dimensionless, typically
10–30); supply it on the environment, or bind the handheld-instrument profile which
declares 12" is the same refusal doing its job.

The same asymmetry applies to waiting. An engineer who watches a silent terminal for four
minutes does not conclude the mesh is hard; they conclude the tool is broken, and the next
time they reach for the spreadsheet. Progress is not decoration — it is the difference
between a tool that is trusted while it works and one that is only trusted when it is
finished.

None of this is expensive, and all of it is much cheaper to specify now than to retrofit
across a CLI, an MCP server, a Python API, and a UI that have each grown their own habits.

## What Changes

- New capability spec `interaction-quality`, binding on every surface: no silent wait,
  cancellation that leaves no half-state, refusals that carry an actionable remedy naming
  a concrete subject, output that adapts to where it is going, and accessibility rules
  that make none of the information color-dependent.
- **Progress is honest**: determinate work reports completed and total units; indeterminate
  work says it is indeterminate rather than animating a fake percentage; an estimate
  appears only when derived from completed work of the same kind, and is labeled an
  estimate.
- **Responsiveness is budgeted and measured** per release the way time-to-first-part
  already is, and any operation that can exceed the budget must have a progress surface.
- `headless-automation` gains the CLI conventions — TTY and `NO_COLOR` detection, width
  awareness, machine-readable output on every command, distinct exit codes for refusal
  versus failure versus crash, shell completion, examples in help, and near-miss
  suggestions.
- `workbench-ui` gains parity: the same progress, cancellation, remedy, and accessibility
  guarantees, so neither surface is the good one.

## Impact

- Affected specs: new `interaction-quality`; `headless-automation` (ADDED);
  `workbench-ui` (ADDED). Interacts with `onboarding` (which owns the first run),
  `declaration-completeness` (the needs report is where most remedies land),
  `sandbox-security` (cancellation must not leave a sandbox running), and `benchmarking`
  (the responsiveness budget is a measured release gate).
- Affected code (when implemented): a progress channel threaded through long operations,
  cancellation and cleanup, a remedy field on refusals, output adapters, and the CI gates
  over message quality.
- Explicitly out: telemetry of any kind; animation or styling beyond what carries
  information; and progress estimates for work whose size is not known in advance.
