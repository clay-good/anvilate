# Design notes: Model credibility

Research done on 2026-10-19.

## NASA-STD-7009A credibility factors

Eight factors, each scored 0 to 4 on an ordinal scale, 0 when evidence is insufficient:

| Factor | What Anvilate already holds as evidence |
| --- | --- |
| Data pedigree | Standards and materials database provenance per record |
| Input pedigree | Value origin (user-stated, database-resolved, default, agent-read, confirmed) |
| Code verification | Worked-example anchors and derivation evaluation gates in CI |
| Solution verification | Mesh-convergence study on FEA results; none for closed-form checks (which is a correct 0 or a stated "not applicable") |
| Conceptual validation | Stated modeling assumptions on every physics result |
| Referent validation | The correlation this change adds |
| Results uncertainty | Monte Carlo bands from `uncertainty-quantification` |
| Results robustness | Sensitivity ranking from the same capability; neighborhood checks from `add-design-optimization` |

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
