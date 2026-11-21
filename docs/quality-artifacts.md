# Quality artifacts

**The paperwork a design is judged on, written from the design's own evidence.** In
automotive, aerospace and medical work a part is not done when it passes; it is done when
its quality records do. These exports hand those records the checks and the verification
plan Anvilate already holds, and leave every judgement that belongs to your quality system
with it.

| Export | Feeds | Built from | Stays with you |
| --- | --- | --- | --- |
| [DVP&R](verification-planning.md#the-plan-as-a-dvpr), CSV or XLSX | the design verification plan and report a validation engineer runs | the verification plan: each test item, its requirement, procedure and acceptance criterion | sample size, timing, owner, and running the test |
| [Design FMEA](#design-fmea), CSV or XLSX | the DFMEA worksheet: one row per failure mode, its prevention and detection controls | the failure-mode catalogue, the scorecard and the verification plan | severity, effects, your action-priority matrix, and the actions |
| Trace, CSV or ReqIF 1.2 | a requirements tool's link table, or the tool itself through ReqIF | your requirements, the scorecard and the verification plan | the requirements themselves, and whether a covered requirement is met |

## Requirement trace

Declare each requirement with the names of the checks or test items that address it, and
`trace_requirements` follows each name through the scorecard and the plan:

```python
from anvilate.trace import Requirement, trace_requirements

report = trace_requirements([
    Requirement(id="R-1", text="lift 100 kN with a margin", source="customer spec §3.1",
                addressed_by=("beam bending",)),
    Requirement(id="R-2", text="10-year service life", source="customer spec §5.2"),
], scorecard=card, plan=plan)
report.uncovered        # ('R-2',)
report.untraced_checks  # every check no requirement names
report.to_csv()
report.to_reqif(as_of=date(2026, 11, 16), title="Lifter trace")
```

| A row says | When |
| --- | --- |
| `uncovered` | nothing addresses the requirement: the 10-year life with no fatigue check and no test |
| `covered`, and the worst status of what addresses it | a check or a test item does; coverage is not a verdict, and a requirement on a failing check is covered and fails |
| evidence | each test item with a recorded outcome, and its verdict; a planned test is not evidence |
| `untraced` | a check no requirement names, as its own row so a requirements tool sees it |

A check brings the test items standing behind it, and a test item brings its recorded
outcome. A name that is neither a check on the card nor an item of the plan is refused:
a trace to something that does not exist reads as coverage and is none.

## The trace as ReqIF

`to_reqif` writes the trace as a ReqIF 1.2 document, the OMG exchange format requirements
tools import. Each requirement is a spec object whose `ReqIF.ForeignID` is its id and whose
string attributes carry its text, source, coverage, status, checks, test items and
evidence, so an uncovered requirement arrives marked uncovered. The untraced checks are a
specification of their own, so they are not lost in the crossing.

The document carries no clock: `as_of` stamps its creation time and every element's last
change, and the same trace on the same day is the same bytes. Every emitted document is
validated against OMG's published `reqif.xsd` in CI's scheduled interchange job, alongside
the QIF and DCC schemas.

## Design FMEA

`fmea` writes one row per failure mode the catalogue applies to the item. Each row names
the checks that prevent the mode and the test items that would detect it, so a reader can
follow every control to its entry:

```python
from anvilate.fmea import FmeaDeclaration, fmea, load_action_priority

report = fmea(card, {"element": "angle_bracket", "interfaces": ("bolted_face",)},
              item="motor bracket", function="hold the motor to the frame",
              plan=plan, catalog=team_catalog,
              declared={"joint loosening": FmeaDeclaration(severity=9, effect="motor drops")},
              priority_matrix=load_action_priority(matrix_csv, source="QP-7.3 rev 4, table 2"))
report.to_csv()   # or to_xlsx(): the rows, and a sheet naming where every rating came from
```

| Column | Comes from |
| --- | --- |
| failure mode, cause / mechanism, discovery stage, citation | the failure-mode catalogue, with your own modes added through `ModeCatalog.extended` |
| prevention controls | the checks that ran and address the mode, with their status |
| detection controls | the plan's test items behind those checks; else the physical test the catalogue names, marked not on the plan |
| effect, severity | you, per mode. Never inferred: what a failure does to the system and to people is not something a part screen can know |
| occurrence, detection | the bands below, ranked on Anvilate's scale or yours |
| action priority | your matrix only. With no severity or no matrix, the cell says which one is missing |

The rows are as complete as the catalogue, which is a floor and never an exhaustive list:
the export says so.

### Rating scales

Occurrence and detection are rated by **band of evidence**: what the design record
actually shows. Anvilate publishes its own ranks for the bands. They are not a reproduction
of any handbook table, and rank 1 is held back on both, because no design record shows
that a mode cannot occur or that a process is error-proofed.

| Occurrence band | Means | Rank |
| --- | --- | --- |
| `unaddressed` | no check that ran addresses the mode | 10 |
| `check-fails` | a check addressing it fails | 10 |
| `margin-below-1.1` | the worst addressing check passes with under 10% over its required factor, inside the scatter of material and load | 7 |
| `passed-no-margin` | the checks pass and state no factor, so it cannot be told from a thin pass | 6 |
| `margin-1.1-to-1.5` | the worst check holds 1.1 to 1.5 times its required factor | 5 |
| `margin-1.5-to-2` | 1.5 to 2 times | 3 |
| `margin-2-or-more` | every check holds twice its required factor or more | 2 |

| Detection band | Means | Rank |
| --- | --- | --- |
| `test-recorded` | a test item on the plan has a recorded outcome | 2 |
| `test-planned` | a test or demonstration on the plan reaches the mode, not yet run | 4 |
| `inspection-planned` | only an inspection on the plan reaches it | 5 |
| `test-named` | the catalogue names a physical test; the plan holds none | 7 |
| `analysis-only` | a check ran; analysis predicts and does not detect | 8 |
| `none` | nothing would catch it before release | 10 |

The margin is the computed safety factor over the required one; over several checks the
band with the highest rank wins. A deferred (out-of-depth) or not-evaluated check bounds
nothing.

### Your own tables

Your quality system's ranks for the same bands load from CSV, `band,rank`, one line per
band, with `load_rating_scale(text, kind="occurrence", source=...)`. Your action-priority
matrix loads with `load_action_priority(text, source=...)` from
`severity,occurrence,detection,priority`, each rank a number or a range such as `7-10`:

```text
severity,occurrence,detection,priority
9-10,7-10,1-10,H
9-10,1-6,1-10,M
1-8,1-10,1-10,L
```

Every one of the 1,000 combinations must get exactly one priority; a gap or an overlap is
refused with the first combinations it hits. A table with no source is refused, since the
export names it. No matrix ships with Anvilate: the handbook matrices most programs use are
licensed, and a test sweeps every bundled file to keep one from arriving.

## Not yet

Special-characteristic marks and the control-plan seed they feed, stable characteristic
numbering, and risk records.
