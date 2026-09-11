# Change: Margin ledger — no silent conservatism

## Why

Anvilate refuses to hand back a green it did not earn. It will just as readily hand back a
green it over-earned, and say nothing.

Conservatism enters a design at a dozen points and nobody sees the product. The engineer
picks a safety factor of 2.0 where the code asks 1.5. The material allowable is a
statistical minimum already two standard deviations below typical. The load was rounded
up "to be safe." A contingency was added for growth. A wall thickness was rounded to the
next stock size. Each step is defensible alone; multiplied, they produce a part that is
three times heavier than the physics requires, and no artifact anywhere states the
cumulative factor. The design-margins literature names this directly: margins get applied
to requirements and to design parameters by different people, and organizations duplicate
them without being aware of it.

This is not a niche accounting concern. It is the single largest source of unnecessary
mass, cost, and lead time in mechanical design, it is invisible to every tool on the
market, and Anvilate is unusually placed to fix it — because unlike a spreadsheet or a
CAD system, it already knows every factor it applied and where each one came from.

The rule is the mirror of no-silent-green: **every factor that makes a result more
conservative than the physics is recorded, attributed, and multiplied out.** The tool does
not decide whether the total is right. It makes the total visible, so an engineer can.

## What Changes

- New capability spec `margin-ledger`: every conservatism applied anywhere in a build is
  recorded as a typed ledger entry carrying its value, kind, origin, and the authority
  that justifies it; the cumulative factor per checked quantity is computed and reported.
- Entries are classified by kind — code-required, user-elected, statistical-basis,
  contingency/growth, rounding, and derating — because a code-required factor and a
  hunch-derived one are not the same evidence and MUST NOT render identically.
- Duplicate conservatism is detected and named: two entries of the same kind bearing on
  the same quantity from different origins are reported as possible double-counting with
  both origins named, rather than silently multiplied.
- The ledger reports the **physics-limited** result beside the delivered one: what the
  screen would have concluded with code-required factors only, so the cost of elected
  conservatism is legible as a number.
- Entries are unattributed at no point: a factor whose origin cannot be named SHALL be
  refused, because an unattributable factor is indistinguishable from an arbitrary one.
- `validation-gauntlet` renders the ledger with the scorecard and makes an unledgered
  factor a defect.

## Impact

- Affected specs: new `margin-ledger`; `validation-gauntlet` (ADDED). Interacts with
  `analysis-library` (the user-supplied allowables doctrine already carries provenance),
  `performance-budgets` (a growth allowance is a ledger entry), `uncertainty-quantification`
  (a statistical basis is a ledger entry with a band), and `calculation-report`.
- Affected code (when implemented): a ledger type threaded through check evaluation, a
  duplicate detector, cumulative computation per quantity, and report rendering.
- Explicitly out: deciding whether a factor is correct; recommending its removal;
  optimizing against the ledger; and any automatic relaxation of a user's declared factor.
