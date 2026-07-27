# Change: Reason free, constrain late — protect local-model accuracy under schema constraints

## Why

Anvilate's intent compiler forces schema-valid Spec IR out of a small local model. New
evidence says the obvious implementation of that — constrain every token from the start —
buys validity at a real accuracy cost. "The Constraint Tax" (May 2026,
https://arxiv.org/abs/2605.26128) measured on 0.5B–1.7B models: hard schema-constrained
decoding lifts schema validity from 61.5% to 100% while *dropping* answer accuracy from
19.7% to 11.0%, and wrong-but-schema-valid outputs rise from 49.5% to 88.9%. On tool
calls, executable accuracy fell from 91.5% prompt-only to 48.0% under hard constraint. A
companion result finds much of the damage enters through the prompt and the schema's own
key names acting as instructions (https://arxiv.org/pdf/2604.14862).

For Anvilate this is a direct threat to the local-first promise: a confidently
well-formed Spec IR with the wrong load in it is worse than a malformed one, because
schema validation cannot catch it. The mitigation the literature recommends is a two-pass
"reason free, constrain late" shape — reason unconstrained, then package into the schema
— plus measuring validity and correctness as separate numbers rather than one.

The existing `intent-compilation` requirement already mandates schema-constrained output
and backend independence; this change specifies *how* that constraint is applied so it
does not silently degrade the small models the project recommends.

## What Changes

- `intent-compilation` (ADDED): compilation runs as an unconstrained reasoning pass
  followed by a constrained packaging pass; schema field naming is treated as part of the
  prompt surface and version-controlled; and validity and correctness are reported as
  separate metrics, never collapsed into one "success" number.
- `benchmarking` (ADDED): the local-model recommendation is gated on separately measured
  schema validity, field-level correctness, and wrong-but-valid rate.

## Impact

- Affected specs: `intent-compilation` and `benchmarking` (one ADDED requirement each;
  existing requirements unchanged — output is still always schema-validated before use).
  Complements `extend-benchmarking-agent-evals` without overlapping it: that change
  measures agents driving the tool surface, this one measures the compiler's own
  correctness under constraint.
- Affected code (when implemented): the compilation pipeline's two-pass structure and the
  eval harness metrics.
- Out of scope: choosing a constrained-decoding backend, and any relaxation of the rule
  that free text never crosses a subsystem boundary.
