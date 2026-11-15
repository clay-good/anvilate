# Model credibility

**A correlation never changes a verdict.** It sits beside it. A proof test that held 8%
less than the lug check predicted leaves the check reading `pass` and adds a finding
naming both numbers — because the verdict is what the analysis said, and the finding is
what the test found, and a reader needs to see the two together.

Three things come out of a recorded test.

## 1. The correlation

[Verification planning](verification-planning.md) already records an outcome: what was
measured, when, by whom, on what instrument. Give that outcome a **number** and it can be
compared with the check that planned it.

```python
from anvilate.credibility import AcceptanceBand, PredictionSense, annotate, correlate

found = correlate(
    plan, card,
    bands={"lug tension": AcceptanceBand(fraction=0.05, source="proof-test procedure §4.2")},
)
print(found[0])
# lug tension: predicted 100 kN, measured 92 kN (ratio 0.920, band ±0.05 (...)) — unconservative
card = annotate(card, found)   # the finding lands on the entry; the verdict does not move
```

| What the test said | What happens |
| --- | --- |
| Within the band | `agrees`. Nothing to report but the agreement itself, which is evidence. |
| Outside it, the unsafe way | `unconservative` — a **finding** on the card, and an escaped-defect candidate if the check passed. |
| Outside it, the safe way | `conservative` — a **note** to the [margin ledger](margin-ledger.md): conservatism the design carries that no ledger entry accounts for. |
| No band declared | `not_evaluated`. Both values and the ratio are still reported, and the output names the band it needs. |

Which direction is unsafe is the check's to state, not ours to guess: a predicted
*capacity* measured low and a predicted *response* measured high are the same failure.
Say which with `senses={"lug tension": PredictionSense.CAPACITY}`.

A declared band is required for a verdict on purpose. "Within the test corridor" is a weak
validation metric when nobody says where the corridor came from, so the band carries its
source and a reader can disagree with the band rather than with the result.

**An outcome with no number stays a valid record.** It shows as performed and
*uncorrelated* — never as agreeing. "Passed" is a performer's judgement, not a comparison.

## 2. The escaped-defect candidate

An unconservative correlation **on a check that passed** is the thing
[benchmarking](../openspec/specs/benchmarking/spec.md) defines as an escaped defect: a
green-checked part that did not hold. One is filed with the evidence bundle's digest, the
check, both values, the band and the test record, and stays listed until a person
dispositions it — as a real escaped defect (post-mortem and permanent regression), a test
or instrument issue, or a conservatism of the test itself, with the reason and the person
recorded. **Dispositioning never removes the finding from the card.**

## 3. The credibility factors

NASA-STD-7009A scores eight factors 0 to 4 so a decision-maker can see how much a result
deserves to be trusted. Anvilate proposes a score **only from evidence it holds**, names
that evidence beside every score, and scores 0 — *insufficient evidence* — where it holds
none.

The mapping is published so you can disagree with it rather than with a number. Every
ceiling is 2, and that is the honest reading of the standard: level 3 needs formal
end-to-end verification and validation points that significantly span the domain of
operation, level 4 needs comparison with the real-world system across its full operating
range. A screening library has neither, whatever its test count.

| Factor (NASA-STD-7009A Rev A) | Evidence Anvilate can hold | Proposed at most |
| --- | --- | --- |
| Data Pedigree | Bundled standard and material records with edition and clause | 2 |
| Verification | Worked-example anchors, derivations evaluated in CI | 2 |
| Validation | A recorded test correlated within its band | 2 |
| Input Pedigree | A stated origin on every input | 2 |
| Uncertainty Characterization | A declared distribution propagated by Monte Carlo | 2 |
| Results Robustness | The first-order sensitivity ranking | 2 |
| M&S History | A change and use history you state | 2 |
| M&S Process/Product Management | A managed process you state | 2 |

A reviewer may override any score with a reason, under their name; the dossier shows the
proposal, the override, the reason and the person.

**Revision A renamed the factors.** The 2008 original's *code verification*, *solution
verification*, *conceptual validation* and *referent validation* are Rev A's `Verification`
and `Validation`; `M&S History` and `M&S Process/Product Management` are new. Anything
written against the 2008 names is a revision behind.

### What a score does not claim

- **It is not a certification.** It is an assessment of the evidence held, nothing more.
- **It is not a grade.** Level 0 means *insufficient evidence*, not *bad*.
- **It does not add up.** The standard states the levels are ordinal and are not to be
  arithmetically manipulated, so there is no total, mean or overall score here, and there
  will not be one. An average of eight ordinal scales is the one number a reader would
  compare against another one.

## The validation domain

A `ValidationDomain` records, per check, the parameter ranges it has actually been
anchored and correlated over — each range naming the worked example or recorded test it
came from, so "validated from 20 to 40 mm" is visibly two points and not a continuum.
`label_checks` turns those into a label per check, and `annotate` puts it on the entry. A
use inside one is labelled *interpolative* with the range named; a use outside every one is
*extrapolative*, naming the parameter and the nearest recorded range. The verdict does not
move — an extrapolative check may well be right, and you are entitled to know that nothing
has ever been measured out there.

A check compared nowhere gets no label at all. Calling it interpolative would claim a
validation domain it does not have.

## Out of scope

Statistical validation metrics beyond ratio and difference (they plug into the same record
later). Any automatic re-tuning of a check from test data — a correlation is information
for a person and a regression for CI, never a calibration. Any statement that a result is
"validated" in a regulatory sense.

## Sources

- NASA-STD-7009A, *Standard for Models and Simulations*, Appendix E. Approved for public
  release, distribution unlimited;
  [NTRS 20160011121](https://ntrs.nasa.gov/citations/20160011121). Its factor names and
  0–4 scale are cited; nothing else is reproduced.
- ASME V&V 10 supplies the vocabulary — verification, validation, validation metric,
  validation domain. The document is copyrighted and only its terms are used.

Worked end to end in [`examples/proof_test_correlation.py`](../examples/proof_test_correlation.py).
