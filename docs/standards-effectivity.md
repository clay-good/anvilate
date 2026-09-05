# Standards effectivity (which edition a citation means)

Every check here cites a clause, and the evidence bundle's whole claim is *these numbers
came from these clauses*. A clause without an edition weakens that to the point of being
unfalsifiable. AISC 360-16 and -22 both have a Chapter E. ACI 318-14 and -19 both have a
§22.8. They do not always say the same thing. **"AISC §E3" identifies a paragraph in a
book nobody named.**

## Three separate questions, kept separate

| Question | Who answers it | Where |
| --- | --- | --- |
| Which edition were the library's checks written against? | This repository, verifiably | `WRITTEN_AGAINST`, held against the source by a contract gate |
| Which edition has this project adopted? | You | `DesignBasis(pins={...})` |
| Which edition applies in this jurisdiction? | **Not this library** | see below |

That third row is deliberate. Adoption is a legal question that varies by state, county
and city, changes on schedules nobody publishes centrally, and being confidently wrong
about it is the worst failure mode available here. You say what you have adopted; the
library checks that the bundle is consistent with what you said.

## Mixing editions is allowed. Mixing silently is not.

A structure designed to one code and retrofitted under another is ordinary practice, so
forbidding it would be wrong. What the screen refuses is a bundle that *reads* as though
every number came from one book when it did not:

```
new mezzanine only         pass   all 3 references name an edition and no standard is split
whole bundle, unwaived     fail   AISC 360 appears at editions 16, 22 with no recorded
                                  waiver covering them
whole bundle, waived       pass   ... recorded waivers: AISC 360 16/22 by
                                  A. Engineer, P.E. (engineer of record) on
                                  2026-08-17: the existing frame is assessed
                                  under the edition it was designed to; new
                                  members follow the currently adopted edition
```

A `MixedEditionWaiver` requires `accepted_by` and `rationale`, and refuses a blank one. A
waiver with nobody's name on it is not an accepted risk, it is a suppressed warning — so
the entry carries the reason and the date as well as the name. Reading who signed without
reading why does not distinguish an assessed retrofit from a mistake somebody signed. See
[`examples/retrofit_two_code_editions.py`](../examples/retrofit_two_code_editions.py).

A reference at an edition *other than the pinned one* is **reported, not failed** — a
project may deliberately assess an existing structure under the code it was designed to,
and the basis is what says which is which.

## A pin nothing reads is not a pass

The screen used to answer a pin only off the citations in front of it. So a project that
pins `ASCE 7-16` — while this library's load combinations are written to ASCE 7-22 — got
a clean `pass` and no mention of either edition, as long as the bundle in hand happened
to carry no ASCE citation. The pin was accepted and read by nothing.

Two things can answer a pin, and the screen now asks both:

| The pin | Answered by | Result |
| --- | --- | --- |
| a designation this bundle cites | the citation | reported when the editions differ |
| a designation `WRITTEN_AGAINST` declares | this repository | reported when the editions differ |
| neither | nothing | `NOT_EVALUATED`, naming what *is* available to pin |

```
pins {"AISC 360": "16", "ASCE 7": "16"}   pass    ASCE 7-16 is pinned while this library's
                                                  checks are written against ASCE 7-22
pins {"AISC-360": "16"}                   n/e     not evaluated — 1 pinned standard is named
                                                  by no citation in this bundle and not
                                                  declared by this library ... Designations
                                                  available to pin: ACI 318, AISC 360, ...
```

That third row is the misspelling case, and it is the likeliest one: `"AISC-360"` is an
exact-match miss against `AISC 360`, and screening a basis against nothing must not read
as agreement. The refusal names the near misses, the way every retrieval refusal here does.

## An editionless reference is NOT_EVALUATED, never a pass

A clause with no edition cannot be checked against a basis at all. Reporting only the
references that happen to carry editions would describe a bundle nobody assembled, so
the screen reports `NOT_EVALUATED` and says how many were missing and which.

The outstanding ones are enumerated in
[`docs/api/editionless-citations.txt`](api/editionless-citations.txt) and held as a
ratchet by `tests/conftest.py`: a new editionless citation fails, and a listed one that
has since been versioned must be struck off. The list can only shrink.

It went from six lines to twenty-two the day the gate started reading the whole library.
The ratchet had been building its own reference set — the structural pack's entries plus
a hand-written sample — so every other pack's citations were outside it. Sixteen of the
twenty-two had been editionless since the day their pack shipped. A ratchet is only as
honest as its census, which is why this one now runs off the same session-wide collector
the derivation-coverage gate uses and cannot be narrower than the library it audits.

**Three of the twenty-two are paid off** — `EN 1993-1-9:2005` (twice) and
`EN 15978:2011 / ISO 14040:2006` — and each was versioned off an anchor, not a guess. The
weld-fatigue curve this library builds (N_C = 2M, N_D = 5M, N_L = 100M, m = 3 then 5) and
the §8 elastic limit are the 2005 edition, which is also the edition every
`WeldDetailCategory` in these docs already declares. The remaining nineteen stay listed
because their edition has to be *read off the standard*: BTH-1's design factors and TMS
402's allowable-stress form are identical across editions, so nothing in this repository
says which book they came out of, and inventing one would be exactly the confidently-wrong
citation the whole page is about.

## Textbooks are not debt

`names_a_standard` matches a curated list of standards bodies, not "anything
capitalised". `"Roark's Formulas for Stress and Strain, Table 8.1"` and `"Timoshenko
plate theory"` are complete citations as they stand — a textbook is cited by author, and
its printing is not a normative parameter. Counting them as missing editions would inflate
the debt with entries that can never be paid, which is how a ratchet stops meaning
anything.

