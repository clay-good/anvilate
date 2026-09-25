# Anvilate

*anvil + validate* — describe a mechanical part, get back a physics-validated pass/fail where **every check cites the code it came from**.

![Anvilate screening a cantilever bracket and a lifting lug, then exporting a DXF](docs/demo.gif)

Anvilate runs the engineering checks you'd otherwise do by hand in a spreadsheet — bending, deflection, buckling, resonance, bolted and welded connections, pressure, tolerance stack-ups — and rolls them into one scorecard that **won't hand you a silent green**. A check it could not run says so; it never counts as a pass. Local-first and open source: no cloud, no LLM, no account.

> **Status: pre-alpha (v0.0.1).** The analytical screening core, the command line, the MCP server, and a few audited 3D patterns (STEP, DXF, 3MF) work today. The natural-language front end, wider geometry catalog, FEA, and semantic PMI described under [Where this is going](#where-this-is-going) are still being built.

## Install

Python 3.11+.

```bash
git clone https://github.com/clay-good/anvilate.git
cd anvilate
python -m venv .venv && source .venv/bin/activate
pip install -e ".[geometry,export,pdf]"  # geometry adds B-Rep/STEP; export adds DXF; pdf reads requirement sheets
```

## Try it

Run any of the worked examples. Each is self-contained, needs no network, and prints its result: a scorecard for the screening examples, the computed values for the analysis ones.

```bash
python examples/cantilever_bracket_check.py
```

```text
[PASS] bending yield: safety factor 1.84 vs required minimum 1.50
[FAIL] tip deflection: deflection 36.284 mm vs limit 15.000 mm
scorecard FAIL (2 checks); governing: tip deflection
```

The aluminum bracket is strong enough but too bendy — the deflection check catches what a yield-only hand check would wave through.

## Screen a part from a document

Describe the part in YAML. The required safety factor is read from
`constraints.min_safety_factor`, never invented.

```yaml
name: padeye
description: A lifting padeye on a skid frame.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
element_type: lifting_lug
element_params:
  name: padeye
  material: ASTM-A36
  width: {magnitude: 120.0, unit: mm}
  hole_diameter: {magnitude: 40.0, unit: mm}
  thickness: {magnitude: 20.0, unit: mm}
  load: {magnitude: 60.0, unit: kN}
constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}
acceptance: {tiers: [T1_analytical]}
```

It ships as [`examples/padeye.spec.yaml`](examples/padeye.spec.yaml):

```bash
anvilate check examples/padeye.spec.yaml
```

```text
padeye: PASS
  pass           padeye net tension
                 safety factor 6.67 vs required minimum 2.00
                 [ASME BTH-1 §3-3]
  pass           padeye pin bearing
                 safety factor 3.33 vs required minimum 2.00
                 [ASME BTH-1 §3-3]
  pass           material resolution
                 ASTM-A36 resolves in the bundled materials database
  governing:     padeye pin bearing (pass)
  not evaluated: 0
  out of depth:  0
```

See [screening a document](docs/spec-screening.md).

## Or from Python

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
print(card)   # scorecard FAIL (2 checks); governing: tip deflection
```

Units are first-class — mix `kip`, `ksi`, `in`, `mm` and `MPa` freely.

## What's inside

- **Screening packs** for structural steel, cold-formed steel, aluminum, concrete, masonry, timber, geotechnical, hydraulics, pressure vessels, process piping, lifting devices, machinery, and building services — each check naming the clause it came from.
- **An analytical library** (237 closed-form modules and 1,883 public symbols, each dimension-checked and tested; 6,520 tests).
- **Reports and exports:** calculation reports (text, HTML, PDF), DXF, STEP, 3MF and QIF — written only when the checks pass, or stamped `UNVALIDATED`.
- **A command line** — `anvilate check`, `build`, `export`, `verify`, `interfaces`, `diff`, `doctor`. See [the CLI guide](docs/headless-cli.md).
- **An MCP server** exposing the pipeline's eight operations to an agent. See [agent integration](docs/agent-mcp-integration.md).
- **510 runnable examples**, each executed in CI. Start with the [highlights](docs/example-highlights.md) or browse the [full gallery](examples/README.md).

## Learn more

- [Quickstart](docs/quickstart.md) — install, screen a lifting lug, and read a cited verdict in under ten minutes.
- [Documentation index](docs/README.md) — every guide, arranged by task.
- [Adding a check](docs/contributing-analysis.md) and [CONTRIBUTING.md](CONTRIBUTING.md) — for contributors.

## Where this is going

The goal is a plain-English request that compiles into the same validated scorecard *and* a parametric solid you can open in CATIA, SolidWorks, or NX. The LLM only writes the spec and proposes edits; the geometry and validation stay deterministic and run identically without any AI. Nothing unvalidated leaves the tool. The design reference is [`openspec/specs/`](openspec/specs/).

## Security

Anvilate reads documents from other people and is built for it: safe YAML loading, no `eval`/`exec`/`pickle`, and no network access without stated consent. See [SECURITY.md](SECURITY.md) for each property, the test that holds it, and how to report a vulnerability.

## License

MIT — see [LICENSE](LICENSE).
