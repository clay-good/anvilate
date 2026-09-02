# Change: Let a check say it has no formula, instead of a side file guessing per clause

## Why

The derivation-coverage ratchet keys on the clause a check cites, because that was the only
stable identity a `ScorecardEntry` carried. It works, and it has one failure the registry
was warned about at the time: **a clause covering more than one check is one line, and the
line has to be right for all of them.**

Three of the sixteen remaining debts are that failure and nothing else. Each is a clause
whose computed entries are fully worked and which cannot come off the list because one
entry beside them has nothing to render:

| Clause | Derived | Blocked by |
| --- | --- | --- |
| `AISC 360-16 §L3` | 8 of the pack's support/load combinations | 26 beam load cases with no `deflection_formula`, 3 of which are a numeric root of the elastic curve and have no symbolic form at all |
| `ASCE 7-22 §2.3.1` | the capacity-vs-combination screen | the spec-screening entry that reports *which* combination governs and re-resolves the set from its name |
| `ASME BTH-1 §3-1.4` | the stress-range margin | the Class 0 exemption entry, a PASS that states an exemption and calculates nothing |

The registry cannot distinguish them because it addresses clauses and the difference is
per entry. Splitting the key is not a matter of taste: as it stands, paying off the
derivable half of any of these three changes the ratio by nothing and the list by nothing,
which is a meter that stops moving while the work happens.

## What Changes

**A check declares its own absence of a formula, on the entry, where the check is.** The
side file exists because nothing on a `ScorecardEntry` could say "there is no formula
here"; the requirement's own words are "explicitly registered as tabular-only **with a
stated reason**", and the honest place for that reason is next to the code that knows it.

Three kinds have to stay apart, and today the registry can only express two:

- **no formula** — an exemption, an identification line, a table comparison, a consistency
  verdict. Complete as it stands.
- **no symbolic form** — a numerically solved result. There is a formula; it is a root of
  an equation and cannot be written as a substitutable line. Different from the first, and
  the fallback table is the correct rendering for it rather than a shortfall.
- **debt** — a closed form nobody has written down yet.

The second is new. It is not a lookup (there is real mathematics behind it) and it is not
debt (nobody will ever pay it off), and filing it as either is the collapse the current
registry forbids for the other pair.

## Impact

- Affected specs: `calculation-report`.
- Affected code: a field on `ScorecardEntry`, the coverage ratchet in `tests/conftest.py`,
  and `docs/api/underived-checks.txt`, which shrinks to the clauses that are genuinely
  debt everywhere they are cited.
- **Nothing is wrong today that this fixes.** The registry's lines say precisely why each
  clause is on the list. What it fixes is that three of them cannot be worked off, so the
  ratio understates the work done and will keep understating it.

## Open, and not a detail

**Does the reason belong on the entry or on the check that builds it?** On the entry it
travels into the evidence bundle and the JSON, where a consumer can act on it — and it is
one more field on a type that already has eleven. On the builder it stays out of the
payload and the gate has to reach the builder to read it, which is the identity problem
this change exists to escape. The bundle argument looks decisive, but a field that every
entry may set and almost none does is how a model accumulates.
