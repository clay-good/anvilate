# Design notes: Model credibility

Research done on 2026-10-19.

## NASA-STD-7009A credibility factors

**Read from the standard on 2026-11-14, and the proposal's first draft had the wrong
names.** Revision A renamed the set. The 2008 original's *code verification*, *solution
verification*, *conceptual validation* and *referent validation* are Rev A's single
`Verification` and `Validation` factors, and Rev A adds a third category, *Supporting
Evidence*, carrying two factors that did not exist before. Appendix E, figure 2 and
table 3 are the authority for the list below.

Eight factors in three categories, each scored 0 to 4, 0 meaning insufficient evidence:

| Category | Factor | What Anvilate already holds as evidence |
| --- | --- | --- |
| M&S Development | Data Pedigree | Standards and materials database provenance per record |
| M&S Development | Verification | Worked-example anchors and derivation-evaluation gates in CI (code verification); no solution verification for a closed form, which is a correct 0 |
| M&S Development | Validation | The correlation this change adds |
| M&S Use | Input Pedigree | Value origin (user-stated, database-resolved, default, agent-read, confirmed) |
| M&S Use | Uncertainty Characterization | Monte Carlo bands from `uncertainty-quantification` |
| M&S Use | Results Robustness | Sensitivity ranking from the same capability |
| Supporting Evidence | M&S History | A declared change and use history; nothing holds one today |
| Supporting Evidence | M&S Process/Product Management | A declared managed process; nothing holds one today |

Two statements of the standard that the implementation obeys rather than paraphrases:

- **E.4: the assessments are ordinal only and "should not be arithmetically
  manipulated."** `CredibilityFactorSet` therefore offers no total, mean or overall score,
  and a test holds that absence — an average of eight ordinal scales is a number with no
  meaning that every reader would nonetheless compare.
- **E.4: the assessment of each factor level is a discrete step function, with no partial
  credit.** Levels are integers, never interpolated.

Every proposed level is capped at 2, published as `EVIDENCE_CEILINGS` with the reason per
factor. That is the honest reading of table 4 to table 6: level 3 needs *formal*
verification practices over the end-to-end model and validation points that significantly
span the domain of operation; level 4 needs comparison against the real-world system
across its full operating range. A screening library anchored to worked examples and
correlated against whichever tests a user records has neither, whatever its test count. A
reviewer who believes a higher level is earned says so as an override, under their name.

The standard is approved for public release, distribution unlimited (NTRS 20160011121,
"Work of the US Gov. Public Use Permitted"). Sources:
https://ntrs.nasa.gov/citations/20160011121,
https://ntrs.nasa.gov/api/citations/20160011121/downloads/20160011121.pdf

Anvilate proposes a score only with evidence it can point at, and never above the level
that evidence supports. The mapping from evidence to level is a published table in the
docs, so a reviewer can disagree with it rather than with a number.

## ASME V&V 10 vocabulary

- Verification: the model is solved correctly. Validation: the model is the right one for
  the use, shown by comparison with a referent (test).
- Validation metric: a quantitative measure of agreement between prediction and
  experiment. First phase: ratio and difference with units; later phases may add
  probabilistic metrics under the same record.
- Validation domain versus intended-use domain: a prediction outside the domain where the
  model was compared is extrapolative. The ASME 2025 teaching module and its 2026 draft
  make this distinction explicitly.

Sources:
https://asme.org/getmedia/fedec7de-ceed-4203-aa1f-5f2e876b3fb0/VVUQ-Intro-Module-Part-3-Validation.pdf,
https://faa.niar.wichita.edu/Portals/0/Uncertainty%20Quantification%20and%20Validation%20ASsessment%20-%20Thacker-FAA_Workshop.pdf

## Why unconservative is the finding and conservative is a note

A measured capacity above the predicted one, or a measured response below it, means the
check is conservative; that is information for the margin ledger (a possible elected
conservatism nobody elected), not a defect. A measured capacity below the prediction is
the class of failure the escaped-defect process exists for. Both are recorded; only one
is a finding.
