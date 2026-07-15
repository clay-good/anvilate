# Anvilate

*anvil + validate* — describe a mechanical part, get back a physics-validated pass/fail where **every check cites the code it came from**.

![Anvilate screening a cantilever bracket and a lifting lug, then exporting a DXF](docs/demo.gif)

Anvilate is a **local-first, open-source** design tool for mechanical, structural, and industrial engineers. It runs the analytical screens you'd otherwise do by hand in a spreadsheet — bending, deflection, buckling, resonance, bolted and welded connections, contact, thick-wall pressure, tolerance stack-ups — and rolls them into one scorecard that **won't hand you a silent green**. No cloud, no LLM required, no account.

> **Status: pre-alpha (v0.0.1).** The deterministic engineering core is real, tested, and runnable today. The natural-language front end, 3D geometry, FEA, and STEP export described under [Where this is going](#where-this-is-going) are still being built.

## Quickstart

Python 3.11+.

```bash
git clone https://github.com/clay-good/anvilate.git
cd anvilate
python -m venv .venv && source .venv/bin/activate
pip install -e ".[export]"      # drop [export] if you don't need DXF output
```

Run any of the worked examples — each is self-contained, needs no network, and prints a scorecard:

```bash
python examples/cantilever_bracket_check.py
```

```text
[PASS] bending yield: safety factor 1.84 vs required minimum 1.50
[FAIL] tip deflection: deflection 36.284 mm vs limit 15.000 mm
scorecard FAIL (2 checks)
```

The aluminum bracket is strong enough but too bendy — the deflection screen catches what a yield-only hand check would wave through.

## Write your own screen

The whole flow is: pull a material, describe the geometry and load, roll the checks into a `Scorecard`.

```python
from anvilate.analysis import (
    cantilever_end_load, rectangular_second_moment,
    strength_scorecard, deflection_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

al = default_materials_db().get("AA-6061-T6")
I = rectangular_second_moment(Quantity.parse("20 mm"), Quantity.parse("10 mm"))

beam = cantilever_end_load(
    force=Quantity.parse("100 N"),
    length=Quantity.parse("500 mm"),
    second_moment=I,
    extreme_fibre=Quantity.parse("5 mm"),
    elastic_modulus=al.elastic_modulus.quantity,
)

card = Scorecard(entries=(
    strength_scorecard("bending yield", stress=beam.max_bending_stress,
                       allowable=al.yield_strength.quantity, required=1.5),
    deflection_scorecard("tip deflection", deflection=beam.max_deflection,
                         limit=Quantity.parse("15 mm")),
))
print(card)   # scorecard FAIL (2 checks)
```

Units are first-class (SI and US customary — mix `kip`, `ksi`, `in`, `mm`, `MPa` freely); materials come from a provenance-tagged database; safety factors and citations travel with every result.

## What you can do today

Over 45 runnable examples, each executed in CI so they stay honest. A few:

| Run this | What it shows |
|---|---|
| `machine_on_floor_beam.py` | Declaring where a load *actually* sits recovers real margin the worst-case mid-span guess throws away (FAIL 1.19 → PASS 1.58). |
| `lug_drawing.py` | Code-check a lifting lug (ASME BTH-1), then export its outline to a fabrication-ready DXF. |
| `column_base_plate.py` | A base plate checked for concrete bearing (AISC J8) *and* plate bending (Design Guide 1) — bearing passes, the thin plate fails. |
| `motor_mount_resonance.py` | A mount that's statically bulletproof but resonates below running speed — the dimension a static hand calc never sees. |
| `hydraulic_cylinder_wall.py` | The thin-wall formula reads a comfortable pass; the exact Lamé solution says the barrel fails. |
| `tolerance_stackup.py` | A 1D stack-up worst-case rejects the design, yet Monte Carlo predicts 99%+ assembly yield. |

Full annotated gallery: [`examples/README.md`](examples/README.md).

What's implemented: a units layer, the typed **Design Spec IR**, a standards/materials database (materials, fasteners, bearings, NEMA, dowels, T-slot), the T1 analytical library above, ISO 286 fits + tolerance stack-ups + DFM process-capability checks, an auditable evidence/provenance roll-up, DXF export, and a structural discipline pack (beams, columns, beam-columns, bolted/welded connections, base plates, lugs, gussets — AISC 360 / ACI 318 / ASME BTH-1, every check citing its clause).

## Where this is going

The screens above are the trustworthy core. The end goal is to wrap them so a plain-English request compiles into that same validated scorecard *and* a parametric solid you can open in CATIA, SolidWorks, or NX:

```
 natural language ──► typed Design Spec ──► parametric B-Rep geometry
        ▲                                          │
        │                                          ▼
   human review ◄── validation report ◄── physics + DFM + FEA checks
        │                                          │
        └───────── agent self-corrects ◄───────────┘  (until checks pass)
                            │
                            ▼
              STEP AP242 · DXF · 2D drawing · source code
```

The LLM is a replaceable component that only writes the spec and proposes edits; the geometry and validation pipeline is deterministic and runs identically with or without any AI. Nothing unvalidated leaves the tool.

The behavioral contract for every subsystem is specified up front in [`openspec/specs/`](openspec/specs/) — that's the authoritative design reference, including the roadmap, non-goals, and risk analysis.

## License

MIT — see [LICENSE](LICENSE). GPL-licensed analysis engines (Gmsh, CalculiX) are invoked as separate subprocesses with file-based interchange, keeping Anvilate's own code MIT.
