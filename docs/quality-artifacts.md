# Quality artifacts

**The paperwork a design is judged on, written from the design's own evidence.** In
automotive, aerospace and medical work a part is not done when it passes; it is done when
its quality records do. These exports hand those records the checks and the verification
plan Anvilate already holds, and leave every judgement that belongs to your quality system
with it.

| Export | Feeds | Built from | Stays with you |
| --- | --- | --- | --- |
| [DVP&R](verification-planning.md#the-plan-as-a-dvpr), CSV or XLSX | the design verification plan and report a validation engineer runs | the verification plan: each test item, its requirement, procedure and acceptance criterion | sample size, timing, owner, and running the test |
| Trace, CSV | a requirements tool's link table | your requirements, the scorecard and the verification plan | the requirements themselves, and whether a covered requirement is met |

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

## Not yet

FMEA rows and their rating scales, special-characteristic marks and the control-plan seed
they feed, stable characteristic numbering, risk records, and the trace as ReqIF.
