# Change: Margin-of-safety reporting — the stress report an aerospace reviewer expects

## Why

An aerospace stress engineer does not hand in "safety factor 2.4, pass". They hand in a
margin table. Each row gives:

- a part and its failure mode;
- the governing load case and the applied load;
- the allowable, with its statistical basis and source;
- the factor of safety and any special factors;
- the margin of safety, MS = allowable / (applied × FS × special factors) − 1.

Yield and ultimate get separate rows. The pass rule is MS ≥ 0. Reviewers at design
reviews look for the lowest margin in each subsystem, then check the free body that
produced it. Space, defense and heavy-equipment programs use the same format, and
automotive structural teams increasingly do too.

Anvilate already computes most of the checks. What it lacks is the bookkeeping that makes
a reviewer trust them. Four pieces of it are missing:

- **Limit or ultimate.** Every load must say whether it is a limit or an ultimate load.
  Factoring an ultimate load again, or forgetting to factor a limit load, is the classic
  error.
- **Factor sets by program.** Factors are chosen by program, not by taste. The
  public-domain sources give them per verification approach:
  - NASA-STD-5001B for prototype and protoflight hardware;
  - GSFC-STD-7000B for static and random loads, with higher no-test factors;
  - 14 CFR 25.303 for transport aircraft ultimate loads (1.5);
  - 14 CFR 25.625 for fitting factors (at least 1.15).
- **Allowable basis.** A primary-structure ultimate check on a "typical" property is not a
  margin anyone will sign.
- **Hundreds of load cases, one governing row.** Programs analyze hundreds or thousands of
  cases. The table shows the governing case for each check, with how many were evaluated.

## What Changes

| Area | Change |
| --- | --- |
| Load tagging | Every load in a margin report is tagged limit or ultimate. Ultimate loads are never factored again, and an untagged load in a margin report is refused. |
| Factor sets | Named, cited factor sets bundled from public-domain sources, plus user and company sets. A set states its yield and ultimate factors, special factors and their stacking rule, and the allowable basis it requires. |
| Margin of safety | MS computed per check for yield and ultimate under the bound set, with every factor in its own column. |
| Verification approach | Whether an item is qualified by test or by analysis alone changes the factors, as the source documents prescribe. Materials the set excludes from analysis-only qualification are refused. |
| Envelope | Each check runs over every load case and reports its governing case, the count evaluated, and any ties. |
| Margin table | CSV, XLSX and a report section, sorted by margin, with the lowest margin per subsystem summarized for design reviews. |
| Free bodies | Each governing row can render its free-body diagram: loads in, reactions out, equilibrium residual. |

## Impact

- New capability: `margin-of-safety-reporting`. Delta: `calculation-report` (ADDED).
- Builds on:
  - the scorecard, which stays the verdict;
  - `add-margin-ledger`, which records the factors applied;
  - load combinations;
  - `add-cae-handoff`, the source of many-case loads;
  - `add-product-structure`, for subsystem roll-up.
- Complements `add-margin-ledger`. The ledger answers "how conservative is this, in
  total"; this change answers "what margin, under which program's rules".
- Licensing: only factor values read from public-domain documents are bundled, each with
  its clause. Paid standards' factors are entered by the user with a citation.
- Explicitly out: certification credit, and fitting-factor waivers. A waiver is the
  user's declared decision with its basis.
