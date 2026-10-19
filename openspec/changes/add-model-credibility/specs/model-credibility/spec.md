# Model Credibility Specification

## Purpose

What a measured result says about the prediction that planned it, and how much a result
deserves to be trusted, stated on a public scale with the evidence beside each score. A
correlation never changes a verdict; it annotates it, feeds the escaped-defect process,
and tells the next reader whether the check has ever been compared with a test in the
range it is being used.

## ADDED Requirements

### Requirement: A recorded outcome is correlated with the prediction that planned it

The system SHALL compute a correlation whenever a verification outcome recorded against a
planned item carries a measured value: the predicted value from the driving check, the
measured value, their ratio and difference in the quantity's units, and the comparison
against an acceptance band the document declares with its source. A correlation whose
measured value is unconservative beyond the band SHALL be a finding on the driving check's
card entry naming both values; one conservative beyond the band SHALL be noted to the
margin ledger as a possible unattributed conservatism. The check's verdict SHALL NOT
change. Without a declared band, the correlation SHALL be reported with no finding and a
not-evaluated comparison naming the band it needs.

#### Scenario: The proof test held less than predicted

- **WHEN** a lug's proof-load item records a measured capacity 8% below the predicted one
  and the declared band is ±5%
- **THEN** the lug check keeps its verdict and carries a finding naming the predicted and
  measured values, the ratio and the band

#### Scenario: No band, no verdict on the comparison

- **WHEN** a measured deflection is recorded and no acceptance band is declared
- **THEN** the correlation reports both values and the ratio, and the comparison is not
  evaluated naming the band

### Requirement: An unconservative correlation is an escaped-defect candidate

An unconservative correlation on a check that passed SHALL be filed as an escaped-defect
candidate carrying the evidence bundle digest, the check identifier, the predicted and
measured values, the acceptance band and the test record, in the form the benchmarking
escaped-defect process consumes. The candidate SHALL be visible in the dossier until it is
dispositioned by a person, and dispositioning it SHALL NOT remove the finding from the
card.

#### Scenario: The candidate reaches the process

- **WHEN** a passing bolt-preload check records a measured preload below the predicted
  minimum beyond the band
- **THEN** an escaped-defect candidate is written with the bundle digest and the test
  record, and the dossier lists it as undispositioned

### Requirement: Credibility factors are stated with their evidence

A result and an evidence bundle SHALL be able to carry a credibility factor set on the
NASA-STD-7009A scale — data pedigree, input pedigree, code verification, solution
verification, conceptual validation, referent validation, results uncertainty and
results robustness, each scored 0 to 4 — where every score names the evidence it rests on.
The system MAY propose a score only from evidence it holds (a worked-example anchor, a
convergence study, a correlation, an uncertainty band, a provenance origin) by a
published mapping, SHALL score a factor 0 when it holds no evidence, and SHALL accept a
person's override of any score with a stated reason, attributed. A factor set SHALL be
rendered in the dossier with the standard cited, and MUST NOT be rendered as a
certification or as "validated".

#### Scenario: A closed-form check with a correlation

- **WHEN** a bending check anchored to a worked example and correlated with one recorded
  test is scored
- **THEN** code verification and referent validation carry proposed scores naming the
  anchor and the correlation, solution verification is stated not applicable with the
  reason, and results uncertainty is 0 with "no distribution declared" as its evidence

#### Scenario: An override is attributed

- **WHEN** a reviewer lowers a proposed referent-validation score with a reason
- **THEN** the dossier shows the proposed score, the override, the reason and the person

### Requirement: Use outside the validation domain is labeled

Each check SHALL record the parameter ranges over which it has been anchored to worked
examples and correlated with recorded tests. A card entry whose inputs fall outside every
recorded range SHALL be labeled extrapolative naming the parameter and the nearest
recorded range; one inside a range SHALL be labeled interpolative with the range named.
The label SHALL NOT change the verdict.

#### Scenario: A lug twice the size of any test

- **WHEN** a lug check runs at a pin diameter outside every anchored or correlated range
- **THEN** the entry is labeled extrapolative naming the pin diameter and the nearest range,
  and the verdict is unchanged
