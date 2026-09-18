# What the card did not check

Anvilate answers every question the document asks. The expensive failures are the ones
nobody asked.

A card can report a clean pass on twelve checks while the part goes on to fail by
self-loosening at a bolted joint under transverse vibration, by galvanic corrosion at a
dissimilar-metal interface, by fatigue at a weld toe nobody assessed. Not one of those is a
bug in a screen. Each is a failure mode that no screen addressed and no entry mentioned —
and a silent card reads as a clean one.

## What you get

```python
from anvilate.failure_modes import coverage

report = coverage(card, {"element": "bolted_connection", "dissimilar_metals": True})
report.applicable        # how many catalogued modes apply to what the document declares
report.addressed()       # the ones a check that RAN addresses
report.planned()         # the ones with no check, left to a physical test
report.unaddressed()     # applicable, no check, no test — named, not counted
report.complete()        # never a substitute for the list
print(report)            # all of it, with the population and the floor caveat
```

## The rules

| Rule | What it means |
| --- | --- |
| Applicability keys on declared facts | A mode applies on an element class, an interface kind, an environment or a declared dissimilar-metal pair — never on free text, because a catalogue that matched prose would fire on the wording of a description rather than on the design. What a document does not state cannot make a mode apply. |
| A plan is never evidence | A mode left to a physical test is not addressed. The archetype says what would reach it; nothing has been done about it yet, and counting it as coverage is the silent green a coverage number is most likely to produce. |
| A check that did not run addresses nothing | The card already says the check did not run. Counting it would use one gap to hide another. |
| Never a bare percentage | Every rendering carries the counts, the population they came from, and the unaddressed modes by name. |
| The stage is a stage | `design`, `qualification`, `production`, `field` say where a mode is normally found — how many stages a discovery would be pulled earlier, not how bad the mode is. Nothing in the rendering ranks the modes against each other. |
| The catalogue is a floor | It says what this library knows to ask about. It cannot say that nothing else can go wrong, and every rendering says so. |
| Extensible, and clashes refused | A module or a user extends the catalogue; an id already in it is refused rather than shadowed. |

## What ships today

Five modes, each cited to a source a reader can go and read: bolt self-loosening (Junker,
SAE 690055), galvanic corrosion (ASTM G82-98 (2014)), weld-toe fatigue (EN 1993-1-9), fretting at a
clamped interface (Waterhouse), and thermal ratcheting of a clearance (ASME BPVC VIII-2
§5.5.6). All five are bound to verification archetypes rather than to checks, which is the
honest state of it: this library screens none of the five, and the report says so instead
of leaving the card silent.

## Status

This is the catalogue, the applicability resolution and the coverage report
(`openspec/changes/add-failure-mode-coverage`, groups 1, 2 and 3). Binding modes to the
checks that address them needs each check to declare its modes, which is group 2.2 and the
gates in group 4; the card does not yet carry its own coverage report, and no screen
declares the modes it addresses.
