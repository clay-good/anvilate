# Change: Model credibility — the prediction compared with the test, and the credibility of a result stated on a public scale

## Why

Anvilate says what it predicted and, through `verification-planning`, what test would
confirm it, and lets a person record the test's result. It then does nothing with the
result. A proof test that held 8% less than the lug check predicted is recorded beside a
check that still reads pass, and no card, dossier or benchmark learns that the prediction
was unconservative.

That is the one loop the project's own doctrine demands and does not close. `benchmarking`
defines an escaped defect as a green-checked part that failed physically for a reason the
validation claims to model, and requires a post-mortem and a permanent regression. The
record that would detect one already exists; it is not read.

Two public documents give the shape:

- **NASA-STD-7009A** (Standard for Models and Simulations, Revision A, 2016; approved
  for public release, distribution unlimited) defines eight credibility factors, each
  scored 0 to 4, with 0 meaning insufficient evidence: data pedigree, input pedigree,
  code verification, solution verification, conceptual validation, referent validation,
  results uncertainty, results robustness. It was written after the Columbia accident so
  that a decision-maker could see how much a simulation result deserved to be trusted.
  Anvilate already holds evidence for most of these factors (database provenance, value
  origins, worked-example anchoring, mesh convergence, uncertainty bands) and states none
  of it on the 7009 scale that aerospace reviewers use. `add-industry-profiles`'
  spaceflight profile needs exactly this.
- **ASME V&V 10** (verification and validation in computational solid mechanics) supplies
  the vocabulary: a validation metric is a mathematical measure of agreement between a
  simulation outcome and an experimental outcome; a prediction is interpolative or
  extrapolative with respect to the validation domain the model was compared in; and a
  2016 FAA workshop presentation warns that "within the test corridor" is a weak metric
  because the corridor is arbitrary and the mismatch is not quantified. The document is
  copyrighted and nothing of it is reproduced; the terms are cited.

## What Changes

| Area | Change |
| --- | --- |
| Correlation | A recorded test outcome with a measured value is compared with the check that planned it: the ratio and difference, in the quantity's units, against an acceptance band the document declares with its source. Unconservative beyond the band is a finding on the card. The verdict is unchanged; the finding sits beside it. |
| Escaped-defect candidate | An unconservative correlation on a check that passed is filed as an escaped-defect candidate carrying the bundle digest, the check, the predicted and measured values and the test record, for the post-mortem process `benchmarking` already requires. |
| Credibility factors | Each result, and the bundle as a whole, can carry the eight NASA-STD-7009A factors, each a score with the evidence it rests on. Anvilate proposes a score only where it holds the evidence (a worked-example anchor, a convergence study, a correlation, an uncertainty band, a provenance origin) and names it; a factor with no evidence is 0, and a person may override any score with a reason. The dossier renders the set. |
| Validation domain | A check records the parameter ranges over which it has been anchored and correlated. A use outside them is labeled extrapolative on the entry. No verdict changes; the label is the information. |
| Vocabulary | Verification, validation, validation metric and validation domain are used in the ASME V&V 10 sense and cited as such. |

## Impact

- New capability: `model-credibility`. Deltas: `verification-planning` (ADDED),
  `benchmarking` (ADDED).
- Builds on `verification-planning` (recorded outcomes with value, date, performer,
  instrument), `uncertainty-quantification` (results uncertainty), `validation-gauntlet`
  (mesh convergence as solution verification), `analysis-library` (worked-example
  anchors as code verification), `evidence-attestation` and `responsible-charge-review`
  (the dossier renders credibility). Feeds `add-industry-profiles` (a profile may require
  a minimum factor set) and `add-service-life-planning` (a measured condition is a
  correlation point).
- Licensing: NASA-STD-7009A is a work of the US government approved for public release;
  its factor names and scale are cited. ASME V&V 10 is copyrighted and only its terms are
  used.
- Explicitly out:
  - Statistical validation metrics beyond ratio and difference in the first phase
    (area metric, probabilistic comparisons) — they plug into the same record later.
  - Any automatic re-tuning of a check from test data. A correlation is information for a
    person and a regression for CI, never a calibration.
  - Any statement that a result is "validated" in a regulatory sense.
