# Tasks: Standards effectivity

## 1. Contracts

- [x] 1.1 Citation type gains standard + edition + clause, enforced at registration
- [x] 1.2 Design-basis type (standard → edition pins) on the spec
- [x] 1.3 Mixed-edition waiver type; superseded-edition registry with dates

## 2. Implementation

- [x] 2.1 Basis resolution per check; unsupported-edition → "not evaluated"
- [x] 2.2 Bundle-level mixed-edition gate
- [ ] 2.3 Edition-difference registry + side-by-side evaluation reporting — DEFERRED: the
      mechanism is worth building, but every entry needs verifying against the publishers'
      own comparison documents, and an unverified entry is worse than an empty registry
- [ ] 2.4 Optional offline jurisdiction mapping — DECLINED: shipping one means shipping a
      staleness-dated claim about the law in every jurisdiction, and an advisory answer to a
      legal question is the kind of thing that gets quoted as an authoritative one

## 3. Tests

- [x] 3.1 Editionless citation fails registration (CI-enforced across all checks)
- [x] 3.2 Mixed-edition bundle blocked without waiver, allowed with it
- [x] 3.3 Superseded label renders without changing the verdict
- [ ] 3.4 Edition comparison reports both results — follows 2.3

## 4. Docs & examples

- [x] 4.1 Example: same beam checked under two editions, difference explained
- [x] 4.2 Explanation page: why Anvilate will not tell you which code applies to you

## Scope as shipped

- **1.1 is a ratchet, not a flag day.** Requiring an edition on every citation at once
  would mean back-filling editions onto clauses nobody re-read. Instead the debt is
  enumerated in `docs/api/editionless-citations.txt` and gated in both directions, so a
  new citation must carry an edition and a paid-off one must come off the list.

  **It stood at two entries when the gate landed, and that number was wrong.** The gate
  built its own reference set — the structural pack's entries plus whatever a hand-written
  sample happened to reach — so every other pack's citations were outside the thing auditing
  them, and "13 of 16 carried an edition" described 16 references out of a library that
  builds far more. Moved onto the session-wide collector in `tests/conftest.py`, the debt
  read **22**. Sixteen of those had been editionless since the day their pack shipped; the
  seventeenth reason they were not listed is that nothing was looking.

  **19 remain.** Three were paid off against anchors already in this repository — EN
  1993-1-9:2005 twice (the curve anchors this library builds, and the edition every
  `WeldDetailCategory` in the docs already declares) and EN 15978:2011 / ISO 14040:2006. The
  other nineteen are **not payable by reading this repository**: BTH-1's design factors
  (2.00/3.00, 1.20 on fracture) and TMS 402 §8.2.4's allowable-stress form are identical
  across their editions, so no constant here identifies one, and guessing would manufacture
  the confidently-wrong citation the ratchet exists to prevent. The reason is recorded in
  the file itself so it is not re-derived.

  The lesson is the general one: **a ratchet is only as honest as its census**, and a census
  that builds its own corpus measures the corpus.
- The gate distinguishes a **standard** from a **textbook**: "ASME BTH-1 §3-3" is debt,
  "Timoshenko plate theory" is not. Counting textbooks would inflate the list with
  entries that can never be paid, which is how a ratchet stops meaning anything.
- The parser knows a **Eurocode number from a year**: EN 1990-1999 are document numbers,
  not editions, and reading `EN 1993-1-9` as a 1993 edition would have been silent and
  plausible.
