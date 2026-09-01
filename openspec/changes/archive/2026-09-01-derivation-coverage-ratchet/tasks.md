# Tasks: Derivation coverage ratchet

## 1. Decide

- [x] 1.1 What identifies a check. **The clause it cites** — the same key
      `docs/api/editionless-citations.txt` uses, and the thing a reviewer reads. The
      alternatives were measured and lost: the constructing function collapses to
      `scorecard.py:from_safety_factor` for every pack, because that is how entries are
      built, and the citation is attached later by `model_copy`, so a (function, citation)
      pair matched on 1 of 88 sites. What the clause key loses — two checks citing one
      clause are one line — is bought back by counting strictly: a clause is covered only
      when EVERY evaluated entry citing it carries a derivation.
- [x] 1.2 How the gate harvests. **A session-wide collector in `tests/conftest.py`**, the
      shape the disarmed-approx ratchet already proved: it costs nothing, sees everything
      4,556 tests build, and cannot drift the way a hand-written census would. Neither
      ordering-sensitive nor a second suite run.

## 2. The registry (follows 1.1)

- [x] 2.1 Two categories in `docs/api/underived-checks.txt`, `[lookup]` and `[debt]`, each
      line carrying its reason.
- [x] 2.2 Classify. 47 clauses read one at a time: 4 lookups, 43 debts.

## 3. The gate (follows 2)

- [x] 3.1 Report the ratio. Every full run prints it; it stands at 15/62.
- [x] 3.2 Fail on a clause in neither list, naming it.
- [x] 3.3 Ratchet downward-only, and enforce the reclassification rule from the data
      rather than from the reason: a clause whose entries carry a computed safety factor
      cannot be a lookup.

## Scope as shipped

- **The measurement moved, twice, and both moves were corrections.** The proposal measured
  18 of 75 clauses derived. Excluding entries the *tests* build — a fixture citing
  `AISC 360-16 §J4.1` is not one of the library's checks — dropped 13 clauses. Excluding
  `NOT_EVALUATED` entries, which have no result and so nothing to show the work for,
  removed two false debts (`AISC 360-16 Ch. E` and `Ch. G` were fully worked and looked
  partial only because of their refusals) and retired four clauses the suite never drives
  to a verdict at all. Collecting at entry construction rather than at `Scorecard`
  construction then *added* six clauses the proposal's harvest never saw, because those
  checks return their entries as a tuple and never reach a card. Net: 15 of 62.
- **The two categories are told apart by the data, not the prose.** The spec's third
  scenario — a debt must not be retirable by relabelling — is enforced by refusing a
  `[lookup]` line for any clause whose entries carry a computed safety factor. A safety
  factor is a quotient and a quotient is a formula. Moving `NDS` to `[lookup]` fails the
  run naming 72 entries, without anyone reading the reason.
- **Two of the four rules read an absence and only a full run may act on them.** "This
  debt has no underived entry left" and "that test did not run" are the same observation
  on a filtered run: `pytest tests/test_contract.py` alone reaches the derived half of the
  plate checks and reported the plate clause as paid off. Those two live behind the same
  full-run guard the approx ratchet uses; the other two fire on positive evidence and are
  correct on any subset.
- **Clauses are the key, so a check that cites nothing is outside the gate.** 1,865
  entries carry no citation — screening constraints, load entries, DFM gaps. The
  effectivity ratchet has the same blind spot for the same reason, and closing it means
  giving those entries a citation, which is a different change.
- **No derivation was written here.** The debt is now counted and cannot grow silently;
  paying it down is 43 separate pieces of work against 43 standards.
