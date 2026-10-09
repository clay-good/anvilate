# Anvilate

<!-- mcp-name: io.github.clay-good/anvilate -->

*anvil + validate* — describe a mechanical part, get back a physics-validated pass/fail where **every check cites the code it came from**.

Anvilate runs the engineering checks you'd otherwise do by hand in a spreadsheet — bending, deflection, buckling, resonance, bolted and welded connections, pressure, tolerance stack-ups — and rolls them into one scorecard that **won't hand you a silent green**. A check it could not run says so; it never counts as a pass. Local-first and open source: no cloud, no LLM, no account.

> **Status: pre-alpha (v0.0.1).** The analytical screening core, the command line, the MCP server, and a few audited 3D patterns (STEP, DXF, 3MF) work today. Plain-English requests work through your own MCP agent, which writes the spec. The wider geometry catalog, FEA, and semantic PMI described under [Where this is going](#where-this-is-going) are still being built.

## Install

Python 3.11+.

```bash
git clone https://github.com/clay-good/anvilate.git
cd anvilate
python -m venv .venv && source .venv/bin/activate
pip install -e ".[geometry,export,pdf]"  # geometry adds B-Rep/STEP; export adds DXF; pdf reads requirement sheets
```

## Use it from your AI agent

Anvilate has no language model of its own. Your agent (Claude Code, Claude Desktop, Cursor, or any MCP client) is the model: it turns your description into a spec, and Anvilate validates and screens it locally over stdio. There is no account, no API key and nothing hosted.

```bash
claude mcp add anvilate -- "$(which anvilate-mcp)"
```

Then ask in plain English, for example *"Check an ASTM A36 lifting lug, 80 mm wide, 12 mm thick with a 25 mm pin hole, for a 50 kN load and a safety factor of 2."* The agent writes the spec, Anvilate returns a scorecard where every check cites its source, and a check that could not run says so. Other clients and the full loop are in [agent integration](docs/agent-mcp-integration.md).

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
- **An analytical library** (237 closed-form modules and 1,883 public symbols, each dimension-checked and tested; 7,335 tests), with machine-readable repairs now spanning units, tolerances, manufacturing quality, geometry, casting, casting gating, centrifugal casting, injection molding, sheet-metal bending and drawing, wire drawing, shear spinning, thermoforming, extrusion, forging, rolling, conventional machining, broaching, drilling, grinding, EDM, electrochemical machining, laser cutting, weld design, arc-welding heat input, resistance welding, electroplating, shot peening, wear, corrosion and asset integrity, Hall–Petch strengthening, creep and rupture life, elastic constants, axial response, stress combination and concentration, reinforced- and prestressed-concrete response, masonry allowable-stress design, timber member, record, and stability design, aluminum member and weld-affected design, cold-formed-steel effective-width and Direct Strength Method checks, structural load combinations, steel compactness, elastic foundations, riveted joints, O-ring glands, lifting mechanics, work-energy, impact and friction mechanics, power transmission, living hinges, ball screws, centrifugal governors, mechanism kinematics, fundamental motion, gravitation, radioactivity, and radiation shielding, electromechanical sensors, surface engineering, fluid storage, HVAC duct and fan sizing, compressible flow, gas compression, combustion, chemical equilibria, geometric, wave, and instrument optics, quantum photonics, shaft torsion, springs, and shared branch-selector inputs; every analysis module now raises its refusals with a structured remedy naming the parameter to correct, and [a ledger](docs/api/raised-refusals-without-remedies.txt) counts the core refusals still waiting for one.
- **Reports and exports:** calculation reports (text, HTML, PDF), DXF, STEP, 3MF and QIF — written only when the checks pass, or stamped `UNVALIDATED`, with machine-readable repairs when geometry cannot be released.
- **A command line** — `anvilate check`, `build`, `export`, `verify`, `interfaces`, `diff`, `doctor`, `fetch`, with field-specific repairs for invalid specs. See [the CLI guide](docs/headless-cli.md).
- **An MCP server** exposing the pipeline's eight operations to an agent over stdio, with durable task results, worker-failure reporting, and abandoned-task recovery. Malformed requests receive protocol errors without stopping the stream. Each release publishes its pinned `uvx` install command to the official registry. See [agent integration](docs/agent-mcp-integration.md) and the [release procedure](docs/mcp-registry-release.md).
- **510 runnable examples**, each executed in CI. Start with the [highlights](docs/example-highlights.md) or browse the [full gallery](examples/README.md).

## Learn more

- [Quickstart](docs/quickstart.md) — install, screen a lifting lug, and read a cited verdict in under ten minutes.
- [Documentation index](docs/README.md) — every guide, arranged by task.
- [Design decisions](docs/design-decisions.md) — why Anvilate is fully local and MCP-only, with no model of its own.
- [Adding a check](docs/contributing-analysis.md) and [CONTRIBUTING.md](CONTRIBUTING.md) — for contributors.

## Where this is going

The goal is a plain-English request that compiles into the same validated scorecard *and* a parametric solid you can open in CATIA, SolidWorks, or NX. Your own agent writes the spec and proposes edits over MCP; the geometry and validation stay deterministic, run locally, and run identically without any AI. Nothing unvalidated leaves the tool. The design reference is [`openspec/specs/`](openspec/specs/).

## Security

Anvilate reads documents from other people and is built for it: safe YAML loading, no `eval`/`exec`/`pickle`, and no network access without stated consent. See [SECURITY.md](SECURITY.md) for each property, the test that holds it, and how to report a vulnerability.

## License

MIT — see [LICENSE](LICENSE).
