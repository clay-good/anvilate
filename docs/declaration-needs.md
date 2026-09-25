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

## What applies to this document

`what_applies(card)` answers the question before the needs report does: every screen the
document reaches, and for each whether it runs now, is deferred by the declared screening
depth, or needs something, with the declarations it needs:

```python
from anvilate.needs import what_applies

print(what_applies(screen_spec(spec)))
# 2 screens apply (1 runs now, 1 needs, 0 deferred)
#   T1 analytical: needs element_type, element_params
#   material resolution: runs now
```

A screen that could not run and names no typed need shows the reason its own check gives.

## Profiles: many declarations in one action

Answering the report one value at a time is the other half of the friction. A `Profile` is a
cited, versioned set of declarations — an environment, a shop practice, a handling case —
bound in a single action:

```python
from anvilate.profile import Applicability, Profile, SuppliedValue
from anvilate.units import Quantity

coastal = Profile(
    id="ENV-COASTAL", version="v2.1",
    citation="ISO 12944-2 C5-M, company practice EP-3",
    applicability=(Applicability(context="ambient temperature",
                                 minimum=Quantity(magnitude=253.15, unit="K"),
                                 maximum=Quantity(magnitude=323.15, unit="K")),),
    supplies=(SuppliedValue(declaration="environment.corrosivity", value="C5-M"),
              SuppliedValue(declaration="manufacturing.min_wall",
                            value=Quantity(magnitude=6.0, unit="mm"))),
)

binding = coastal.bind({"ambient temperature": Quantity(magnitude=300.0, unit="K")})
binding.declarations()   # every value the profile supplies, in one mapping
binding.attribution()    # per declaration: "profile ENV-COASTAL v2.1 (ISO 12944-2 …)"
tightened = binding.override("manufacturing.min_wall", Quantity(magnitude=8.0, unit="mm"))
tightened.attribution()["manufacturing.min_wall"]  # "user override of profile ENV-COASTAL v2.1"
```

| Rule | What it means |
| --- | --- |
| Applicability is checked, not documented | Binding outside the profile's own stated range is refused naming the value and the bound. A bound the context does not state is refused too: an applicability nobody checked is an applicability nobody has. |
| Every value is attributed | A profile-supplied value carries the profile's id, version and citation wherever it appears, so a number that governs a verdict never reads as one the engineer stated. |
| An override is the user's, and keeps what the profile said | The profile's value stays beside the override, so a reader can see what changed and from what. Overriding a declaration the profile never supplied is refused. |
| A profile supplies declarations only | It does not screen, weaken a refusal, or change a verdict. |

### Applying a profile to a document

`binding.apply(spec)` returns the document with every value the profile supplies filled in:

```python
shop = Profile(
    id="SHOP-STRUCT", version="1.0.0", citation="the shop's structural practice, rev C",
    applicability=(Applicability(context="plate thickness",
                                 minimum=Quantity(magnitude=3.0, unit="mm"),
                                 maximum=Quantity(magnitude=25.0, unit="mm")),),
    supplies=(SuppliedValue(declaration="constraints.min_safety_factor", value=2.0),),
)
applied = shop.bind({"plate thickness": Quantity(magnitude=10.0, unit="mm")}).apply(spec)
applied.constraints.min_safety_factor.origin     # Origin.PROFILE_SUPPLIED
applied.constraints.min_safety_factor.rationale  # "profile SHOP-STRUCT 1.0.0 (the shop's …)"
```

The value lands with the origin `profile_supplied` and the profile named in its rationale;
an override lands as the engineer's own (`user_stated`), naming the profile value it replaced.
Every check judged against a profile-supplied required minimum or upper band says so in its
own line — `… vs required minimum 2.00 — the required minimum was supplied by profile
SHOP-STRUCT 1.0.0 (…)` — which is the sentence the terminal, the calculation report and the
evidence bundle all print. The bundle also carries the document itself, origin included.

Three things are refused, each naming the declaration:

