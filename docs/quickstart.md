# Quickstart

Install, screen a part, read the verdict. Ten minutes, no network, no CAD.

## Install

Python 3.11 or newer. Anvilate is pre-alpha and is not on PyPI yet, so the install is from a
clone — the same one the [README](../README.md) gives:

```bash
git clone https://github.com/clay-good/anvilate.git
cd anvilate
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Nothing else is required. The materials and standards tables ship inside the package; DXF
output needs the export extra (`pip install -e ".[export]"`), and nothing here does.

## Your first validated part

A 12 mm lifting lug, 80 mm wide, with a 25 mm pin hole, carrying 50 kN:

```python
from anvilate.packs.structural import LiftingLug, screen_structure
from anvilate.units import Quantity

lug = LiftingLug(
    name="padeye",
    width=Quantity.parse("80 mm"),
    hole_diameter=Quantity.parse("25 mm"),
    thickness=Quantity.parse("12 mm"),
    load=Quantity.parse("50 kN"),
    material="ASTM-A36",
)
card = screen_structure([lug], required_safety_factor=2.0)
```

```text
FAIL
  pass   padeye net tension: safety factor 3.30 vs required minimum 2.00
         ASME BTH-1 §3-3
  fail   padeye pin bearing: safety factor 1.50 vs required minimum 2.00
         ASME BTH-1 §3-3
governing: padeye pin bearing
```

Four things happened that are worth naming, because they are the whole design of this
library:

- **The material came from a table**, not from a number you typed. `ASTM-A36` resolved to a
  specified minimum yield with a citation behind it.
- **Both checks ran and both are reported.** The lug is comfortable in tension and short in
  bearing; a screen that returned one number would have returned the wrong one.
- **Every entry cites its clause.** `ASME BTH-1 §3-3`, not "per code".
- **The card is FAIL because its worst entry is**, and `card.governing()` names which — the
  check to fix first. A thicker lug is the fix, and
  [typed repair feedback](repair-feedback.md) will say by how much.

## The same thing from the shell

If your part is a spec document rather than Python:

```bash
anvilate check part.yaml
```

The exit code is the interface: **0 only when every check passed, 1 when one failed, 2 when
a card could not be fully evaluated** — and 2 is not a pass, which is the single rule to
carry into a CI job. [The command-line page](headless-cli.md) has the rest, including
`export`, `verify` and `diff`.

Screening a *spec document* reaches fewer checks than screening a declared element does
today: a Design Spec states a material, a process, dimensions and loads, but not what kind
of structural element the part is, so the analytical tier reports that gap by name rather
than guessing. [Screening a Design Spec](spec-screening.md) says exactly what a document
alone can be screened on.

## What you just got, and what you did not

A **screening** result: closed-form, dimension-checked, cited, and reproducible. Not a
certified design, not a finite element run, and not a substitute for the engineer whose
seal goes on the drawing. Every rendered result says so, and
[what a citation means](citations.md) says precisely what the clause reference claims.

## Where to go next

- [The documentation index](README.md) — everything, arranged by what you are trying to do.
- [Screening by discipline](README.md#screening-by-discipline) — steel, concrete, timber,
  masonry, geotechnical, pressure equipment, building services.
- [The evidence bundle](evidence-bundle.md) — what to hand somebody who has to check you.
