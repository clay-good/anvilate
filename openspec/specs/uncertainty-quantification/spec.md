# uncertainty-quantification Specification

## Purpose
Declared input scatter propagated to a margin, without ever weakening the deterministic verdict. Distributions are typed and unit-checked, sampling is seeded and reproducible, and the result adds a percentile band, a shortfall probability and a sensitivity ranking beside the nominal answer — never in place of it. A probabilistic result is labelled as screening and gated to the methods that support it.

## Requirements
### Requirement: Typed input distributions

Any physical-quantity input to an analysis check SHALL be declarable with a typed uncertainty — at minimum symmetric bounds (±), uniform, and normal (mean, standard deviation) — sharing vocabulary with the tolerance capability; a distribution declaration MUST NOT change the deterministic nominal evaluation of the check.

#### Scenario: Load with scatter

- **WHEN** a user declares a lifting load as 5 t nominal with ±15% uniform uncertainty
- **THEN** the check still evaluates and reports its nominal verdict from 5 t, and the distribution is available to the uncertainty analysis

#### Scenario: Dimensional consistency enforced

- **WHEN** a distribution's bounds carry units inconsistent with the nominal value
- **THEN** the declaration is rejected naming the field and dimensions, per the units capability

### Requirement: Margin distribution by seeded Monte Carlo

The system SHALL propagate declared input distributions through any analysis check by seeded Monte Carlo sampling, reporting the margin distribution (percentile band), the probability that the margin falls below the required minimum, and the sample count and seed; identical spec, seed, and toolchain versions SHALL reproduce identical results.

#### Scenario: Probability of shortfall reported

- **WHEN** the uncertainty analysis runs on a bending check with a load distribution declared
- **THEN** the result reports the nominal margin, a percentile band, and the estimated probability the safety factor falls below the required minimum, with seed and sample count recorded

#### Scenario: Reproducible run

- **WHEN** the same analysis reruns with the same seed and versions
- **THEN** every reported statistic is identical

### Requirement: Sensitivity ranking

Uncertainty results SHALL rank the declared uncertain inputs by their contribution to margin variance, so the user knows which input most rewards better information; the ranking method SHALL be named and cited in the result.

#### Scenario: Governing uncertainty named

- **WHEN** load, yield strength, and a dimension all carry distributions
- **THEN** the result ranks their contributions and identifies the one that governs the margin spread

### Requirement: Probabilistic results never weaken deterministic verdicts

A probabilistic result SHALL annotate, never replace, the deterministic nominal verdict; when a nominally passing check carries an estimated shortfall probability above a declared reporting threshold (default 5%), the scorecard SHALL show a distinct uncertainty warning with the probability stated — a nominal PASS with material failure probability MUST NOT render as an unqualified green.

#### Scenario: Fragile pass flagged

- **WHEN** a check passes nominally at SF 1.55 against a 1.5 minimum but 18% of samples fall below the minimum
- **THEN** the check renders as a pass with an uncertainty warning stating the 18% shortfall probability

#### Scenario: No distributions, no annotation

- **WHEN** no input carries a declared distribution
- **THEN** checks render exactly as today with no probabilistic annotation

### Requirement: Screening label and method gating

Every probabilistic result SHALL carry the screening label, the method name, and its citation; reliability methods beyond Monte Carlo (FORM/SORM-class) SHALL, when introduced, plug into this same contract — typed inputs, seeded determinism, annotation-not-replacement, screening label.

#### Scenario: Method visible

- **WHEN** an uncertainty annotation is rendered in a report
- **THEN** it names the sampling method, sample count, and the screening label — never a bare probability presented as a certified reliability figure