| Refused | Why |
| --- | --- |
| A field that cannot record an origin | Only a provenanced field (`units`, and `constraints`' `max_mass`, `min_safety_factor`, `max_safety_factor`, `max_cost`) has somewhere to say where its value came from. Anywhere else the value would read as one the engineer stated. |
| A value the document already states | A profile fills what is missing. Replacing what the engineer wrote would make their number read as the profile's; override the binding instead. |
| A path the document does not have | A value put nowhere is a value silently dropped. |

## Declared screening depth

A document can say how deep it wants to be screened, so an early-concept run is a short
honest card rather than a long red one:

```yaml
acceptance: {tiers: [T1_analytical, T2_dfm], depth: concept}
```

`concept` screens the part and what it is made of — the element's pack checks, the
references they resolve, the loads and their combination, the bounds the document states.
`detailed`, the default, adds the work that only makes sense once the drawing exists: the
toleranced dimensions against the process floor, the stack-up chains, the geometric
tolerances, and the interfaces this part publishes.

| Rule | What it means |
| --- | --- |
| A deferral is its own status | `out_of_depth` is neither a pass nor `not_evaluated`: "I chose not to screen that yet" and "I could not screen that" are different facts, and no surface renders them alike. |
| Both counts, always | The card, `anvilate check` and the calculation report state the unevaluated count and the out-of-depth count separately, zeros included, so a complete card says so positively. |
| A deferral blocks nothing | The exit code is unchanged and the verdict is not a failure — but a card whose only blemish is a deferral rolls up as `out_of_depth`, never as `pass`. |
| Deferring is never an improvement | `anvilate diff` treats a check that stops running as a regression, whether it became `not_evaluated` or was deferred: declaring a depth must not be a way to silence a failing gate. Only `out_of_depth → pass` is an improvement. |
| The deferral says how to undo it | Each out-of-depth entry names the declaration that would have driven the check and the depth that would run it. |
| The default changes nothing | A document that declares no depth is screened exactly as before. |

### Going deeper names its price and its return

```python
from anvilate.needs import deepening
from anvilate.spec import ScreeningDepth

change = deepening(spec, ScreeningDepth.DETAILED)
change.newly_run        # the checks that now produce a verdict, named
change.newly_required   # the needs those checks add that the shallower screen never had
print(change)           # "concept -> detailed: runs 3 more check(s), needs 1 more declaration(s)"
```

Both halves, because a raise has a return and a price: reporting only the needs makes a
deeper screen read as a new wall, and reporting only the checks makes it read as free. A
raise to the depth already declared, or to a shallower one, is refused rather than reported
as a change of nothing.

## The refusals that state nothing

Nine of the screening module's thirty-three refusals state a need today. The rest are listed
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

The same gate reads every other module that builds a refusal. Outside screening, the library
has 78 more, and 51 state a need today: every screen that stops for a value names it, with the
dimension and units to write it in where it is a quantity. The optomechanics screens name the
gap a shock is judged against or the pressure differentials a window sees (which an
environment profile's ambient pressure bounds). The timber screens name the adjusted NDS
design value, the B31.3 screen the Table A-1 allowable, and a structural pack screen the
material property its design allowable could not be read for. The screens that take a
computed accounting (a DSM strength, a UG-37 area balance, a FAD point) name the function
that makes it. The three assembly screens a document's `assembly` block reaches name the path
it writes: `assembly.parts[].insertion`, `assembly.adjustments[].access` and
`assembly.inspections[].access`.

The other 27 are excused by name in the same file, each with its cause. Most are not gaps: a
budget or a dependency chain waiting on a check whose own entry states the need, a correction
of a value the caller did supply, an answer (zero demand, a wall the allowances consume), or a
capability this library has not built. The backlog is empty, and a per-module ceiling in
`tests/test_needs.py` keeps it that way: a new refusal that states nothing, in any module,
fails the build until it states its need or is excused with a cause.
The sweep sees a refusal however it is spelled, whether as a status keyword,
a status chosen in a branch and held in a local, or an `update` dict on a copy. Every unit a
declared need offers is also parsed and checked against the dimension it states.

## Status

This is the consolidated report and its CLI rendering
(`openspec/changes/add-declaration-completeness`, group 1),
with the nine screening refusals that state a need today, and the library's others counted
above. A profile's record, binding,
applicability check and overrides ship too (group 2), and so does applying a binding to a
document with every profile-sourced value marked through the spec, the card, the calculation
report and the bundle (2.3, 4.3). The declared screening depth and the depth-raise report
ship too (group 3).
