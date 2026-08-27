# Change: Responsible-charge review — the dossier an engineer needs before sealing

## Why

Anvilate's output eventually reaches a licensed engineer who must decide whether to put
their seal on it. The NSPE Board of Ethical Review has now addressed this directly:
failing to maintain responsible charge over an AI tool's output before sealing was found
unethical, with the governing framing that an AI tool is like an engineering intern —
the engineer must set the constraints, must not blindly accept the output, and must
satisfy themselves before sealing (NSPE BER, "Use of Artificial Intelligence in
Engineering Practice"; NSPE Position Statement 03-1774 requires AI-generated technical
work receive at least the same scrutiny as human work).

Anvilate produces the raw material for that scrutiny — scorecard, assumptions, citations,
iteration history — but has no requirement that it be *assembled for a reviewer* or that
review be recorded. Meanwhile the emerging approval-UX conventions for AI-generated work
converge on a consistent list of what a reviewer must see before approving: the exact
action, what state changed, the evidence, the uncertainty, the alternatives, and the
limits of reversal. And the practical problem is measurable — AI-generated pull requests
wait 4.6× longer for review pickup, because reviewers cannot tell cheaply what deserves
attention.

The EU AI Act's Article 50 transparency obligations apply from August 2026 (high-risk
Annex III duties slipped to December 2027 under the June 2026 Digital Omnibus), so
machine-readable AI-involvement disclosure — already spec'd in `add-evidence-attestation`
— gets a human-facing counterpart here.

## What Changes

- New capability spec `responsible-charge-review`: a reviewer dossier assembling what
  must be examined before sign-off, ordered by what most deserves scrutiny; per-decision
  AI attribution distinguishing what a model chose from what the deterministic pipeline
  computed; a recorded review action naming the reviewer, scope, and outcome; and a hard
  rule that Anvilate never represents review status as professional certification.

## Impact

- Affected specs: new `responsible-charge-review`. Interacts with `workbench-ui`
  (report pane), `agent-repair-loop` (iteration provenance), `artifact-export` (bundle),
  and `add-evidence-attestation` (machine-readable disclosure); none change.
- Affected code (when implemented): a dossier assembler over existing provenance, a
  review-record type, and rendering in the report pane and evidence bundle.
- Out of scope: digital signatures on sealed documents, PE-stamp workflows, jurisdictional
  licensure logic, and any assertion that Anvilate's review satisfies a legal obligation.
