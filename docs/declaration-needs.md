# What the build needs next

Every refusal in this library is right on its own. A screen that invents a value it was not
given is the silent green the whole tool exists to prevent. The cumulative effect, on a
first run, is a card of "not evaluated" entries and no obvious next move — the same friction
from the other side. Rigor nobody can drive is not rigor.

So a check that could not run states what it needed, and the needs report collects those
statements into one list.

## What you get

```python
from anvilate.needs import needs_report
from anvilate.screening import screen_spec

report = needs_report(screen_spec(spec))
len(report)                       # how many declarations the build is waiting on
report.items[0].need.declaration  # "element_type" — the field a document would state
report.items[0].leverage          # how many screens supplying it would unblock
report.items[0].unblocks          # the checks it would resolve, named
report.tied()                     # items grouped by leverage; a group of two or more is a tie
print(report)                     # the list, with the leverage caveat printed above it
```

A `Need` names the declaration the way a document writes it (`constraints.min_safety_factor`),
what the value is in one phrase, its dimension and the units it accepts when it is a
quantity, and where an acceptable value may come from: a standard, a bundled database
record, a measurement, or the user's own statement.

## The rules

| Rule | What it means |
| --- | --- |
| The screen states its own gap | A need is carried on the not-evaluated entry that wanted it, so the report is built from what a check declared and never from a parse of its detail line. |
| A check that ran has no needs | Naming a need on a passing, failing or over-margin entry is refused at construction: it would send a reader to supply a value that changed nothing. |
| One declaration, one item | Two checks waiting on the same declaration merge into one item naming both, because the engineer's next action is one edit. |
| The count is shown beside the order | Items are ordered by how many screens they unblock and print that number, so the ordering is checkable rather than asserted. |
| Ties are ties | Items unblocking equally many screens are reported as tied, in the order the screens ran. |
| Leverage is not importance | Every rendering says so. A declaration unblocking one safety-governing check can matter more than one unblocking six secondary screens, and nothing here can tell which is which. |
| A passing card still reports its gaps | A pass computed over a subset of the checks is not a complete answer. |
| Nothing is inferred | The report never supplies a value, weakens a refusal, or changes a verdict. |

## On the command line

`anvilate check` prints the unevaluated count under the card — zero included, so a complete
card says so positively — and the report indented below it when anything is missing. `--format json`
carries the same thing per spec under `needs`, present with an empty `items` list when
nothing is missing. Neither changes the verdict or the exit code.

## The refusals that state nothing

Nine of the screening module's thirty-two refusals state a need today. The rest are listed
in [`docs/api/refusals-without-needs.txt`](api/refusals-without-needs.txt) with a cause per
site, because not every refusal has a declaration behind it: some report a capability this
library has not built (T0 geometry, T3 FEA, a published contract that needs built geometry),
some answer a declaration that is present (every declared wall clears the minimum), and some
are corrections rather than gaps — the document said something and it did not resolve, which
a needs item would misdescribe as a value nobody supplied.

A gate in `tests/test_needs.py` reads the refusals off the module's syntax tree and fails a
NOT_EVALUATED entry that neither states a need nor appears in that file, refuses a line for a
site that no longer exists, and carries a population floor so a refactor cannot turn it green
by emptying it. A second assertion is a one-way ratchet on how many refusals state their
needs.

## Status

This is the consolidated report and its CLI rendering
(`openspec/changes/add-declaration-completeness`, group 1),
with the nine screening refusals that state a need today. Profiles — a cited,
versioned bundle of declarations — and a declared screening depth are the remaining groups of
that change, and the rest of the library's refusals have yet to state their needs.