## The Eurocode trap

Eurocodes are EN 1990 through EN 1999 — document numbers that read *exactly* like years.
Reading `EN 1993-1-9` as "the 1993 edition of EN" would record a wrong edition for every
Eurocode citation in the library, silently and plausibly. The parser knows the difference:
`EN 1993-1-9` names a part at no edition, and its edition is the colon suffix,
`EN 1993-1-9:2005`. A part number is not an edition either — `ISO 286-2` parses to no
edition, not to edition "2".

## The same trap, in ASME's spelling

The Eurocode guard was written for one shape of the problem and the other shape was live:
ASME Section VIII numbers its clauses `UG-37`, `UG-99(b)`, `UW-12`, and the two-digit suffix
parsed as an **edition**. Both of those citations are emitted by this library — the UG-37
reinforcement check and the UG-99 hydrostatic verification — so an ordinary pressure-vessel
bundle failed with "ASME VIII Div 1 UG appears at editions 37, 99". A gate that cries wolf
on the ordinary case is a gate that gets turned off.

What separates the two spellings is the character before the hyphen. A designation ending
in a **digit** takes an edition suffix — `AISC 360-16`, `ACI 318-19`, `AISI S100-16`. One
ending in a **letter** is a clause prefix, and the number after it is the clause. The
four-digit form needs no such test and is now read wherever it appears: `ASME B31.3-2022`,
`AWS D1.1-2020` and `ASME B36.10M-2018` used to parse as naming no edition at all, because
the year branch demanded a space or a colon in front of it.

### A third spelling, found by making the parser round-trip

`29 CFR 1926` is OSHA's construction part, and the year branch read it as the **1926
edition** of something called `OSHA 29 CFR`. This library cites it beside a B30.20 proof
test, so a bundle carrying `29 CFR 1926` and `29 CFR 1910` would have read as one
regulation at two editions.

Three spellings of one trap now: a Eurocode part that reads like a year, an ASME clause
that reads like a two-digit edition, and a CFR part that reads like a year. **The gate that
finds them is the round trip** — parse every citation the library emits and render it back.
A document number swallowed as an edition changes the rendering, which is how `29 CFR 1926`
surfaced as `OSHA 29 CFR 1926 .251(a)(4)`. A hand-written expectation would not have found
it, because nobody writes down the citation they were not thinking about.

## Where a bundle says it

`BundleSections.design_basis` is the adopted-editions record for a bundle, and it is
optional — but its *absence* is named by `missing()`, so a bundle whose citations nobody
checked and one whose citations check out no longer render identically.

The section is informational until it fails, and the split is deliberate. Most references
in this library name a clause and no edition, so `NOT_EVALUATED` is the ordinary answer;
letting it into the roll-up would put nearly every bundle at `NOT_EVALUATED` over checks
that ran and passed, which teaches a reader to skip the status line. A `FAIL` is different
in kind — the citations contradict each other, so the bundle reads as though every number
came from one book and did not. That is evidence misrepresenting itself, and a roll-up
saying `PASS` over it would be doing the same thing one level up.

## What is deliberately not here

- **No jurisdiction table.** The proposal allows an advisory offline mapping; shipping one
  means shipping a staleness-dated claim about the law in every US jurisdiction, and an
  advisory answer to a legal question is the kind of thing that gets quoted as an
  authoritative one.
- **No edition-difference registry entries.** The mechanism for "this provision changed
  between editions, here is the result under each" is worth building; populating it needs
  each difference verified against the publishers' own comparison documents, and an
  unverified entry would be worse than an empty registry.

## Reading a citation is linear in what it reads

The designation half of the citation pattern was an unbounded lazy repetition, so the scan
was **quadratic in the length of the subject** — the time quadrupled every time the length
doubled. A reference a few thousand characters long took a tenth of a second, one four times
that took seconds, and a long paste did not finish at all.

The subject is not this library's own text. `design_basis_scorecard` is handed
`entry.reference` for every entry of a scorecard, and a scorecard comes back out of the
subject store and out of an attestation envelope — where the field was a free string with no
length on it. So `anvilate export` over one such entry hangs, and nothing in the run says why.
That second half is closed as well now: `reference` is a citation, a citation is at most 1,024
characters, and a linear scan of a bounded subject is bounded work. Both halves are needed —
a linear scan of an unbounded string is still unbounded.

The repetition is bounded now, which makes the scan linear, and the bound is a fact about the
data rather than a guess: the longest designation this library emits is "Aluminum Design
Manual" at 22 characters against a bound of 62. A session-wide rule over every citation the
library actually puts on an entry reports any designation that reaches **half** the bound —
before it is exceeded, because a rule that fires at the bound fires after the first real
standard has been mis-parsed.

**That the repetition is bounded is checked against the parsed pattern, not against its
text.** The gate here used to look for `{0,62}?` as a substring, which a pattern with a
bounded repetition in one place and an unbounded one in another satisfies — the defect
itself. `re._parser` is walked instead, so the claim is about every repetition in the
pattern, and a test builds the pattern that passes the old check and fails the new one.
`_EUROCODE` is deliberately exempt: its `(?:-\d+)*` is unbounded and cannot backtrack,
because every iteration has to begin with a literal `-`.

There is no longer a timing assertion. The one that was here compared 4k against 16k and
required under 8x, which measures the machine as much as the pattern: the larger run does
four times the work and is four times as exposed to being descheduled, so it failed three
times running under load and passed on a quiet machine at the same commit. The two
structural facts — a bounded pattern and a bounded subject — are what made it true, and
they are decidable.
